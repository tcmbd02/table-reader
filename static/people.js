"use strict";
// Step 3, Payroll: the month bar (‹ ›, Month settings, Million's employee list, payroll CSV, the month's Million file),
// the list of the month's companies and employees (left), and the company or employee chosen (right).
// What the list says comes from GET /api/payroll/<month>/people; the employee view (employee.js), the Look panel
// (look.js), the pay table (paytable.js) and the settings (settings.js) draw inside this page.
// Loaded after check.js and paycommon.js; uses their helpers.

let moMonth = null;          // the month shown ("2026-09")
let ppView = null;           // what the server last sent (GET /people)
let ppSel = { employee: null, look: false, company: null };
let coCompany = null;        // the company whose panel is open
let coView = null;           // its row of ppView
let ppChain = Promise.resolve();
let ppTimer = null;

function companyHash(month, company) { return `#/payroll/${month}/c/${encodeURIComponent(company)}`; }
function employeeHash(month, id) { return `#/payroll/${month}/e/${encodeURIComponent(id)}`; }
function moError(message) { $("mo-error").hidden = !message; $("mo-error").textContent = message || ""; }
function coError(message) { $("co-error").hidden = !message; $("co-error").textContent = message || ""; }

function statusText(row) {
  if (row.status === "none") return t("No files yet");
  if (row.status === "needs") return tn(row.needs, "Needs you: {n} thing", "Needs you: {n} things");
  if (row.status === "million") return tn(row.waiting, "Ready, {n} waiting for Million", "Ready, {n} waiting for Million");
  return t("Ready");
}

function companyStatus(r) {
  const parts = [r.status === "none" && r.files_needing ? "" : statusText(r)];
  if (r.files_needing) parts.push(tn(r.files_needing, "{n} file needs you in step 2", "{n} files need you in step 2"));
  if (r.own) parts.push(t("own settings"));
  return parts.filter(Boolean).join(" · ");
}

// A company's line in the list: its status as an icon and a number (the words are the tooltip).
function companyMarks(r) {
  const mark = r.status === "needs" ? [icon("alert-triangle"), ` ${r.needs}`] : r.status === "million" ? [icon("clock-pause")]
    : r.status === "none" ? [] : [icon("circle-check")];
  const step2 = r.files_needing ? [` · ${tn(r.files_needing, "{n} file in step 2", "{n} files in step 2")}`] : [];
  return el("small", { class: `marks ${r.status}`, title: companyStatus(r) }, ...mark, ...step2);
}

function everyone() { return ppView ? ppView.companies.flatMap((r) => r.employees) : []; }

// ``entering``: step 3 was not on the screen just before (the month is asked again, and its notes are taken).
async function showPeople(month, sel, entering = false) {
  const other = month !== moMonth;
  moMonth = month; ppSel = sel;
  $("mo-title").textContent = t("Payroll {month}", { month: monthTitle(moMonth) });
  bellDraw(month);
  if (other || entering) takeMonthNotes(month).forEach((n) => bellAdd(month, noteMessage(n)));   // what step 2 kept for it
  moError("");
  const fresh = entering || !ppView || ppView.month !== month;
  if (fresh) await ppLoad();
  else { ppDraw(); ppRefreshSoon(); }
  await ppShowSelection(fresh);
}

// The month from the server again (one request after the other, so an older answer never draws over a newer one).
function ppLoad() {
  const month = moMonth;
  ppChain = ppChain.then(async () => {
    if (month !== moMonth) return;
    try {
      const view = await api("GET", `/api/payroll/${month}/people`);
      if (month !== moMonth) return;
      if (view.added_by_themselves || view.numbered) bellAdd(month, noteMessage({ added: view.added_by_themselves, numbered: view.numbered }));
      ppView = view; ppDraw();
    } catch (e) { moError(e.message); }
  });
  return ppChain;
}
function ppRefreshSoon() { clearTimeout(ppTimer); ppTimer = setTimeout(() => ppLoad(), 800); }
function loadCompany() { return ppLoad(); }          // settings.js and paytable.js say this after a change

