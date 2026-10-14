"use strict";
// Step 2, Check reading: the list of files (left) and the chosen file (right): its company, what it needs from the user
// in the working month ("This file needs you": whose card, which month, an unknown card layout, no company, set aside),
// Claude's reading beside the picture with its yellow cells, and the buttons on to the next file and to step 3.
// Claude's reading is never changed here: Enter or typing in a cell saves a correction (edits.json).
// Loaded after app.js and paycommon.js; columns.js (the column choice opened under a file) and steps.js come after.

const QUALITY = { CLEAR: t("Clear"), MOSTLY_CLEAR: t("Mostly clear"), FADED: t("Faded or small print"), ILLEGIBLE: t("Hard to read") };
let currentId = null;        // the file shown
let currentDoc = null;       // what the server last sent for it
let ckJobs = null;           // GET /api/jobs, newest first
let ckFiles = null;          // GET /api/payroll/<working month>/files (null with "All months")
let ckAll = recall("checkAll") === "1";

// ------------------------------------------------------------------------------------------------ the file
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
    const j = ckJobs && ckJobs.find((x) => x.id === doc.id);       // the list's count follows
    if (j) { j.cells_to_check = doc.cells_to_check; ckDrawList(); ckDrawFoot(j); }
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
    if (!doc.can_continue) err.append(t(" Go to step 1 to add a corrected file."));
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
  $("doc").hidden = false;
  $("pages").replaceChildren(); $("doc-name").textContent = ""; $("doc-status").textContent = t("Opening…");
  $("doc-error").hidden = true; $("ck-needs").hidden = true; $("ck-foot").replaceChildren(); $("ck-company").replaceChildren();
  clearTimeout(docTimer);
  ckDrawList();                                  // the chosen file is marked in the list
  await pollDoc(true);
}

