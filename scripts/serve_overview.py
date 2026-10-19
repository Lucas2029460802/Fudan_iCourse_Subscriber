#!/usr/bin/env python3
"""Local reader for the overview/ Markdown notes.

Usage:
    python scripts/serve_overview.py
    python scripts/serve_overview.py --port 8765 --no-open
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.runtime import config  # noqa: E402

VIEWER = ROOT / "viewer"
OVERVIEW = Path(config.OVERVIEW_DIR)
if not OVERVIEW.is_absolute():
    OVERVIEW = (ROOT / OVERVIEW).resolve()


def _catalog() -> dict:
    courses = []
    if not OVERVIEW.is_dir():
        return {"courses": []}
    for course_dir in sorted(p for p in OVERVIEW.iterdir() if p.is_dir()):
        lectures = []
        for md in sorted(course_dir.glob("*.md")):
            if md.name == "README.md":
                continue
            lectures.append({"file": md.name, "title": md.stem})
        name = course_dir.name
        if "_" in name:
            course_id, title = name.split("_", 1)
        else:
            course_id, title = name, name
        courses.append({
            "dir": name,
            "id": course_id,
            "title": title,
            "lectures": lectures,
        })
    return {"courses": courses}


def _lecture_path(course: str, filename: str) -> Path | None:
    if not course or not filename:
        return None
    if "/" in course or "\\" in course or "/" in filename or "\\" in filename:
        return None
    if course in (".", "..") or filename in (".", ".."):
        return None
    path = (OVERVIEW / course / filename).resolve()
    try:
        path.relative_to(OVERVIEW.resolve())
    except ValueError:
        return None
    if path.suffix.lower() != ".md" or not path.is_file():
        return None
    return path


def _static_path(url_path: str) -> Path | None:
    rel = unquote(url_path).lstrip("/")
    if not rel or rel.endswith("/"):
        return None
    path = (VIEWER / rel).resolve()
    try:
        path.relative_to(VIEWER.resolve())
    except ValueError:
        return None
    if path.is_file():
        return path
    return None


_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            page = (VIEWER / "index.html").read_bytes()
            self._send(200, page, "text/html; charset=utf-8")
            return
        if path == "/api/catalog":
            body = json.dumps(_catalog(), ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        if path == "/api/lecture":
            qs = parse_qs(parsed.query)
            course = (qs.get("course") or [""])[0]
            filename = (qs.get("file") or [""])[0]
            lecture = _lecture_path(course, filename)
            if lecture is None:
                self._send(404, b'{"error":"not found"}', "application/json")
                return
            body = json.dumps(
                {"markdown": lecture.read_text(encoding="utf-8")},
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        static = _static_path(path)
        if static is not None:
            self._send(200, static.read_bytes(), _TYPES.get(static.suffix.lower(), "application/octet-stream"))
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read overview notes in a browser")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"课程笔记  {url}")
    print(f"目录      {OVERVIEW}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