function ppDraw() {
  if (!ppView) return;
  const v = ppView;
  const toFix = everyone().filter((e) => e.status === "needs").length;
  $("mo-total").replaceChildren(
    el("span", { class: "stat good" }, icon("circle-check"), " ", t("{n} ready", { n: v.ready_employees })),
    el("span", { class: "stat check" }, icon("alert-triangle"), " ", t("{n} to fix", { n: toFix })),
    v.files_needing ? el("button", { type: "button", class: "link",
      text: tn(v.files_needing, "{n} file needs you in step 2 →", "{n} files need you in step 2 →"),
      onclick: () => toFileProblems() }) : "");
  $("mo-export-open").disabled = !v.employees;
  // not checked against Million's own list: a dot on the button that imports it, the sentence as its tooltip
  $("mo-million-import").querySelector(".warn-dot")?.remove();
  if (!v.checked_with_million) {
    $("mo-million-import").append(el("span", { class: "warn-dot", "aria-hidden": "true",
      title: t("The Employee Nos. are not being checked against Million: import Million's employee list.") }));
  }
  stepBadge("payroll", v.companies.reduce((n, r) => n + r.needs, 0));
  ppDrawList();
  if (!$("company").hidden) drawCompany();
  if (!$("employee").hidden) { ppDrawEmployeeNeeds(); ppDrawWalk(); }
}

// The companies the list shows (Company chooser of step 2, search box), each with its employees that match.
function ppRows() {
  const q = $("pp-search").value.trim().toLowerCase();
  return ppView.companies.filter((r) => companyMatches(r.company))
    .map((r) => ({ ...r, shown: r.employees.filter((e) => !q || `${e.emp_no} ${e.name}`.toLowerCase().includes(q)) }))
    .filter((r) => !q || r.shown.length || r.company.toLowerCase().includes(q));
}
function ppOrder() { return ppRows().flatMap((r) => r.shown); }

function ppDrawList() {
  const rows = ppRows();
  $("pp-list").replaceChildren(...rows.map((r) => el("div", { class: "pp-company" },
    el("button", { type: "button", class: "side-head" + (ppSel.company === r.company && !ppSel.employee ? " on" : ""),
      onclick: () => { location.hash = companyHash(moMonth, r.company); } },
    el("strong", { text: r.company || t("(no company)") }), companyMarks(r)),
    el("ul", { class: "side-list" }, ...r.shown.map((e) => el("li", {},
      el("button", { type: "button", class: "side-item" + (ppSel.employee === e.id ? " on" : ""),
        onclick: () => { location.hash = employeeHash(moMonth, e.id); } },
      el("span", { class: "name", text: [e.emp_no, e.name].filter(Boolean).join(" ") || t("An employee") }),
      el("span", { class: e.status === "needs" ? "pill check" : "pill good",
        title: e.status === "needs" ? t("Needs you") : e.status === "million" ? t("Waiting for Million") : t("Ready") },
      icon(e.status === "needs" ? "alert-triangle" : e.status === "million" ? "clock-pause" : "circle-check")))))))));
  $("pp-none").hidden = rows.length > 0 || !ppView.companies.length;
  // the Company chosen in step 2 filters this list too: say so, and let it show everyone again
  $("pp-filter").hidden = !companyFilter;
  if (companyFilter) {
    const showAll = () => {
      companyFilter = "";
      try { localStorage.setItem("companyFilter", ""); } catch (_) { /* private window */ }
      companySignature = "";
      ppDrawList(); if (!$("employee").hidden) ppDrawWalk();
    };
    $("pp-filter").replaceChildren(t("Showing only {company} (the Company chosen in step 2).",
      { company: companyFilter === NO_COMPANY ? t("(no company)") : companyFilter }) + " ",
    el("button", { type: "button", class: "link", text: t("Show all companies"), onclick: showAll }));
  }
}

