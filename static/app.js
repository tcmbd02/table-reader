"use strict";
// Table Reader page. Plain JS, no build step. All text from the server is inserted with textContent (never innerHTML).
// Text shown to the user goes through t()/tn() (page text) or tm() (server messages) from i18n.js.

const $ = (id) => document.getElementById(id);
const QUALITY = { CLEAR: t("Clear"), MOSTLY_CLEAR: t("Mostly clear"), FADED: t("Faded or small print"), ILLEGIBLE: t("Hard to read") };
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
  catch { throw new Error(t("Table Reader is not running any more. Close this tab and open Table Reader again.")); }
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    if (data && data.message) throw new Error(tm(data.message));
    if (res.status === 404 || res.status === 405) {
      throw new Error(t("Table Reader was updated while it was open. Close its window, open Table Reader again, then reload this page."));
    }
    throw new Error(t("Something went wrong. Reload the page and try again."));
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
    box.replaceChildren(el("span", { class: "ok", text: t("✓ Claude connected") }),
      el("span", { class: "muted", text: `${s.email || ""}${plan}` }));
  } else {
    const kids = [el("span", { class: "problem", text: tm(s.message) || t("Claude is not connected.") })];
    if (s.installed) kids.push(el("button", { class: "primary", text: t("Sign in"), onclick: startLogin }));
    box.replaceChildren(...kids);
  }
  updateDropState();
}

async function startLogin() {
  try { await api("POST", "/api/login"); }
  catch (e) { $("claude-box").replaceChildren(el("span", { class: "problem", text: e.message })); return; }
  $("claude-box").replaceChildren(el("span", { text: t("Finish signing in in the browser window that just opened…") }));
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
  $("upload-messages").replaceChildren(...items.map((m) => el("div", { class: `banner ${kind}`, text: m })));
}

async function upload(fileList) {
  const files = [...fileList];
  if (!files.length || uploading) return;
  if (!claudeReady) { showMessages([t("Connect your Claude account first (top right), then add your files.")], "error"); return; }
  uploading = true; updateDropState();
  showMessages([tn(files.length, "Adding {n} file…", "Adding {n} files…")], "info");
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));
  try {
    const r = await api("POST", "/api/jobs", form);
    showMessages(r.rejected.map((x) => tm(x.message)), "error");
    if (r.created.length === 1 && !r.rejected.length) { location.hash = `#/doc/${encodeURIComponent(r.created[0].id)}`; }
  } catch (e) { showMessages([e.message], "error"); }
  uploading = false; updateDropState();
  loadRecent();
}

