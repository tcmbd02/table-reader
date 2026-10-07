"use strict";
// Table Reader page. Plain JS, no build step. All text from the server is inserted with textContent (never innerHTML).

const $ = (id) => document.getElementById(id);
const QUALITY = { CLEAR: "Clear", MOSTLY_CLEAR: "Mostly clear", FADED: "Faded or small print", ILLEGIBLE: "Hard to read" };
let claudeReady = false;
let currentId = null;
let currentDoc = null;
let uploading = false;

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== false && v !== null && v !== undefined) node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) if (c) node.append(c);
  return node;
}

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
  let res;
  try { res = await fetch(url, opts); }
  catch { throw new Error("Table Reader is not running any more. Close this tab and open Table Reader again."); }
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    if (data && data.message) throw new Error(data.message);
    if (res.status === 404 || res.status === 405) {
      throw new Error("Table Reader was updated while it was open. Close its window, open Table Reader again, then reload this page.");
    }
    throw new Error("Something went wrong. Reload the page and try again.");
  }
  return data;
}

// ------------------------------------------------------------------------------------------------ Claude status
let loginTimer = null;

async function refreshClaude() {
  const box = $("claude-box");
  let s;
  try { s = await api("GET", "/api/status"); }
  catch (e) { box.replaceChildren(el("span", { class: "problem", text: e.message })); return; }
  claudeReady = s.logged_in;
  if (s.logged_in) {
    clearInterval(loginTimer); loginTimer = null;
    const plan = s.plan ? ` (${s.plan[0].toUpperCase()}${s.plan.slice(1)})` : "";
    box.replaceChildren(el("span", { class: "ok", text: "✓ Claude connected" }),
      el("span", { class: "muted", text: `${s.email || ""}${plan}` }));
  } else {
    const kids = [el("span", { class: "problem", text: s.message || "Claude is not connected." })];
    if (s.installed) kids.push(el("button", { class: "primary", text: "Sign in", onclick: startLogin }));
    box.replaceChildren(...kids);
  }
  updateDropState();
}

async function startLogin() {
  try { await api("POST", "/api/login"); }
  catch (e) { $("claude-box").replaceChildren(el("span", { class: "problem", text: e.message })); return; }
  $("claude-box").replaceChildren(el("span", { text: "Finish signing in in the browser window that just opened…" }));
  clearInterval(loginTimer);
  let tries = 0;
  loginTimer = setInterval(() => { if (++tries > 100) { clearInterval(loginTimer); refreshClaude(); } else refreshClaude(); }, 3000);
}

// ------------------------------------------------------------------------------------------------ upload
function updateDropState() {
  const drop = $("drop");
  drop.classList.toggle("disabled", !claudeReady || uploading);
  drop.setAttribute("aria-disabled", String(!claudeReady || uploading));
}

function showMessages(items, kind) {
  $("upload-messages").replaceChildren(...items.map((t) => el("div", { class: `banner ${kind}`, text: t })));
}

async function upload(fileList) {
  const files = [...fileList];
  if (!files.length || uploading) return;
  if (!claudeReady) { showMessages(["Connect your Claude account first (top right), then add your files."], "error"); return; }
  uploading = true; updateDropState();
  showMessages([`Adding ${files.length} file${files.length > 1 ? "s" : ""}…`], "info");
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));
  try {
    const r = await api("POST", "/api/jobs", form);
    showMessages(r.rejected.map((x) => x.message), "error");
    if (r.created.length === 1 && !r.rejected.length) { location.hash = `#/doc/${encodeURIComponent(r.created[0].id)}`; }
  } catch (e) { showMessages([e.message], "error"); }
  uploading = false; updateDropState();
  loadRecent();
}

function setupDrop() {
  const drop = $("drop"), input = $("file-input");
  drop.addEventListener("click", () => {
    if (!claudeReady) showMessages(["Connect your Claude account first (top right), then add your files."], "error");
    else if (!uploading) input.click();
  });
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); drop.click(); } });
  input.addEventListener("change", () => { upload(input.files); input.value = ""; });
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); });
  // a file dropped beside the box must not make the browser leave the page
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());
}