// "… need you in step 2 →": step 2 on the working month (not "All months"), on the first file with something to
// settle; for a company's button that company's files, with the Company chooser set to it (else every company).
function toFileProblems(company) {
  remember("checkAll", ""); ckAll = false; ckFiles = null;
  companyFilter = company === undefined ? "" : company === "" ? NO_COMPANY : company;
  try { localStorage.setItem("companyFilter", companyFilter); } catch (_) { /* private window */ }
  companySignature = "";
  remember("check.want", "1");
  location.hash = "#/check";
}

function ppShowPane(which) {
  for (const id of ["company", "employee", "look", "pp-empty"]) $(id).hidden = id !== which;
}

// What the address chose, or else the first employee who needs the user (or the first one). ``fresh``: ppView was
// just asked for; an employee or company not in an older one is looked for again before it counts as gone.
async function ppShowSelection(fresh) {
  if (!ppView) return;
  const sel = ppSel;
  const gone = (sel.employee && !everyone().some((e) => e.id === sel.employee))
    || (sel.company !== null && !ppView.companies.some((r) => r.company === sel.company));
  if (gone && !fresh) { await ppLoad(); if (ppSel === sel) await ppShowSelection(true); return; }
  if (gone) { forget("place.payroll"); location.replace(`#/payroll/${moMonth}`); return; }
  if (!sel.employee && sel.company === null) {
    const order = ppOrder();
    const first = order.find((e) => e.status === "needs") || order[0] || everyone()[0];
    if (first) location.replace(employeeHash(moMonth, first.id)); else ppShowPane("pp-empty");
    return;
  }
  if (sel.employee && sel.look) { ppShowPane("look"); if (typeof showLook === "function") showLook(moMonth, sel.employee); }
  else if (sel.employee) { ppShowPane("employee"); if (typeof showEmployee === "function") showEmployee(moMonth, sel.employee); }
  else { ppShowPane("company"); showCompany(sel.company); }
}

// ------------------------------------------------------------------------------------------------ the month bar
iconize($("mo-prev"), "chevron-left", t("Month before"));
iconize($("mo-next"), "chevron-right", t("Month after"));
iconize($("mo-settings-open"), "calendar-cog", t("Month settings"));
iconize($("mo-million-import"), "users", t("Import employee list from Million"));
$("mo-prev").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, -1)}`; });
$("mo-next").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, 1)}`; });
$("pp-to-upload").addEventListener("click", () => { location.hash = "#/"; });
$("pp-search").addEventListener("input", () => { ppDrawList(); if (!$("employee").hidden) ppDrawWalk(); });
$("pp-search").placeholder = t("Search name or Employee No.");
$("pp-search").setAttribute("aria-label", t("Search name or Employee No."));

// The Million file's summary inside the Export pop-up: who goes in (by company) and who is held back and why (folded).
function personText(p) { return [p.emp_no, p.name].filter(Boolean).join(" ") || t("An employee"); }

function summaryNodes(run) {
  const going = run.companies.filter((c) => c.ready);
  const nodes = [el("p", {}, el("strong", { text: run.ready
    ? t("Going in: {n} · held back: {h}", { n: run.ready, h: run.held })
    : t("No employee is ready for the Million file yet.") }))];
  if (going.length) {
    nodes.push(el("ul", { class: "run-going" }, ...going.map((c) => el("li", {}, el("strong", { text: `${c.company || t("No company")}: ` }),
      c.ready_people.map(personText).join("; ")))));
  }
  if (!run.checked_with_million) nodes.push(el("p", { class: "legend", text: t("The Employee Nos. were not checked against Million: import Million's employee list first.") }));
  if (run.held) nodes.push(el("details", {}, el("summary", { text: tn(run.held, "{n} employee held back: why", "{n} employees held back: why") }), ...heldNodes(run)));
  return [el("div", { class: "summary" }, ...nodes)];
}