function setupDrop() {
  const drop = $("drop"), input = $("file-input");
  drop.addEventListener("click", () => {
    if (!claudeReady) showMessages([t("Connect your Claude account first (top right), then add your files.")], "error");
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
  if (j.status === "queued") return t("Waiting…");
  if (j.status === "reading") return j.pages_total ? t("Reading page {a} of {b}…", { a: Math.min(j.pages_done + 1, j.pages_total), b: j.pages_total }) : t("Preparing…");
  if (j.status === "done") return t("Finished");
  return t("Stopped");
}

// --- client companies: each file is filed under a company the user confirmed once; the list can be filtered by it
const NO_COMPANY = "\u0000none";
const MONTH_WORD = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?$/i;
let companyFilter = "";       // "" = all companies
let editingCompany = null;    // id of the file whose company box is open (the list is not redrawn meanwhile)
try { companyFilter = localStorage.getItem("companyFilter") || ""; } catch (_) { /* private window */ }

// Only a suggestion to start the box with: "MAJU JAYA ALI SEPT 26" -> "MAJU JAYA" (month, year and the worker's
// name taken off). The user checks it before it is saved.
function suggestCompany(name) {
  const words = name.replace(/\.[a-z0-9]{2,4}$/i, "").replace(/_/g, " ").trim().split(/\s+/);
  if (words.length && /^\d{2,4}$/.test(words[words.length - 1])) words.pop();
  if (!(words.length && MONTH_WORD.test(words[words.length - 1]))) return "";
  words.pop();
  return words.length >= 2 ? words.slice(0, -1).join(" ") : "";
}

function companyBox(j, companies) {
  const input = el("input", { type: "text", list: "company-names", maxlength: "80", value: j.company || suggestCompany(j.name),
    placeholder: t("Company name"), "aria-label": t("Company for {name}", { name: j.name }) });
  const close = () => { editingCompany = null; loadRecent(); };
  const save = async () => {
    try {
      const r = await api("PUT", `/api/jobs/${encodeURIComponent(j.id)}/company`, { company: input.value });
      if (r.moved) showMessages([tn(r.moved, "{n} other file starting with “{c}” was put under this company too.", "{n} other files starting with “{c}” were put under this company too.", { c: input.value.trim() })], "info");
    } catch (e) { showMessages([e.message], "error"); }
    close();
  };
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") save(); if (ev.key === "Escape") close(); });
  setTimeout(() => { input.focus(); input.select(); });
  return el("div", { class: "company-edit" },
    el("label", { text: t("Company") }), input,
    el("button", { class: "primary", text: t("Save"), onclick: save }), el("button", { text: t("Cancel"), onclick: close }),
    el("span", { class: "muted", text: t("Check the name. Other files that start with it will go under it too.") }),
    el("datalist", { id: "company-names" }, ...companies.map((c) => el("option", { value: c }))));
}

// Does a file's / employee's company pass the Company chosen in the top bar?
function companyMatches(company) {
  return !companyFilter || (companyFilter === NO_COMPANY ? !company : company === companyFilter);
}

// The Company chooser in the top bar. It filters Recent files and the Payroll screen, and is remembered.
let companySignature = "";
function renderCompanyFilter(jobs) {
  const companies = [...new Set(jobs.map((j) => j.company).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const count = (c) => jobs.filter((j) => (c === NO_COMPANY ? !j.company : j.company === c)).length;
  if (companyFilter && companyFilter !== NO_COMPANY && !companies.includes(companyFilter)) companyFilter = "";
  const none = count(NO_COMPANY);
  const options = [["", t("All companies ({n})", { n: jobs.length })], ...companies.map((c) => [c, `${c} (${count(c)})`]),
    ...(none ? [[NO_COMPANY, t("No company yet ({n})", { n: none })]] : [])];
  const signature = JSON.stringify([options, companyFilter]);
  $("company-box").hidden = jobs.length === 0;
  if (signature === companySignature) return companies;          // unchanged: do not close an open list
  companySignature = signature;
  const sel = el("select", { id: "company-filter", "aria-label": t("Show files of") },
    ...options.map(([value, text]) => el("option", { value, text, selected: value === companyFilter })));
  sel.addEventListener("change", () => {
    companyFilter = sel.value;
    companySignature = JSON.stringify([options, companyFilter]);
    try { localStorage.setItem("companyFilter", companyFilter); } catch (_) { /* private window */ }
    if (!$("home").hidden) loadRecent();
    else if (!$("payroll").hidden && typeof payrollCompanyChanged === "function") payrollCompanyChanged();
  });
  $("company-box").replaceChildren(el("label", {}, t("Company"), sel));
  return companies;
}

async function refreshCompanies() {
  try { renderCompanyFilter(await api("GET", "/api/jobs")); } catch (_) { /* shown elsewhere */ }
}

async function loadRecent() {
  if (editingCompany) return;
  let jobs;
  try { jobs = await api("GET", "/api/jobs"); } catch (e) { showMessages([e.message], "error"); return; }
  const companies = renderCompanyFilter(jobs);
  const shown = jobs.filter((j) => companyMatches(j.company));
  const list = $("recent");
  list.replaceChildren(...shown.map((j) => {
    const cancelled = j.status === "failed" && j.error && j.error.code === "CANCELLED";
    const active = j.status === "queued" || j.status === "reading";
    const cls = j.status === "done" ? "pill good" : j.status === "failed" && !cancelled ? "pill bad" : "pill";
    const li = el("li", {},
      el("span", { class: "name", text: j.name }),
      el("button", { class: j.company ? "company" : "company unset", text: j.company || t("Set company"),
        title: j.company ? t("Click to change the company") : t("Choose the client company of this file"),
        onclick: () => { editingCompany = j.id; drawCompanyEditor(j, companies); } }),
      el("span", { class: "when", text: new Date(j.created).toLocaleString(LOCALE) }),
      el("span", { class: cls, text: cancelled ? t("Cancelled") : progressText(j) }),
      active && el("button", { text: t("Cancel"), onclick: async () => {
        try { await api("POST", `/api/jobs/${encodeURIComponent(j.id)}/cancel`); } catch (e) { showMessages([e.message], "error"); }
        loadRecent();
      } }),
      el("button", { text: t("Open"), onclick: () => { location.hash = `#/doc/${encodeURIComponent(j.id)}`; } }));
    if (j.status === "failed" && j.error && !cancelled) li.append(el("div", { class: "muted", style: "flex-basis:100%", text: tm(j.error.message) }));
    li.dataset.id = j.id;
    return li;
  }));
  $("recent-empty").hidden = jobs.length > 0;
  $("recent-none").hidden = !(jobs.length > 0 && shown.length === 0);
  return jobs;
}

function drawCompanyEditor(j, companies) {
  document.querySelectorAll(".company-edit").forEach((n) => n.remove());
  const li = [...$("recent").children].find((n) => n.dataset.id === j.id);
  if (li) li.append(companyBox(j, companies));
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
  node.title = cell.needs_review ? (tm(cell.unclear_reason) || t("Claude was not sure about this cell.")) : "";
  const input = node.querySelector("input");
  if (document.activeElement !== input) input.value = cell.value ?? "";
  input.dataset.original = cell.value ?? "";
  input.setAttribute("aria-label", cell.needs_review ? t("Cell to check. Type the correct value.") : t("Cell value"));
  node.querySelector(".tools")?.remove();
  const tools = el("div", { class: "tools" });
  if (cell.needs_review) {
    tools.append(el("span", { class: "reason", text: tm(cell.unclear_reason) || t("Please check this cell.") }));
    if (cell.raw_text) {
      tools.append(el("span", { class: "seen", text: t("Claude saw: {x}", { x: cell.raw_text }) }),
        el("button", { type: "button", text: t("Use this"), onclick: () => saveCell(loc, cell.raw_text.trim(), node) }));
    }
    tools.append(el("button", { type: "button", text: t("It's empty"), onclick: () => saveCell(loc, "", node) }));
  } else if (cell.edited) {
    tools.append(el("button", { type: "button", text: t("Undo my change"), onclick: () => saveCell(loc, null, node) }));
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
  if (doc.pages_total > 1) wrap.append(el("h3", { text: t("Page {a} of {b}", { a: page.page, b: doc.pages_total }) }));

  const notes = [];
  if (page.quality !== "CLEAR") notes.push(t("Picture quality: {q}. Check the highlighted cells carefully.", { q: QUALITY[page.quality] || page.quality }));
  notes.push(...page.notes);
  const right = el("div");
  if (notes.length) right.append(el("div", { class: "notes" }, el("strong", { text: t("Claude's notes") }),
    el("ul", {}, ...notes.map((n) => el("li", { text: n })))));

  if (page.header_fields.length) {
    right.append(el("div", { class: "fields" }, ...page.header_fields.map((f, i) =>
      el("div", { class: "field" }, el("label", { text: f.label }), makeCell({ page: page.page, header: i }, f.cell)))));
  }
  if (!page.rows.length) {
    right.append(el("div", { class: "banner error", text: tm(page.problem) || t("No table was found on this page.") }));
  } else {
    const head = el("tr", {}, el("th", { text: "#" }), ...page.column_labels.map((c) => el("th", { text: c })));
    const body = page.rows.map((row, r) => el("tr", {}, el("td", { class: "rownum", text: String(r + 1) }),
      ...page.column_labels.map((col) => el("td", {}, makeCell({ page: page.page, row: r, column: col }, row.cells[col])))));
    right.append(el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, head), el("tbody", {}, ...body))));
  }

  const src = `/api/jobs/${encodeURIComponent(doc.id)}/pages/${page.page}`;
  const left = el("div", { class: "page-image" },
    el("a", { href: src, target: "_blank", rel: "noopener" }, el("img", { src, alt: t("Original, page {n}", { n: page.page }) })),
    el("p", { class: "hint", text: t("Click the picture to open it larger.") }));
  wrap.append(el("div", { class: "page-grid" }, left, right));
  return wrap;
}

function paintStatus(doc) {
  $("doc-name").textContent = doc.name;
  const active = doc.status === "queued" || doc.status === "reading";
  let text;
  if (doc.status === "queued") text = t("Waiting for the other files to finish…");
  else if (doc.status === "reading") {
    text = doc.pages_total
      ? t("Reading page {a} of {b}… This takes about a minute per page. You can keep this window open and add more files.", { a: Math.min(doc.pages_done + 1, doc.pages_total), b: doc.pages_total })
      : t("Preparing the pages…");
  } else if (doc.status === "done" && !doc.pages.some((p) => p.rows.length)) {
    text = t("Finished, but no table could be read from this file. See the message below the picture.");
  } else if (doc.status === "done") {
    text = doc.cells_to_check
      ? tn(doc.cells_to_check, "Finished. {n} cell to check — highlighted in yellow. Type the correct value, or use Claude's suggestion.", "Finished. {n} cells to check — highlighted in yellow. Type the correct value, or use Claude's suggestion.")
      : t("Finished. Nothing was marked as unsure, but have a look before you rely on it.");
  } else if (doc.error && doc.error.code === "CANCELLED") {
    text = t("Cancelled after {a} of {b} pages. Nothing more will be read unless you press Continue.", { a: doc.pages_done, b: doc.pages_total ?? "?" });
  } else text = doc.pages.length ? t("Stopped after {a} of {b} pages.", { a: doc.pages_done, b: doc.pages_total ?? "?" }) : t("Stopped.");
  $("doc-status").textContent = text;
  $("cancel").hidden = !active;
  const err = $("doc-error");
  err.className = "banner " + (doc.error && doc.error.code === "CANCELLED" ? "info" : "error");
  err.hidden = !(doc.status === "failed" && doc.error);
  err.textContent = doc.error ? tm(doc.error.message) : "";
  $("continue").hidden = !doc.can_continue;
  $("download").disabled = doc.status !== "done" || !doc.pages.some((p) => p.rows.length);
  if (err.hidden === false) {
    const code = doc.error.code;
    if (code === "CLAUDE_LOGIN_REQUIRED" || code === "CLAUDE_CLI_MISSING") refreshClaude();   // top-right box shows Sign in
    if (!doc.can_continue) err.append(t(" Use “All files” to go back and add a corrected file."));
  }
  $("next-check").hidden = !(doc.cells_to_check > 0);
  $("next-check").textContent = t("Go to next cell to check ({n})", { n: doc.cells_to_check });
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
  $("home").hidden = true; $("payroll").hidden = true; $("doc").hidden = false;
  $("pages").replaceChildren(); $("doc-name").textContent = ""; $("doc-status").textContent = t("Opening…");
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
  $("doc").hidden = true; $("payroll").hidden = true; $("home").hidden = false;
  loadRecent();
}

function route() {
  refreshCompanies();                                          // the Company chooser is on every screen
  const m = location.hash.match(/^#\/doc\/(.+)$/);
  const pm = location.hash.match(/^#\/payroll(?:\/(\d{4}-\d{2}))?$/);
  if (m) openDoc(decodeURIComponent(m[1]));
  else if (pm && typeof showPayroll === "function") showPayroll(pm[1]);
  else showHome();
}

function setupQuit() {
  $("quit").addEventListener("click", async () => {
    let active = 0;
    try { active = (await api("GET", "/api/activity")).active; } catch { /* quit anyway */ }
    const warn = active ? tn(active, "{n} file is still being read. They will be stopped, and you can press Continue next time. ", "{n} files are still being read. They will be stopped, and you can press Continue next time. ") : "";
    if (!confirm(warn + t("Close Table Reader?"))) return;
    try { await api("POST", "/api/quit"); } catch { /* it may already be closing */ }
    document.body.replaceChildren(el("main", {}, el("h2", { text: t("Table Reader has closed.") }),
      el("p", { text: t("You can close this tab. To use it again, open Table Reader from your desktop.") })));
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
    if (n && !confirm(tn(n, "{n} cell is still highlighted. In the CSV they will be left blank with a note. Download anyway?", "{n} cells are still highlighted. In the CSV they will be left blank with a note. Download anyway?"))) return;
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