// ------------------------------------------------------------------------------------------------ recent files
function progressText(j) {
  if (j.status === "queued") return "Waiting…";
  if (j.status === "reading") return j.pages_total ? `Reading page ${Math.min(j.pages_done + 1, j.pages_total)} of ${j.pages_total}…` : "Preparing…";
  if (j.status === "done") return "Finished";
  return "Stopped";
}

async function loadRecent() {
  let jobs;
  try { jobs = await api("GET", "/api/jobs"); } catch (e) { showMessages([e.message], "error"); return; }
  const list = $("recent");
  list.replaceChildren(...jobs.map((j) => {
    const cancelled = j.status === "failed" && j.error && j.error.code === "CANCELLED";
    const active = j.status === "queued" || j.status === "reading";
    const cls = j.status === "done" ? "pill good" : j.status === "failed" && !cancelled ? "pill bad" : "pill";
    const li = el("li", {},
      el("span", { class: "name", text: j.name }),
      el("span", { class: "when", text: new Date(j.created).toLocaleString() }),
      el("span", { class: cls, text: cancelled ? "Cancelled" : progressText(j) }),
      active && el("button", { text: "Cancel", onclick: async () => {
        try { await api("POST", `/api/jobs/${encodeURIComponent(j.id)}/cancel`); } catch (e) { showMessages([e.message], "error"); }
        loadRecent();
      } }),
      el("button", { text: "Open", onclick: () => { location.hash = `#/doc/${encodeURIComponent(j.id)}`; } }));
    if (j.status === "failed" && j.error && !cancelled) li.append(el("div", { class: "muted", style: "flex-basis:100%", text: j.error.message }));
    return li;
  }));
  $("recent-empty").hidden = jobs.length > 0;
  return jobs;
}

// ------------------------------------------------------------------------------------------------ document view
function findCell(doc, loc) {
  const page = doc.pages.find((p) => p.page === loc.page);
  if (!page) return null;
  if (loc.header !== undefined) return page.header_fields[loc.header]?.cell ?? null;
  return page.rows[loc.row]?.cells[loc.column] ?? null;
}

async function saveCell(loc, value, node) {
  const change = { page: loc.page, value };
  if (loc.header !== undefined) change.header = loc.header; else { change.row = loc.row; change.column = loc.column; }
  try {
    const doc = await api("PUT", `/api/jobs/${encodeURIComponent(currentId)}/cells`, { changes: [change] });
    currentDoc = doc;
    const cell = findCell(doc, loc);
    if (cell) paintCell(node, loc, cell);
    paintStatus(doc);
  } catch (e) { alert(e.message); }
}

// Fills a .cell element (input + helper buttons) from a merged cell. Called on first draw and after each save.
function paintCell(node, loc, cell) {
  node.className = "cell" + (cell.needs_review ? " flag" : "") + (cell.edited ? " edited" : "");
  node.title = cell.needs_review ? (cell.unclear_reason || "Claude was not sure about this cell.") : "";
  const input = node.querySelector("input");
  if (document.activeElement !== input) input.value = cell.value ?? "";
  input.dataset.original = cell.value ?? "";
  input.setAttribute("aria-label", cell.needs_review ? "Cell to check. Type the correct value." : "Cell value");
  node.querySelector(".tools")?.remove();
  const tools = el("div", { class: "tools" });
  if (cell.needs_review) {
    tools.append(el("span", { class: "reason", text: cell.unclear_reason || "Please check this cell." }));
    if (cell.raw_text) {
      tools.append(el("span", { class: "seen", text: `Claude saw: ${cell.raw_text}` }),
        el("button", { type: "button", text: "Use this", onclick: () => saveCell(loc, cell.raw_text.trim(), node) }));
    }
    tools.append(el("button", { type: "button", text: "It's empty", onclick: () => saveCell(loc, "", node) }));
  } else if (cell.edited) {
    tools.append(el("button", { type: "button", text: "Undo my change", onclick: () => saveCell(loc, null, node) }));
  }
  if (tools.children.length) node.append(tools);
}

function makeCell(loc, cell) {
  const input = el("input", { type: "text", autocomplete: "off", spellcheck: "false" });
  const node = el("div", {}, input);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") input.blur();
    else if (e.key === "Escape") { input.value = input.dataset.original; input.blur(); }
  });
  input.addEventListener("change", () => {
    const value = input.value.trim();
    const c = findCell(currentDoc, loc);
    if (!c) return;
    if (value === "" && c.needs_review) return;                 // empty box on a flagged cell: use "It's empty" to confirm
    if (value === (c.value ?? "")) return;
    saveCell(loc, value, node);
  });
  paintCell(node, loc, cell);
  return node;
}