// Export (a pop-up): what (the payroll table to check in Excel, or the Million import file), which companies (all, or
// the ticked ones: ``only`` ticks one), its format (CSV or Excel .xls; the Million file is always Million's .xls) and,
// for several companies, one file or one per company. The table downloads and the pop-up closes; the Million file
// shows its summary in the pop-up first, and once made it is saved in the payroll folder and said in the bell.
function openExport(only) {
  if (!ppView) return;
  const month = moMonth;
  const names = ppView.companies.filter((r) => r.employees.length).map((r) => r.company);
  const pick = (group, value, label, checked, cls = "seg") =>
    el("label", { class: cls }, el("input", { type: "radio", name: group, value, checked }), el("span", {}, ...[].concat(label)));
  const all = el("input", { type: "checkbox", "data-all": "1", checked: only === undefined });
  const ticks = names.map((name) => ({ name,
    box: el("input", { type: "checkbox", "data-company": name, checked: only !== undefined && name === only }) }));
  const form = el("div", { class: "export-form" },
    el("div", { class: "choices" },
      pick("ex-what", "table", [icon("table"), el("strong", { text: t("Payroll table") }), el("small", { text: t("to check in Excel") })], true, "choice"),
      pick("ex-what", "million", [icon("file-spreadsheet"), el("strong", { text: t("Million file") }), el("small", { text: t("to import in Million") })], false, "choice")),
    el("p", { class: "sec", text: t("Companies") }),
    el("div", { class: "chips" }, el("label", { class: "chip" }, all, el("span", { text: t("All") })),
      ...ticks.map(({ name, box }) => el("label", { class: "chip" }, box, el("span", { text: name || t("(no company)") })))),
    el("div", { class: "row export-two" },
      el("div", {}, el("p", { class: "sec", text: t("Format") }),
        el("div", { class: "segs", title: t("The Million import file is always .xls, in Million's layout.") },
          pick("ex-format", "csv", "CSV", true), pick("ex-format", "xls", "Excel", false))),
      el("div", {}, el("p", { class: "sec", text: t("Files") }),
        el("div", { class: "segs" }, pick("ex-split", "one", t("One file"), true), pick("ex-split", "each", t("One per company"), false)))));
  const value = (group) => form.querySelector(`input[name="${group}"]:checked`).value;
  const chosen = () => (all.checked ? null : ticks.filter((k) => k.box.checked).map((k) => k.name));
  const go = el("button", { type: "button", class: "primary", text: t("Export") });
  const cancel = el("button", { type: "button", text: t("Cancel"), onclick: closePopup });
  const paint = () => {
    const million = value("ex-what") === "million";
    form.querySelectorAll('input[name="ex-format"]').forEach((r) => { r.disabled = million; });
    const list = chosen();
    const several = list === null ? names.length > 1 : list.length > 1;
    form.querySelectorAll('input[name="ex-split"]').forEach((r) => { r.disabled = !several; });
    go.disabled = list !== null && !list.length;
  };
  all.addEventListener("change", () => { if (all.checked) ticks.forEach((k) => { k.box.checked = false; }); });
  ticks.forEach((k) => k.box.addEventListener("change", () => { if (k.box.checked) all.checked = false; }));
  form.addEventListener("change", paint);
  const query = () => {
    const p = new URLSearchParams();
    (chosen() || []).forEach((name) => p.append("c", name));
    p.set("split", value("ex-split"));
    return p;
  };
  const showForm = () => { $("popup-body").replaceChildren(form); $("popup-foot").replaceChildren(cancel, go); paint(); };
  const showSummary = (run, params) => {
    const make = el("button", { type: "button", class: "primary", text: t("Make the file"), disabled: !run.ready });
    make.addEventListener("click", async () => {
      make.disabled = true;
      try {
        const made = await api("POST", `/api/payroll/${month}/run?${params}`);
        closePopup(); moError("");
        bellAdd(month, madeMessage(made));
      } catch (e) { popupError(e.message); make.disabled = false; }
    });
    $("popup-body").replaceChildren(...summaryNodes(run));
    $("popup-foot").replaceChildren(el("button", { type: "button", text: t("Back"), onclick: showForm }), make);
  };
  go.addEventListener("click", async () => {
    const params = query();
    go.disabled = true;
    try {
      if (value("ex-what") === "table") {
        params.set("format", value("ex-format"));
        if (await downloadFile(`/api/payroll/${month}/export?${params}`, popupError)) closePopup();
        return;
      }
      const run = await api("GET", `/api/payroll/${month}/run?${params}`);
      if (popupOpen()) { popupError(""); showSummary(run, params); }
    } catch (e) { popupError(e.message); }
    finally { paint(); }
  });
  openPopup({ title: t("Export {month}", { month: monthTitle(month) }), icon: "download", body: [form], buttons: [cancel, go] });
  paint();
}