async function pollDoc(first) {
  if (currentId === null || $("check").hidden) return;
  const id = currentId;
  try {
    const doc = await api("GET", `/api/jobs/${encodeURIComponent(id)}`);
    if (id !== currentId) return;
    const finished = currentDoc && currentDoc.status !== "done" && doc.status === "done";
    const changed = first || !currentDoc || doc.status !== currentDoc.status || doc.pages_done !== currentDoc.pages_done;
    const active = changed ? showDoc(doc) : ckBusy(doc);
    if (finished) await ckLoad();                // its problems in the month are known now
    if (changed) ckDrawFile();
    if (active) docTimer = setTimeout(() => pollDoc(false), 2500);
  } catch (e) {
    if (id !== currentId) return;
    $("doc-status").textContent = "";
    $("doc-error").hidden = false; $("doc-error").textContent = e.message;
  }
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

// ------------------------------------------------------------------------------------------------ the list
function ckError(message, kind = "error") {
  $("ck-error").hidden = !message; $("ck-error").textContent = message || "";
  $("ck-error").className = `banner ${kind}`;
}
function ckBusy(j) { return j.status === "queued" || j.status === "reading"; }
function ckItems(id) { return (!ckAll && ckFiles && ckFiles.files[id]) || []; }

// Does step 2's list show this file? Every file of the chosen company with "All months"; otherwise a file still being
// read or stopped, a file of the month, a file with something to settle in it, and a file on one of its employees.
function ckFilter(j) {
  if (!companyMatches(j.company)) return false;
  if (ckAll || j.status !== "done" || !ckFiles) return true;
  return ckFiles.months[j.id] === ckFiles.month || j.id in ckFiles.files || j.id in ckFiles.employees;
}

function ckNeeds(j) {
  return j.status === "done" && (j.cells_to_check > 0 || ckItems(j.id).some((i) => i.kind !== "other"));
}

function ckState(j) {
  const cancelled = j.status === "failed" && j.error && j.error.code === "CANCELLED";
  if (j.status !== "done") return { text: cancelled ? t("Cancelled") : progressText(j), cls: j.status === "failed" && !cancelled ? "pill bad" : "pill" };
  const items = ckItems(j.id);
  const parts = [];
  if (j.cells_to_check) parts.push(tn(j.cells_to_check, "{n} yellow", "{n} yellow"));
  if (items.some((i) => i.kind !== "other")) parts.push(t("! Needs you"));
  else if (items.length) parts.push(t("Not in this month"));
  return parts.length ? { text: parts.join(" · "), cls: "pill check" } : { text: "✓", cls: "pill good" };
}

// The list (and, for one month, its files' problems) from the server.
async function ckLoad() {
  try {
    const month = workMonth();
    const [jobs, files] = await Promise.all([api("GET", "/api/jobs"),
      ckAll ? Promise.resolve(null) : api("GET", `/api/payroll/${month}/files`)]);
    ckJobs = jobs; ckFiles = files;
    if (files) stepBadge("payroll", files.needs);
    ckError("");
  } catch (e) { ckError(e.message); ckJobs = ckJobs || []; }
  ckDrawList();
}

function ckDrawMonth() {
  const base = defaultPayrollMonth();
  const months = [shiftMonth(base, 1), ...Array.from({ length: 12 }, (_, k) => shiftMonth(base, -k))];
  if (!months.includes(workMonth())) months.unshift(workMonth());
  $("ck-month").replaceChildren(el("option", { value: "all", text: t("All months"), selected: ckAll }),
    ...months.map((m) => el("option", { value: m, text: monthTitle(m), selected: !ckAll && m === workMonth() })));
}

function ckDrawList() {
  ckDrawMonth();
  renderCompanyFilter(ckJobs, () => { ckDrawList(); if (currentId) ckDrawFile(); });
  const shown = ckJobs.filter(ckFilter);
  $("ck-files").replaceChildren(...shown.map((j) => {
    const s = ckState(j);
    return el("li", {}, el("button", { type: "button", class: "side-item" + (j.id === currentId ? " on" : ""),
      onclick: () => { location.hash = `#/check/${encodeURIComponent(j.id)}`; } },
    el("span", { class: "name" }, el("strong", { text: j.name }), el("small", { text: j.company || t("No company yet") })),
    el("span", { class: s.cls, text: s.text })));
  }));
  refreshCheckBadge(ckJobs);
}

async function showCheck(id, columns) {
  const stale = !ckJobs || (!ckAll && (!ckFiles || ckFiles.month !== workMonth())) || (id && !ckJobs.some((j) => j.id === id));
  if (stale) await ckLoad(); else ckDrawList();
  $("ck-empty").hidden = true;
  if (!id) {                                       // no file in the address: the first that needs the user, else the first
    const shown = ckJobs.filter(ckFilter);
    const first = shown.find(ckNeeds) || shown[0];
    if (first) location.replace(`#/check/${encodeURIComponent(first.id)}`); else ckShowEmpty();
    return;
  }
  if (!ckJobs.some((j) => j.id === id)) { forget("place.check"); location.replace("#/check"); return; }
  if (id !== currentId || !currentDoc) await openDoc(id); else ckDrawFile();
  if (columns) showLayout(id, columns.page, columns.hours); else $("layout").hidden = true;
}

function ckShowEmpty() {
  currentId = null; currentDoc = null; clearTimeout(docTimer);
  $("doc").hidden = true; $("ck-empty").hidden = false;
  $("ck-empty-text").textContent = !ckJobs.length ? t("Nothing here yet. Add files in step 1.")
    : !ckJobs.some((j) => companyMatches(j.company)) ? t("No files for this company. Choose “All companies” to see every file.")
      : t("No files for {month}. Choose “All months” to see every file.", { month: monthTitle(workMonth()) });
}

// The file's company, what it needs in the month, and the buttons on.
function ckDrawFile() {
  const j = ckJobs && ckJobs.find((x) => x.id === currentId);
  if (!j || !currentDoc) return;
  if (editingCompany !== j.id) {
    $("ck-company").replaceChildren(el("button", { type: "button", class: j.company ? "company" : "company unset",
      text: j.company || t("Set company"), title: j.company ? t("Click to change the company") : t("Choose the client company of this file"),
      onclick: () => {
        editingCompany = j.id;
        $("ck-company").append(companyBox(j, companyNames(ckJobs), async () => { await ckLoad(); ckDrawFile(); }, ckError));
      } }));
  }
  const items = ckItems(j.id);
  $("ck-needs").hidden = !items.length || j.status !== "done";
  $("ck-needs").replaceChildren(
    el("h3", { text: items.some((i) => i.kind !== "other") ? t("This file needs you") : t("Not in this month's payroll") }),
    el("ol", { class: "needs" }, ...items.map(fileItemNode)));
  ckDrawFoot(j);
}

function ckDrawFoot(j) {
  const shown = ckJobs.filter(ckFilter);
  const at = shown.findIndex((x) => x.id === j.id);
  const next = [...shown.slice(at + 1), ...shown.slice(0, Math.max(at, 0))].find(ckNeeds);
  const month = workMonth();
  const people = (!ckAll && ckFiles && ckFiles.employees[j.id]) || [];
  $("ck-foot").replaceChildren(
    el("button", { type: "button", text: next ? t("Next file with yellow cells →") : t("No other file needs checking"),
      disabled: !next, onclick: () => { location.hash = `#/check/${encodeURIComponent(next.id)}`; } }),
    ...people.map((p) => el("button", { type: "button", text: t("See {name} in payroll →", { name: p.name || t("An employee") }),
      onclick: () => { location.hash = `#/payroll/${month}/e/${encodeURIComponent(p.id)}`; } })),
    el("button", { type: "button", class: "primary", text: t("Go to payroll for {month} →", { month: monthTitle(month) }),
      onclick: () => { location.hash = `#/payroll/${month}`; } }));
}

// Do something about the file, then draw the list and the file again from the server.
async function ckAct(button, action) {
  button.disabled = true;
  try { await action(); ckError(""); await ckLoad(); ckDrawFile(); }
  catch (e) { ckError(e.message); button.disabled = false; }
}

// One thing the file needs (wording and buttons as on the company screen before the three steps).
function fileItemNode(item) {
  const buttons = [];
  let head = "", details = [];
  const month = ckFiles.month;
  if (item.kind === "unplaced") {
    head = t("{file}: whose card is this?", { file: item.name });
    if (!item.readable) details = [t("Table Reader cannot work out the days from this file yet; the figures will have to be typed.")];
    const place = (button, employee) => ckAct(button, () => api("POST", `/api/payroll/${month}/place`, { ref: item.ref, employee }));
    for (const e of ckFiles.choices[item.company] || []) {
      const b = el("button", { type: "button", text: e.name || e.emp_no || t("An employee") });
      b.addEventListener("click", () => place(b, e.id));
      buttons.push(b);
    }
    const fresh = el("button", { type: "button", text: t("New employee") });
    fresh.addEventListener("click", () => place(fresh, null));
    buttons.push(fresh);
    if (item.ref === item.doc) {                 // a whole file that is nobody's card (a notice, a second scan)
      const none = el("button", { type: "button", text: t("Not a time card") });
      none.addEventListener("click", () => ckAct(none, () => api("POST", "/api/payroll/file-month", { id: item.doc, month: "none" })));
      buttons.push(none);
    }
  } else if (item.kind === "layout") {
    head = item.confirmed ? t("{file}: the days cannot be worked out with the saved card layout", { file: item.name })
      : t("{file}: a card layout Table Reader does not know", { file: item.name });
    details = [item.confirmed ? t("Say which column holds the date and which the hours or times.")
      : t("Columns with figures that are not used: {list}. Say once what they mean; it is kept for every card with the same headings.",
        { list: item.columns.join(", ") })];
    const hours = item.hours_column ? `/h/${encodeURIComponent(item.hours_column)}` : "";
    buttons.push(el("button", { type: "button", class: "primary", text: t("Check the columns"),
      onclick: () => { location.hash = `#/check/${encodeURIComponent(item.doc)}/columns/${item.page}${hours}`; } }));
    if (!item.confirmed) {
      const asIs = el("button", { type: "button", text: t("It is right as it is") });
      asIs.addEventListener("click", () => ckAct(asIs, () => api("PUT", "/api/layouts",
        { doc: item.doc, page: item.page, as_is: true, hours_column: item.hours_column })));
      buttons.push(asIs);
    }
  } else if (item.kind === "month") {
    head = t("{file}: which month is this for?", { file: item.name });
    details = [tm(item.why)];
    const here = el("button", { type: "button", text: t("It is for {month}", { month: monthTitle(month) }) });
    here.addEventListener("click", () => ckAct(here, () => api("POST", "/api/payroll/file-month", { id: item.doc, month })));
    const none = el("button", { type: "button", text: t("Not a time card") });
    none.addEventListener("click", () => ckAct(none, () => api("POST", "/api/payroll/file-month", { id: item.doc, month: "none" })));
    buttons.push(here, none);
  } else if (item.kind === "other") {
    head = item.name;
    details = [item.month === "none" ? t("Set aside as not a time card.") : t("Read as a file of {month}.", { month: monthTitle(item.month) })];
    const here = el("button", { type: "button", text: t("It is for {month}", { month: monthTitle(month) }) });
    here.addEventListener("click", () => ckAct(here, () => api("POST", "/api/payroll/file-month", { id: item.doc, month })));
    buttons.push(here);
  } else if (item.kind === "company") {
    head = t("{file}: which company is this for?", { file: item.name });
    const input = el("input", { type: "text", maxlength: "80", placeholder: t("Company name"), value: suggestCompany(item.name),
      "aria-label": t("Company for {name}", { name: item.name }) });
    const save = el("button", { type: "button", class: "primary", text: t("Save") });
    save.addEventListener("click", () => ckAct(save, async () => {
      if (!input.value.trim()) throw new Error(t("Type the company's name first."));
      await api("PUT", `/api/jobs/${encodeURIComponent(item.doc)}/company`, { company: input.value });
    }));
    buttons.push(input, save);
  }
  return el("li", { class: "need" }, el("strong", { text: head }),
    ...details.map((d) => el("p", { class: "legend", text: d })), el("div", { class: "need-buttons" }, ...buttons));
}

// Another month (or all of them): the list again, and the file shown stays only if the new list has it.
$("ck-month").addEventListener("change", async () => {
  ckAll = $("ck-month").value === "all";
  remember("checkAll", ckAll ? "1" : "");
  if (!ckAll) setWorkMonth($("ck-month").value);
  ckFiles = null;
  await ckLoad();
  const j = currentId && ckJobs.find((x) => x.id === currentId);
  if (j && ckFilter(j)) ckDrawFile();
  else if (location.hash === "#/check") showCheck(null, null);
  else location.hash = "#/check";
});
$("ck-to-upload").addEventListener("click", () => { location.hash = "#/"; });

// The list follows the files being read; a file that finishes or is added (here, in another tab, in the Inbox folder)
// fetches the month's problems again too.
setInterval(async () => {
  if ($("check").hidden || editingCompany || !ckJobs) return;
  let jobs;
  try { jobs = await api("GET", "/api/jobs"); } catch (_) { return; }
  const finished = (list) => list.filter((j) => j.status === "done").map((j) => j.id).sort().join("|");
  if (jobs.length !== ckJobs.length || finished(jobs) !== finished(ckJobs)) { await ckLoad(); if (currentId) ckDrawFile(); }
  else if (jobs.some(ckBusy) || ckJobs.some(ckBusy)) { ckJobs = jobs; ckDrawList(); }
}, 4000);

setupDocButtons();