function buildPage(doc, page) {
  const wrap = el("section", { class: "page" });
  if (doc.pages_total > 1) wrap.append(el("h3", { text: `Page ${page.page} of ${doc.pages_total}` }));

  const notes = [];
  if (page.quality !== "CLEAR") notes.push(`Picture quality: ${QUALITY[page.quality] || page.quality}. Check the highlighted cells carefully.`);
  notes.push(...page.notes);
  const right = el("div");
  if (notes.length) right.append(el("div", { class: "notes" }, el("strong", { text: "Claude's notes" }),
    el("ul", {}, ...notes.map((n) => el("li", { text: n })))));

  if (page.header_fields.length) {
    right.append(el("div", { class: "fields" }, ...page.header_fields.map((f, i) =>
      el("div", { class: "field" }, el("label", { text: f.label }), makeCell({ page: page.page, header: i }, f.cell)))));
  }
  if (!page.rows.length) {
    right.append(el("div", { class: "banner error", text: page.problem || "No table was found on this page." }));
  } else {
    const head = el("tr", {}, el("th", { text: "#" }), ...page.column_labels.map((c) => el("th", { text: c })));
    const body = page.rows.map((row, r) => el("tr", {}, el("td", { class: "rownum", text: String(r + 1) }),
      ...page.column_labels.map((col) => el("td", {}, makeCell({ page: page.page, row: r, column: col }, row.cells[col])))));
    right.append(el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, ...body))));
  }

  const src = `/api/jobs/${encodeURIComponent(doc.id)}/pages/${page.page}`;
  const left = el("div", { class: "page-image" },
    el("a", { href: src, target: "_blank", rel: "noopener" }, el("img", { src, alt: `Original, page ${page.page}` })),
    el("p", { class: "hint", text: "Click the picture to open it larger." }));
  wrap.append(el("div", { class: "page-grid" }, left, right));
  return wrap;
}

function paintStatus(doc) {
  $("doc-name").textContent = doc.name;
  const active = doc.status === "queued" || doc.status === "reading";
  let text;
  if (doc.status === "queued") text = "Waiting for the other files to finish…";
  else if (doc.status === "reading") {
    text = doc.pages_total
      ? `Reading page ${Math.min(doc.pages_done + 1, doc.pages_total)} of ${doc.pages_total}… This takes about a minute per page. You can keep this window open and add more files.`
      : "Preparing the pages…";
  } else if (doc.status === "done" && !doc.pages.some((p) => p.rows.length)) {
    text = "Finished, but no table could be read from this file. See the message below the picture.";
  } else if (doc.status === "done") {
    text = doc.cells_to_check
      ? `Finished. ${doc.cells_to_check} cell${doc.cells_to_check > 1 ? "s" : ""} to check — highlighted in yellow. Type the correct value, or use Claude's suggestion.`
      : "Finished. Nothing was marked as unsure, but have a look before you rely on it.";
  } else if (doc.error && doc.error.code === "CANCELLED") {
    text = `Cancelled after ${doc.pages_done} of ${doc.pages_total ?? "?"} pages. Nothing more will be read unless you press Continue.`;
  } else text = doc.pages.length ? `Stopped after ${doc.pages_done} of ${doc.pages_total ?? "?"} pages.` : "Stopped.";
  $("doc-status").textContent = text;
  $("cancel").hidden = !active;
  const err = $("doc-error");
  err.className = "banner " + (doc.error && doc.error.code === "CANCELLED" ? "info" : "error");
  err.hidden = !(doc.status === "failed" && doc.error);
  err.textContent = doc.error ? doc.error.message : "";
  $("continue").hidden = !doc.can_continue;
  $("download").disabled = doc.status !== "done" || !doc.pages.some((p) => p.rows.length);
  if (err.hidden === false) {
    const code = doc.error.code;
    if (code === "CLAUDE_LOGIN_REQUIRED" || code === "CLAUDE_CLI_MISSING") refreshClaude();   // top-right box shows Sign in
    if (!doc.can_continue) err.append(" Use “All files” to go back and add a corrected file.");
  }
  $("next-check").hidden = !(doc.cells_to_check > 0);
  $("next-check").textContent = `Go to next cell to check (${doc.cells_to_check})`;
  return active;
}