$("mo-export-open").replaceChildren(icon("download"), " ", t("Export"));
$("mo-export-open").addEventListener("click", () => openExport());

// A payroll file (CSV), fetched rather than opened as a link: when it cannot be made or saved (open in Excel, nobody
// in it) the reason is shown on the screen in the user's language instead of replacing the page.
async function downloadFile(url, showError) {
  let res;
  try { res = await fetch(url); }
  catch (_) { showError(t("Table Reader is not running any more. Close this tab and open Table Reader again.")); return; }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (_) { /* not JSON */ }
    showError(data && data.message ? tm(data.message) : t("Something went wrong. Reload the page and try again."));
    return;
  }
  const blob = await res.blob();
  const m = /filename\*=utf-8''([^;]+)|filename="?([^";]+)"?/i.exec(res.headers.get("content-disposition") || "");
  const a = el("a", { href: URL.createObjectURL(blob), download: m ? decodeURIComponent(m[1] || m[2]) : "Payroll.csv" });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 30000);
  showError("");
  return true;
}


$("mo-million-import").addEventListener("click", () => $("mo-million-file").click());
$("mo-million-file").addEventListener("change", async () => {
  const file = $("mo-million-file").files[0];
  $("mo-million-file").value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const month = moMonth;
  try {
    const list = await api("POST", "/api/million/employees", form);
    bellAdd(month, { icon: "users", line: tn(list.employees.length, "Employee list imported · {n} employee", "Employee list imported · {n} employees") });
    moError("");
    await ppLoad();
  } catch (e) { moError(e.message); }
});

// ------------------------------------------------------------------------------------------------ the company panel
function showCompany(company) {
  if (company !== coCompany) { $("co-million").hidden = true; coError(""); }
  coCompany = company;
  drawCompany();
  if (company) loadPayTable();
}

function drawCompany() {
  coView = ppView.companies.find((r) => r.company === coCompany)
    || { company: coCompany, status: "none", needs: 0, waiting: 0, items: [], employees: [], million_new: [], files_needing: 0 };
  $("co-title").textContent = `${coCompany || t("(no company)")} - ${monthTitle(moMonth)}`;
  $("co-status").textContent = companyStatus(coView);
  for (const id of ["co-settings-open", "co-export", "co-pay"]) $(id).hidden = !coCompany;   // files with no company: none
  const items = coView.items.map(itemNode);
  if (coView.files_needing) {
    items.push(el("li", { class: "need" }, el("strong", { text: tn(coView.files_needing,
      "{n} file of this company needs you in step 2.", "{n} files of this company need you in step 2.") }),
    el("div", { class: "need-buttons" }, el("button", { type: "button", class: "primary", text: t("Go to step 2 →"),
      onclick: () => toFileProblems(coCompany) }))));
  }
  $("co-items").replaceChildren(items.length ? el("ol", { class: "needs" }, ...items)
    : el("p", { class: "muted", text: t("Nothing needs you here.") }));
  $("co-export").disabled = !coView.employees.length;
  drawMillionNew();
}

// Do something for an item, then draw the month again from the server (and the employee, when one is open).
async function coAct(button, action) {
  button.disabled = true;
  try {
    await action(); coError(""); moError("");
    await ppLoad();
    if (!$("employee").hidden && typeof emLoad === "function") await emLoad();
  } catch (e) { ($("company").hidden ? moError : coError)(e.message); button.disabled = false; }
}

function employeeName(id) {
  const e = everyone().find((x) => x.id === id);
  return e ? (e.name || t("An employee")) : t("An employee");
}

