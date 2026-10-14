"use strict";
// Table Reader page. Plain JS, no build step. All text from the server is inserted with textContent (never innerHTML).
// Text shown to the user goes through t()/tn() (page text) or tm() (server messages) from i18n.js.

const $ = (id) => document.getElementById(id);
const QUALITY = { CLEAR: t("Clear"), MOSTLY_CLEAR: t("Mostly clear"), FADED: t("Faded or small print"), ILLEGIBLE: t("Hard to read") };
let claudeReady = false;
let currentId = null;
let currentDoc = null;

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
    if (data && data.message) throw Object.assign(new Error(tm(data.message)), { code: data.code });   // code: for a screen that acts on it
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

// ------------------------------------------------------------------------------------------------ files and companies
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

function companyNames(jobs) {
  return [...new Set(jobs.map((j) => j.company).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

// The box that files a file under a company. ``done``: called when it closes (saved or not); ``say(text, kind)``:
// where the page shows what happened ("info" / "error").
function companyBox(j, companies, done, say) {
  const input = el("input", { type: "text", list: "company-names", maxlength: "80", value: j.company || suggestCompany(j.name),
    placeholder: t("Company name"), "aria-label": t("Company for {name}", { name: j.name }) });
  const close = () => { editingCompany = null; done(); };
  const save = async () => {
    try {
      const r = await api("PUT", `/api/jobs/${encodeURIComponent(j.id)}/company`, { company: input.value });
      if (r.moved) say(tn(r.moved, "{n} other file starting with “{c}” was put under this company too.", "{n} other files starting with “{c}” were put under this company too.", { c: input.value.trim() }), "info");
    } catch (e) { say(e.message, "error"); }
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

// Does a file's company pass the Company chooser?
function companyMatches(company) {
  return !companyFilter || (companyFilter === NO_COMPANY ? !company : company === companyFilter);
}

// The Company chooser of step 2's list (it filters step 3's list too). Remembered in this browser.
let companySignature = "";
function renderCompanyFilter(jobs, onChange) {
  const companies = companyNames(jobs);
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
    onChange();
  });
  $("company-box").replaceChildren(el("label", {}, t("Company"), sel));
  return companies;
}

// What this tab remembers (sessionStorage): where the user was in each step, the working month, the files added here.
// A private window may refuse it: then nothing is remembered and each step opens on its first screen.
function remember(key, value) { try { sessionStorage.setItem(key, value); } catch (_) { /* refused */ } }
function recall(key) { try { return sessionStorage.getItem(key); } catch (_) { return null; } }
function forget(key) { try { sessionStorage.removeItem(key); } catch (_) { /* refused */ } }

// The number beside a step button (0 hides it).
function stepBadge(step, n) {
  const badge = $(`step-${step}-n`);
  badge.hidden = !n; badge.textContent = n ? String(n) : "";
}

// "2 Check reading": the yellow cells left in the files step 2's list shows (every file until check.js is loaded).
function refreshCheckBadge(jobs) {
  const shown = typeof ckFilter === "function" ? jobs.filter(ckFilter) : jobs;
  stepBadge("check", shown.reduce((n, j) => n + (j.cells_to_check || 0), 0));
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
  // A cell Claude was not sure about: the yellow box shows what Claude saw, and nothing else (the reason is the
  // tooltip). It stays yellow, and unconfirmed, until the user presses Enter in it or types over it. A "?" before or
  // after the marks ("18:50?") is Claude's doubt, not part of the value, so it is not shown; a "?" inside ("1?:50") stays.
  const shown = cell.needs_review ? (cell.raw_text || "").trim().replace(/^\?+|\?+$/g, "").trim() : cell.value ?? "";
  if (cell.needs_review && cell.raw_text && cell.raw_text.trim() !== shown) node.title += " " + t("Claude saw: {x}", { x: cell.raw_text });
  if (document.activeElement !== input) input.value = shown;
  input.dataset.original = shown;
  input.setAttribute("aria-label", cell.needs_review ? t("Cell to check. Press Enter to accept it, or type the correct value.") : t("Cell value"));
  node.querySelector(".tools")?.remove();
  const tools = el("div", { class: "tools" });
  if (cell.edited) {
    tools.append(el("button", { type: "button", text: t("Undo my change"), onclick: () => saveCell(loc, null, node) }));
  }
  if (tools.children.length) node.append(tools);
}

function makeCell(loc, cell) {
  const input = el("input", { type: "text", autocomplete: "off", spellcheck: "false" });
  const node = el("div", {}, input);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      // Enter in a yellow cell accepts what the box shows (an empty box: the cell is empty), also when nothing was typed
      const c = findCell(currentDoc, loc);
      if (c && c.needs_review && input.value.trim() === input.dataset.original) saveCell(loc, input.value.trim(), node);
      input.blur();
    } else if (e.key === "Escape") { input.value = input.dataset.original; input.blur(); }
  });
  input.addEventListener("change", () => {
    const value = input.value.trim();
    const c = findCell(currentDoc, loc);
    if (!c) return;
    if (c.needs_review ? value === input.dataset.original : value === (c.value ?? "")) return;   // nothing typed
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
    el("ul", {}, ...notes.map((n) => el("li", { text: tm(n) })))));

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
      ? tn(doc.cells_to_check, "Finished. {n} cell to check — the yellow box shows what Claude saw. Press Enter in it to accept it, or type the correct value.", "Finished. {n} cells to check — the yellow boxes show what Claude saw. Press Enter in a box to accept it, or type the correct value.")
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
  hideScreens(); $("doc").hidden = false;
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

setupDocButtons();
setupQuit();
refreshClaude();
setInterval(() => { if (!loginTimer) refreshClaude(); }, 60000);