function showDoc(doc) {
  currentDoc = doc;
  const active = paintStatus(doc);
  // Do not redraw the table while someone is typing in it; the next poll will catch up.
  if (!$("pages").contains(document.activeElement)) $("pages").replaceChildren(...doc.pages.map((p) => buildPage(doc, p)));
  return active;
}

let docTimer = null;
async function openDoc(id) {
  currentId = id; currentDoc = null;
  $("home").hidden = true; $("doc").hidden = false;
  $("pages").replaceChildren(); $("doc-name").textContent = ""; $("doc-status").textContent = "Opening…";
  $("doc-error").hidden = true;
  clearTimeout(docTimer);
  await pollDoc(true);
}

async function pollDoc(first) {
  if (currentId === null) return;
  const id = currentId;
  try {
    const doc = await api("GET", `/api/jobs/${encodeURIComponent(id)}`);
    if (id !== currentId) return;
    const changed = first || !currentDoc || doc.status !== currentDoc.status || doc.pages_done !== currentDoc.pages_done;
    const active = changed ? showDoc(doc) : (doc.status === "queued" || doc.status === "reading");
    if (active) docTimer = setTimeout(() => pollDoc(false), 2500);
  } catch (e) {
    if (id !== currentId) return;
    $("doc-status").textContent = "";
    $("doc-error").hidden = false; $("doc-error").textContent = e.message;
  }
}

function showHome() {
  currentId = null; currentDoc = null; clearTimeout(docTimer);
  $("doc").hidden = true; $("home").hidden = false;
  loadRecent();
}

function route() {
  const m = location.hash.match(/^#\/doc\/(.+)$/);
  if (m) openDoc(decodeURIComponent(m[1])); else showHome();
}

function setupQuit() {
  $("quit").addEventListener("click", async () => {
    let active = 0;
    try { active = (await api("GET", "/api/activity")).active; } catch { /* quit anyway */ }
    const warn = active ? `${active} file${active > 1 ? "s are" : " is"} still being read. They will be stopped, and you can press Continue next time. ` : "";
    if (!confirm(`${warn}Close Table Reader?`)) return;
    try { await api("POST", "/api/quit"); } catch { /* it may already be closing */ }
    document.body.replaceChildren(el("main", {}, el("h2", { text: "Table Reader has closed." }),
      el("p", { text: "You can close this tab. To use it again, open Table Reader from your desktop." })));
  });
}

function setupDocButtons() {
  $("back").addEventListener("click", () => { location.hash = ""; });
  $("cancel").addEventListener("click", async () => {
    try { await api("POST", `/api/jobs/${encodeURIComponent(currentId)}/cancel`); await pollDoc(true); }
    catch (e) { $("doc-error").hidden = false; $("doc-error").textContent = e.message; }
  });
  $("continue").addEventListener("click", async () => {
    try { await api("POST", `/api/jobs/${encodeURIComponent(currentId)}/resume`); await pollDoc(true); }
    catch (e) { $("doc-error").hidden = false; $("doc-error").textContent = e.message; }
  });
  $("download").addEventListener("click", () => {
    if (!currentDoc || currentDoc.status !== "done") return;
    const n = currentDoc.cells_to_check;
    if (n && !confirm(`${n} cell${n > 1 ? "s are" : " is"} still highlighted. In the CSV they will be left blank with a note. Download anyway?`)) return;
    location.href = `/api/jobs/${encodeURIComponent(currentId)}/csv`;
  });
  $("next-check").addEventListener("click", () => {
    const inputs = [...document.querySelectorAll("#pages .cell.flag input")];
    if (!inputs.length) return;
    const after = inputs.findIndex((i) => i === document.activeElement);
    const next = inputs[(after + 1) % inputs.length];
    next.scrollIntoView({ block: "center", behavior: "smooth" });
    next.focus({ preventScroll: true });
  });
}

// Keep the recent-files list live while anything is being read.
setInterval(() => { if (!$("home").hidden) loadRecent(); }, 4000);

setupDrop();
setupDocButtons();
setupQuit();
window.addEventListener("hashchange", route);
refreshClaude();
setInterval(() => { if (!loginTimer) refreshClaude(); }, 60000);
route();