const ITEM_HEADS = {
  look: "{name}: cells to check on the card",
  days: "{name}: days that do not add up",
  column: "{name}: Table Reader cannot work out the days",
  nocard: "{name}: no time card yet",
  held: "{name}: not ready for the Million file",
};

const ITEM_ICONS = { look: "eye", days: "calendar", column: "table", nocard: "id", held: "clock-pause",
  settings: "calendar-cog", offer: "users", empno: "id" };

// One thing that needs the user about an employee or a company (the files' are in step 2). ``short``: an icon and the
// title with the buttons; the longer sentences folded under More.
function itemNode(item, { short = false } = {}) {
  const name = item.employee ? employeeName(item.employee) : "";
  const buttons = [];
  let head = "", details = [];
  if (ITEM_HEADS[item.kind]) {
    head = t(ITEM_HEADS[item.kind], { name });
    details = item.texts.map(item.kind === "held" ? runReason : tm);
    if (item.places) {
      details.unshift(tn(item.places, "{n} line of the time cards to check.", "{n} lines of the time cards to check."));
      buttons.push(el("button", { type: "button", class: "primary", text: t("Look"),
        onclick: () => { location.hash = `${employeeHash(moMonth, item.employee)}/look`; } }));
    }
    if (item.kind === "look" && item.texts.length) {               // problems the panel cannot show: on the card
      item.cards.forEach((c, n) => buttons.push(el("button", { type: "button", title: c.name,
        text: item.cards.length > 1 ? t("Check card {n} →", { n: n + 1 }) : t("Check this card →"),
        onclick: () => { location.hash = `#/check/${encodeURIComponent(c.id)}`; } })));
    }
  } else if (item.kind === "settings") {
    head = t("{company}: the month's default changed after this company got its own settings", { company: item.company });
    details = [t("Public holidays and rest days marked in the month's settings are not copied to a company with its own settings. Check its calendar.")];
    const right = el("button", { type: "button", text: t("It is right") });
    right.addEventListener("click", () => keepCompanySettings(right));
    buttons.push(el("button", { type: "button", class: "primary", text: t("Open settings"), onclick: openCompanySettings }), right);
  } else if (item.kind === "offer") {
    head = t("{name}: Million has Employee No. {no} for {million}", { name, no: item.emp_no, million: item.million_name });
    const use = el("button", { type: "button", class: "primary", text: t("Use {no}", { no: item.emp_no }) });
    use.addEventListener("click", () => coAct(use, () => api("PUT",
      `/api/payroll/${moMonth}/employees/${encodeURIComponent(item.employee)}`, { emp_no: item.emp_no })));
    buttons.push(use);
  } else if (item.kind === "empno") {
    head = t("{name}: Employee No. to fix", { name });
    details = [item.why === "empty" ? t("It is empty. Type it exactly as in Million Payroll.")
      : item.why === "shared" ? t("Employee No. {no} is used for {n} employees. Each employee needs their own.", { no: item.emp_no, n: item.count })
        : t("In Million Payroll, Employee No. {no} is {million}.", { no: item.emp_no, million: item.million_name })];
  }
  if (short) {
    return el("li", { class: "need short" },
      el("div", { class: "need-head" }, icon(ITEM_ICONS[item.kind] || "alert-triangle"), el("strong", { text: head }),
        el("div", { class: "need-buttons" }, ...buttons)),
      details.length ? el("details", {}, el("summary", { text: t("More") }), ...details.map((d) => el("p", { class: "legend", text: d }))) : null);
  }
  return el("li", { class: "need" }, el("strong", { text: head }),
    ...details.map((d) => el("p", { class: "legend", text: d })), el("div", { class: "need-buttons" }, ...buttons));
}

// "New in Million": the company's employees whose Employee No. is not in Million's imported list. They are held back
// from the month's file until they are created in Million and its list is imported again; the rest go in.
// The clipboard API first; where the browser refuses it, the older copy of a selected text box.
function copyBySelecting(text) {
  const box = el("textarea", { readonly: true, style: "position:fixed;left:-9999px", text });
  document.body.append(box);
  box.select();
  let done = false;
  try { done = document.execCommand("copy"); } catch (_) { /* not supported */ }
  box.remove();
  if (!done) throw new Error("copy refused");
}

