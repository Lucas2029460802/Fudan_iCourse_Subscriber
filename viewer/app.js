const nav = document.querySelector("#nav");
const doc = document.querySelector("#doc");
const crumb = document.querySelector("#crumb");
const search = document.querySelector("#search");
const prevBtn = document.querySelector("#prev");
const nextBtn = document.querySelector("#next");
const menuBtn = document.querySelector("#menu");
const sidebar = document.querySelector(".sidebar");
const wideQuery = window.matchMedia("(min-width: 861px)");
const SIDEBAR_KEY = "overview-sidebar-collapsed";

let catalog = { courses: [] };
let flat = [];
let current = null;

function labelOf(title) {
  return title.replace(/^(\d{4}-\d{2}-\d{2}) \1/, "$1");
}

function flatten(data, query) {
  const q = query.trim().toLowerCase();
  const items = [];
  for (const course of data.courses) {
    const lectures = course.lectures.filter((lec) => {
      if (!q) return true;
      const blob = `${course.title} ${lec.title}`.toLowerCase();
      return blob.includes(q);
    });
    if (!lectures.length) continue;
    items.push({ course, lectures });
  }
  return items;
}

function renderNav() {
  flat = flatten(catalog, "").flatMap((g) =>
    g.lectures.map((lec) => ({ course: g.course, lecture: lec }))
  );
  const groups = flatten(catalog, search.value);
  if (!groups.length) {
    nav.innerHTML = '<div class="empty-filter">没有匹配的课次</div>';
    syncPager();
    return;
  }
  nav.innerHTML = groups.map((g) => {
    const buttons = g.lectures.map((lec) => {
      const active = current
        && current.course.dir === g.course.dir
        && current.lecture.file === lec.file;
      return `<button class="lecture${active ? " active" : ""}" type="button" data-dir="${escapeAttr(g.course.dir)}" data-file="${escapeAttr(lec.file)}">${escapeHtml(labelOf(lec.title))}</button>`;
    }).join("");
    return `<div class="course-name">${escapeHtml(g.course.title)}<span>${g.lectures.length}</span></div>${buttons}`;
  }).join("");
  syncPager();
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

function escapeAttr(s) {
  return escapeHtml(s);
}

// CommonMark ignores **...** when the marker sits between CJK punctuation
// (。，（）) and a following character. Turn those spans into HTML first.
function loosenEmphasis(text) {
  const codes = [];
  const stripped = text.replace(/``[\s\S]*?``|`[^`\n]+`/g, (block) => {
    codes.push(block);
    return `\u0000C${codes.length - 1}\u0000`;
  });
  let out = stripped;
  out = out.replace(/(?<!\\)\*\*\*(?!\s)([^*\n]*?\S)\*\*\*(?!\*)/g, "<em><strong>$1</strong></em>");
  out = out.replace(/(?<!\\)\*\*(?!\s)([^*\n]*?\S)\*\*(?!\*)/g, "<strong>$1</strong>");
  out = out.replace(/(?<!\\)(?<!\*)\*(?!\s)([^*\n]*?\S)\*(?!\*)/g, "<em>$1</em>");
  return out.replace(/\u0000C(\d+)\u0000/g, (_, i) => codes[+i]);
}

function renderMarkdown(md) {
  const fences = [];
  const math = [];
  let text = md.replace(/```[\s\S]*?```/g, (block) => {
    fences.push(block);
    return `\n\nFENCE${fences.length - 1}END\n\n`;
  });
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => {
    math.push({ tex: tex.trim(), display: true });
    return `MATH${math.length - 1}END`;
  });
  text = text.replace(/(^|[^\\$])\$(?!\$)([^\n$]+?)\$(?!\$)/g, (all, pre, tex) => {
    math.push({ tex: tex.trim(), display: false });
    return `${pre}MATH${math.length - 1}END`;
  });
  text = loosenEmphasis(text);
  text = text.replace(/FENCE(\d+)END/g, (_, i) => fences[+i]);
  let html = marked.parse(text);
  html = html.replace(/<a href="mailto:[^"]*">([\s\S]*?)<\/a>/g, "$1");
  html = html.replace(/MATH(\d+)END/g, (_, i) => {
    const item = math[+i];
    if (!window.katex) {
      return item.display ? `$$${escapeHtml(item.tex)}$$` : `$${escapeHtml(item.tex)}$`;
    }
    return katex.renderToString(item.tex, {
      displayMode: item.display,
      throwOnError: false,
      strict: "ignore",
    });
  });
  return html;
}

async function openLecture(course, lecture, pushHash) {
  current = { course, lecture };
  crumb.textContent = `${course.title}  ·  ${labelOf(lecture.title)}`;
  doc.innerHTML = '<p class="placeholder">正在打开…</p>';
  renderNav();
  const url = `/api/lecture?course=${encodeURIComponent(course.dir)}&file=${encodeURIComponent(lecture.file)}`;
  const res = await fetch(url);
  if (!res.ok) {
    doc.innerHTML = '<p class="placeholder">这篇笔记暂时读不到，可能正在写入。过几秒再打开一次。</p>';
    return;
  }
  const data = await res.json();
  doc.innerHTML = `<div class="doc-inner">${renderMarkdown(data.markdown)}</div>`;
  doc.scrollTop = 0;
  if (pushHash) {
    history.replaceState(null, "", `#${encodeURIComponent(course.dir)}/${encodeURIComponent(lecture.file)}`);
  }
  sidebar.classList.remove("open");
  updateMenuButton();
}

