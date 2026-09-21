"""Write course summaries as Markdown files grouped by course.

Used by the nightly / single-run workflows: after processing, every course
gets a folder and every summarized lecture becomes a file inside it.  The
CI job then force-pushes that tree to the ``Overview`` branch.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data.database import Database

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_SPACE = re.compile(r"\s+")


def safe_component(name: str, max_len: int = 80) -> str:
    """Sanitise a course/lecture title for use as a path component."""
    text = _UNSAFE.sub("_", (name or "").strip())
    text = _MULTI_SPACE.sub(" ", text).strip(" .")
    return (text[:max_len] if text else "untitled")


def _course_dir_name(course_id: str, title: str) -> str:
    safe_title = safe_component(title)
    if not safe_title or safe_title == "untitled":
        return str(course_id)
    return f"{course_id}_{safe_title}"


def _lecture_filename(sub_id: str, sub_title: str, date: str,
                      used: set[str]) -> str:
    """Build a unique ``.md`` filename for one lecture inside a course folder."""
    parts = [p for p in (date, sub_title) if p]
    base = safe_component(" ".join(parts) if parts else sub_id)
    name = f"{base}.md"
    if name in used:
        name = f"{base}_{sub_id}.md"
    used.add(name)
    return name


def _lecture_markdown(course_title: str, teacher: str, lecture: dict) -> str:
    sub_title = lecture.get("sub_title") or lecture["sub_id"]
    date = lecture.get("date") or ""
    summary = (lecture.get("summary") or "").rstrip() + "\n"
    lines = [f"# {sub_title}", ""]
    meta = [f"- 课程：{course_title}"]
    if teacher:
        meta.append(f"- 教师：{teacher}")
    if date:
        meta.append(f"- 日期：{date}")
    lines.extend(meta)
    lines.extend(["", "---", "", summary])
    return "\n".join(lines)


def _course_readme(course_id: str, title: str, teacher: str,
                   entries: list[tuple[str, str, str]]) -> str:
    """``entries`` is ``(filename, sub_title, date)`` in display order."""
    lines = [f"# {title or course_id}", ""]
    if teacher:
        lines.append(f"教师：{teacher}")
        lines.append("")
    lines.append(f"课程 ID：`{course_id}`")
    lines.append("")
    if not entries:
        lines.append("暂无摘要。")
        lines.append("")
        return "\n".join(lines)
    lines.append("## 课次")
    lines.append("")
    for filename, sub_title, date in entries:
        label = f"{date} {sub_title}".strip() if date else sub_title
        lines.append(f"- [{label}]({filename})")
    lines.append("")
    return "\n".join(lines)


def dump_from_db(db: "Database", out_dir: str) -> tuple[int, int]:
    """Write every summarized lecture into ``out_dir``.

    Layout::

        out_dir/
          README.md
          {course_id}_{title}/
            README.md
            {date} {sub_title}.md

    Existing files in ``out_dir`` are replaced so a deleted lecture
    disappears on the next publish.  Returns ``(n_courses, n_lecture_files)``.
    """
    os.makedirs(out_dir, exist_ok=True)

    # Drop previously written course folders so removed courses don't linger
    # when this is the staging dir for a force-push.
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif name != "README.md":
            os.remove(path)

    courses = db.list_courses()
    n_files = 0
    n_courses = 0
    index_lines = [
        "# 课程摘要",
        "",
        "本目录由 iCourse Subscriber 工作流自动更新。"
        "每个文件夹对应一门课程，文件夹内为各课次 Markdown 摘要。",
        "",
        "## 课程",
        "",
    ]

    for course in courses:
        course_id = str(course["course_id"])
        title = course.get("title") or course_id
        teacher = course.get("teacher") or ""
        lectures = db.list_lecture_summaries(course_id)
        if not lectures:
            continue

        folder = _course_dir_name(course_id, title)
        course_path = os.path.join(out_dir, folder)
        os.makedirs(course_path, exist_ok=True)

        used_names: set[str] = {"README.md"}
        entries: list[tuple[str, str, str]] = []
        for lec in lectures:
            filename = _lecture_filename(
                str(lec["sub_id"]),
                lec.get("sub_title") or "",
                lec.get("date") or "",
                used_names,
            )
            with open(os.path.join(course_path, filename), "w",
                      encoding="utf-8") as fh:
                fh.write(_lecture_markdown(title, teacher, lec))
            entries.append((
                filename,
                lec.get("sub_title") or str(lec["sub_id"]),
                lec.get("date") or "",
            ))
            n_files += 1

        with open(os.path.join(course_path, "README.md"), "w",
                  encoding="utf-8") as fh:
            fh.write(_course_readme(course_id, title, teacher, entries))

        index_lines.append(f"- [{title}]({folder}/)")
        n_courses += 1

    if n_courses == 0:
        index_lines.append("暂无已生成摘要的课程。")
    index_lines.append("")

    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(index_lines))

    return n_courses, n_files