async function copyText(button, text) {
  try {
    try { await navigator.clipboard.writeText(text); } catch (_) { copyBySelecting(text); }
    const was = button.textContent;
    button.textContent = t("Copied");
    setTimeout(() => { button.textContent = was; }, 1500);
    coError("");
  } catch (_) { coError(t("Copying did not work. Select the numbers and copy them yourself.")); }
}

function drawMillionNew() {
  const list = coView.million_new, panel = $("co-million");
  $("co-million-open").hidden = !list.length;
  $("co-million-open").textContent = tn(list.length, "New in Million: {n} employee", "New in Million: {n} employees");
  if (!list.length) panel.hidden = true;
  if (panel.hidden) return;
  const rows = list.map((m) => {
    const copy = el("button", { type: "button", text: t("Copy") });
    copy.addEventListener("click", () => copyText(copy, m.emp_no));
    return el("tr", {}, el("td", { text: m.emp_no }), el("td", { text: m.name }), el("td", {}, copy));
  });
  const all = el("button", { type: "button", class: "primary", text: t("Copy all") });
  all.addEventListener("click", () => copyText(all, list.map((m) => `${m.emp_no}\t${m.name}`).join("\n")));   // two columns in Excel
  const close = el("button", { type: "button", text: t("Close"), onclick: () => { panel.hidden = true; } });
  panel.replaceChildren(
    el("h3", { text: tn(list.length, "{company}: {n} employee Million does not have yet", "{company}: {n} employees Million does not have yet",
      { company: coCompany || t("(no company)") }) }),
    el("table", { class: "daytable companies" },
      el("tr", {}, el("th", { text: t("Employee No.") }), el("th", { text: t("Name") }), el("th")), ...rows),
    el("p", { class: "legend", text: t("Create them in Million with exactly these numbers, then export Million's employee list and import it on the month page.") }),
    el("p", { class: "legend", text: t("To export the list in Million Payroll: Employee > Print > Employment Listing > Print > Excel > File. The file is rptempepmlist.xls in Million's company folder (for example C:\\million\\Payroll\\mycompany).") }),
    el("div", { class: "need-buttons" }, all, close));
}

$("co-million-open").addEventListener("click", () => { $("co-million").hidden = !$("co-million").hidden; drawMillionNew(); });
$("co-export").replaceChildren(icon("download"), " ", t("Export"));
$("co-export").addEventListener("click", () => openExport(coCompany));

// ------------------------------------------------------------------------------------------------ the open employee
// Their "Needs you", and Previous / Next needing you (the employee view itself is employee.js).
function ppItemsOf(id) {
  const e = everyone().find((x) => x.id === id);
  return e ? e.items : [];
}

function ppDrawEmployeeNeeds() {
  const items = ppItemsOf(ppSel.employee);
  $("em-needs").replaceChildren(items.length ? el("ol", { class: "needs" }, ...items.map((i) => itemNode(i, { short: true })))
    : el("p", { class: "nothing" }, icon("circle-check"), " ", t("Nothing to fix")),
  ...[typeof emInfoNotes === "function" ? emInfoNotes() : null].filter(Boolean));
  if (typeof emDrawTabs === "function") emDrawTabs();
}

function ppDrawWalk() {
  const order = ppOrder();
  const at = order.findIndex((e) => e.id === ppSel.employee);
  const prev = at > 0 ? order[at - 1] : null;
  const next = [...order.slice(at + 1), ...order.slice(0, Math.max(at, 0))].find((e) => e.status === "needs");
  $("em-walk").replaceChildren(
    el("button", { type: "button", text: t("‹ Previous"), disabled: !prev,
      onclick: () => { location.hash = employeeHash(moMonth, prev.id); } }),
    el("button", { type: "button", class: "primary", text: next ? t("Next to fix ›") : t("Nobody else needs you"),
      disabled: !next, onclick: () => { location.hash = employeeHash(moMonth, next.id); } }));
}