function sidebarCollapsed() {
  return document.documentElement.classList.contains("sidebar-collapsed");
}

function updateMenuButton() {
  const wide = wideQuery.matches;
  const open = wide ? !sidebarCollapsed() : sidebar.classList.contains("open");
  menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
  menuBtn.setAttribute("aria-label", open ? "隐藏目录" : "显示目录");
  sidebar.toggleAttribute("inert", wide && sidebarCollapsed());
}

function setSidebarCollapsed(collapsed) {
  document.documentElement.classList.toggle("sidebar-collapsed", collapsed);
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  } catch (e) {}
  updateMenuButton();
}

function indexOfCurrent() {
  if (!current) return -1;
  return flat.findIndex((item) =>
    item.course.dir === current.course.dir && item.lecture.file === current.lecture.file
  );
}

function syncPager() {
  const i = indexOfCurrent();
  prevBtn.disabled = i <= 0;
  nextBtn.disabled = i < 0 || i >= flat.length - 1;
}

function step(delta) {
  const i = indexOfCurrent();
  const next = flat[i + delta];
  if (next) openLecture(next.course, next.lecture, true);
}

async function loadCatalog() {
  const res = await fetch("/api/catalog");
  catalog = await res.json();
  renderNav();
  if (!current && flat.length) {
    const fromHash = lectureFromHash();
    if (fromHash) openLecture(fromHash.course, fromHash.lecture, false);
  } else if (current) {
    const still = flat.find((item) =>
      item.course.dir === current.course.dir && item.lecture.file === current.lecture.file
    );
    if (!still) renderNav();
  }
}

function lectureFromHash() {
  const raw = decodeURIComponent(location.hash.replace(/^#/, ""));
  const slash = raw.indexOf("/");
  if (slash <= 0) return null;
  const dir = raw.slice(0, slash);
  const file = raw.slice(slash + 1);
  for (const course of catalog.courses) {
    if (course.dir !== dir) continue;
    const lecture = course.lectures.find((lec) => lec.file === file);
    if (lecture) return { course, lecture };
  }
  return null;
}

nav.addEventListener("click", (event) => {
  const button = event.target.closest(".lecture");
  if (!button) return;
  const course = catalog.courses.find((c) => c.dir === button.dataset.dir);
  const lecture = course && course.lectures.find((lec) => lec.file === button.dataset.file);
  if (course && lecture) openLecture(course, lecture, true);
});

search.addEventListener("input", renderNav);
prevBtn.addEventListener("click", () => step(-1));
nextBtn.addEventListener("click", () => step(1));
menuBtn.addEventListener("click", () => {
  if (wideQuery.matches) {
    setSidebarCollapsed(!sidebarCollapsed());
    return;
  }
  sidebar.classList.toggle("open");
  updateMenuButton();
});
wideQuery.addEventListener("change", () => {
  if (wideQuery.matches) sidebar.classList.remove("open");
  updateMenuButton();
});
updateMenuButton();

document.addEventListener("keydown", (event) => {
  if (event.target === search) return;
  if (event.key === "ArrowLeft") step(-1);
  if (event.key === "ArrowRight") step(1);
});

loadCatalog();
setInterval(loadCatalog, 20000);
