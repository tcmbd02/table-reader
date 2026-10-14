"use strict";
// Payroll by company: the month overview (one row per company) and a company's screen ("Needs you" + employees).
// Loaded after app.js and paycommon.js and uses their helpers.

let moMonth = null;        // the month the overview / company screen shows ("2026-09")
let moOver = null;         // what the server last sent for the overview (its "settings" = the month's default)

function companyHash(month, company) { return `#/payroll/${month}/c/${encodeURIComponent(company)}`; }

function statusText(row) {
  if (row.status === "none") return t("No files yet");
  if (row.status === "needs") return tn(row.needs, "Needs you: {n} thing", "Needs you: {n} things");
  if (row.status === "million") return tn(row.waiting, "Ready, {n} waiting for Million", "Ready, {n} waiting for Million");
  return t("Ready");
}

function moError(message) { $("mo-error").hidden = !message; $("mo-error").textContent = message || ""; }

async function showMonth(month) {
  clearTimeout(docTimer); currentId = null; currentDoc = null;
  hideScreens(); $("month").hidden = false;
  moMonth = month || defaultPayrollMonth();
  $("mo-title").textContent = t("Payroll {month}", { month: monthTitle(moMonth) });
  $("mo-run-result").hidden = true;
  $("mo-settings").hidden = true;
  moError("");
  try { drawMonth(await api("GET", `/api/payroll/${moMonth}/companies`)); }
  catch (e) { moError(e.message); }
}

function drawMonth(over) {
  moOver = over;
  const info = [addedByThemselves(over.added_by_themselves), over.numbered ? newNumbersText(over.numbered) : ""].filter(Boolean).join(" ");
  $("mo-info").hidden = !info; $("mo-info").textContent = info;
  const rows = over.companies.map((c) => {
    const open = () => { location.hash = companyHash(moMonth, c.company); };
    return el("tr", { class: `company-row ${c.status}`, tabindex: "0", onclick: open,
      onkeydown: (e) => { if (e.key === "Enter") open(); } },
    el("td", { text: c.company || t("(no company)") }), el("td", { text: String(c.employees) }),
    el("td", { text: statusText(c) + (c.own ? ` · ${t("own settings")}` : "") }));
  });
  $("mo-companies").replaceChildren(rows.length
    ? el("table", { class: "daytable companies" },
      el("tr", {}, el("th", { text: t("Company") }), el("th", { text: t("Employees") }), el("th", { text: t("Status") })), ...rows)
    : el("p", { class: "muted", text: t("No files for this month yet. Add time cards on the start page or in the Inbox folder.") }));
  $("mo-csv").disabled = !over.companies.some((c) => c.employees);
  const total = over.companies.filter((c) => c.status !== "none").length;
  $("mo-total").textContent = [
    t("{a} of {b} companies ready.", { a: over.ready_companies, b: total }),
    tn(over.ready_employees, "{n} employee would be in the file now.", "{n} employees would be in the file now."),
    over.checked_with_million ? "" : t("The Employee Nos. are not being checked against Million: import Million's employee list."),
  ].filter(Boolean).join(" ");
}

$("mo-back").addEventListener("click", () => { location.hash = ""; });
// the top bar's Payroll link: on a payroll screen already, the address does not change, so draw it again
$("nav-payroll").addEventListener("click", () => { if (location.hash.startsWith("#/payroll")) route(); });
$("mo-prev").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, -1)}`; });
$("mo-next").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, 1)}`; });

// The month's Million file: first what it would hold and who is held back, then made on "Make the file" (worked out
// again then, so something fixed in between is in it).
function personText(p) { return [p.emp_no, p.name].filter(Boolean).join(" ") || t("An employee"); }

function showMonthSummary(run, month) {
  const box = $("mo-run-result");
  const going = run.companies.filter((c) => c.ready);
  const parts = [el("strong", { text: run.ready
    ? tn(run.ready, "The month's Million file would hold {n} employee from {c}.", "The month's Million file would hold {n} employees from {c}.",
      { c: tn(going.length, "{n} company", "{n} companies") })
    : t("No employee is ready for the month's Million file yet.") })];
  if (going.length) {
    parts.push(el("ul", {}, ...going.map((c) => el("li", {}, el("strong", { text: `${c.company || t("No company")}: ` }),
      c.ready_people.map(personText).join("; ")))));
  }
  if (!run.checked_with_million) parts.push(el("p", { class: "legend", text: t("The Employee Nos. were not checked against Million: import Million's employee list first.") }));
  parts.push(...heldNodes(run));
  const make = el("button", { type: "button", class: "primary", text: t("Make the file"), disabled: !run.ready });
  make.addEventListener("click", async () => {
    make.disabled = true;
    try { showMonthRun(await api("POST", `/api/payroll/${month}/run`), box); moError(""); }    // the summary's month
    catch (e) { moError(e.message); make.disabled = false; }
  });
  const later = el("button", { type: "button", text: t("Not now"), onclick: () => { box.hidden = true; } });
  parts.push(el("div", { class: "need-buttons" }, make, later));
  box.replaceChildren(...parts); box.hidden = false;
  box.scrollIntoView({ block: "nearest" });
}

$("mo-run").addEventListener("click", async () => {
  const btn = $("mo-run"), month = moMonth;
  btn.disabled = true;
  try {
    const run = await api("GET", `/api/payroll/${month}/run`);
    if (month === moMonth && !$("month").hidden) { showMonthSummary(run, month); moError(""); }   // still on that month
  } catch (e) { if (month === moMonth) moError(e.message); }
  finally { btn.disabled = false; }
});

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
}

$("mo-csv").addEventListener("click", () => downloadFile(`/api/payroll/${moMonth}/csv`, moError));

$("mo-million-import").addEventListener("click", () => $("mo-million-file").click());
$("mo-million-file").addEventListener("change", async () => {
  const file = $("mo-million-file").files[0];
  $("mo-million-file").value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  try { await api("POST", "/api/million/employees", form); showMonth(moMonth); }
  catch (e) { moError(e.message); }
});

// ------------------------------------------------------------------------------------------------ company screen
let coCompany = "";        // the company on the screen ("" = no company)
let coView = null;         // what the server last sent for it

function coError(message) { $("co-error").hidden = !message; $("co-error").textContent = message || ""; }

async function showCompany(month, company) {
  clearTimeout(docTimer); currentId = null; currentDoc = null;
  hideScreens(); $("company").hidden = false;
  moMonth = month || defaultPayrollMonth();
  coCompany = company;
  $("co-title").textContent = `${company || t("(no company)")} - ${monthTitle(moMonth)}`;
  $("co-settings").hidden = true;
  $("co-million").hidden = true;
  $("co-million-open").hidden = true;                        // until this company's list is in (not the last one's)
  $("co-settings-open").hidden = !company;                  // files with no company have no settings of their own
  $("co-csv").hidden = !company;                             // the CSV without a company would hold every company
  $("co-tab-pay").hidden = !company;                         // and so would the pay preview
  showCompanyTab("employees");                               // always opens on Employees
  coError("");
  await loadCompany();
}

async function loadCompany() {
  try {
    coView = await api("GET", `/api/payroll/${moMonth}/company?name=${encodeURIComponent(coCompany)}`);
    drawCompany();
    if (!$("co-pay").hidden) loadPayTable();
  } catch (e) { coError(e.message); }
}

// Do something for an item, then draw the company again from the server (the list is always what the server says).
async function coAct(button, action) {
  button.disabled = true;
  try { await action(); coError(""); await loadCompany(); }
  catch (e) { coError(e.message); button.disabled = false; }
}

function employeeName(id) {
  const e = coView.employees.find((x) => x.id === id);
  return e ? (e.name || t("An employee")) : t("An employee");
}

// Whatever a company screen opens (a card, an employee) opens in a new tab, so the list of what needs the user stays
// where it is. Coming back to this tab draws the list again (see the end of this file).
function openInNewTab(hash) { window.open(location.pathname + hash, "_blank"); }

// The employee view: every figure, the cards, the number, the overrides.
function openEmployee(id) { openInNewTab(`#/payroll/${moMonth}/e/${encodeURIComponent(id)}`); }

function openEmployeeButton(id) {
  return el("button", { type: "button", text: t("Open employee"), onclick: () => openEmployee(id) });
}

function openCardButton(doc) {
  return el("button", { type: "button", text: t("Open the card"), onclick: () => openInNewTab(`#/doc/${encodeURIComponent(doc)}`) });
}

const ITEM_HEADS = {
  look: "{name}: cells to check on the card",
  days: "{name}: days that do not add up",
  column: "{name}: Table Reader cannot work out the days",
  nocard: "{name}: no time card yet",
  held: "{name}: not ready for the Million file",
};

function itemNode(item) {
  const name = item.employee ? employeeName(item.employee) : "";
  const buttons = [];
  let head = "", details = [];
  if (ITEM_HEADS[item.kind]) {
    head = t(ITEM_HEADS[item.kind], { name });
    // what the month file says about an employee comes without its "- who: " start: runReason translates those
    details = item.texts.map(item.kind === "held" ? runReason : tm);
    if (item.places) {
      // lines of the cards the calculation could not use: all of them in one panel, beside the card's picture
      details.unshift(tn(item.places, "{n} line of the time cards to check.", "{n} lines of the time cards to check."));
      buttons.push(el("button", { type: "button", class: "primary", text: t("Look"),
        onclick: () => { location.hash = `#/payroll/${moMonth}/look/${encodeURIComponent(item.employee)}`; } }));
    }
    if (item.kind === "look" && item.texts.length) {               // problems the panel cannot show: on the card
      item.cards.forEach((c, n) => buttons.push(el("button", { type: "button", title: c.name,
        text: item.cards.length > 1 ? t("Open card {n}", { n: n + 1 }) : t("Open the card"),
        onclick: () => openInNewTab(`#/doc/${encodeURIComponent(c.id)}`) })));
    } else if (item.kind !== "look") buttons.push(openEmployeeButton(item.employee));
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
    buttons.push(use, openEmployeeButton(item.employee));
  } else if (item.kind === "empno") {
    head = t("{name}: Employee No. to fix", { name });
    details = [item.why === "empty" ? t("It is empty. Type it exactly as in Million Payroll.")
      : item.why === "shared" ? t("Employee No. {no} is used for {n} employees. Each employee needs their own.", { no: item.emp_no, n: item.count })
        : t("In Million Payroll, Employee No. {no} is {million}.", { no: item.emp_no, million: item.million_name })];
    buttons.push(openEmployeeButton(item.employee));
  } else if (item.kind === "unplaced") {
    head = t("{file}: whose card is this?", { file: item.name });
    if (!item.readable) details = [t("Table Reader cannot work out the days from this file yet; the figures will have to be typed.")];
    const place = (button, employee) => coAct(button, () => api("POST", `/api/payroll/${moMonth}/place`, { ref: item.ref, employee }));
    for (const e of coView.employees) {
      const b = el("button", { type: "button", text: e.name || e.emp_no || t("An employee") });
      b.addEventListener("click", () => place(b, e.id));
      buttons.push(b);
    }
    const fresh = el("button", { type: "button", text: t("New employee") });
    fresh.addEventListener("click", () => place(fresh, null));
    buttons.push(fresh);
    if (item.ref === item.doc) {                 // a whole file that is nobody's card (a notice, a second scan)
      const none = el("button", { type: "button", text: t("Not a time card") });
      none.addEventListener("click", () => coAct(none, () => api("POST", "/api/payroll/file-month", { id: item.doc, month: "none" })));
      buttons.push(none);
    }
    buttons.push(openCardButton(item.doc));
  } else if (item.kind === "layout") {
    // a card layout Table Reader has no rule for, with columns of figures the payroll does not use (yet); or one the
    // user confirmed with which the days cannot be worked out (it comes back until the columns are said again)
    head = item.confirmed ? t("{file}: the days cannot be worked out with the saved card layout", { file: item.name })
      : t("{file}: a card layout Table Reader does not know", { file: item.name });
    details = [item.confirmed ? t("Say which column holds the date and which the hours or times.")
      : t("Columns with figures that are not used: {list}. Say once what they mean; it is kept for every card with the same headings.",
        { list: item.columns.join(", ") })];
    const hours = item.hours_column ? `/h/${encodeURIComponent(item.hours_column)}` : "";
    const check = el("button", { type: "button", class: "primary", text: t("Check the columns"),
      onclick: () => { location.hash = `#/payroll/${moMonth}/layout/${encodeURIComponent(item.doc)}/${item.page}${hours}`; } });
    buttons.push(check);
    if (!item.confirmed) {
      const asIs = el("button", { type: "button", text: t("It is right as it is") });
      asIs.addEventListener("click", () => coAct(asIs, () => api("PUT", "/api/layouts",
        { doc: item.doc, page: item.page, as_is: true, hours_column: item.hours_column })));
      buttons.push(asIs);
    }
    buttons.push(openCardButton(item.doc));
  } else if (item.kind === "month") {
    head = t("{file}: which month is this for?", { file: item.name });
    details = [tm(item.why)];
    const setMonth = (button, month) => coAct(button, () => api("POST", "/api/payroll/file-month", { id: item.doc, month }));
    const here = el("button", { type: "button", text: t("It is for {month}", { month: monthTitle(moMonth) }) });
    here.addEventListener("click", () => setMonth(here, moMonth));
    const none = el("button", { type: "button", text: t("Not a time card") });
    none.addEventListener("click", () => setMonth(none, "none"));
    buttons.push(here, none, openCardButton(item.doc));
  }
  return el("li", { class: "need" }, el("strong", { text: head }),
    ...details.map((d) => el("p", { class: "legend", text: d })), el("div", { class: "need-buttons" }, ...buttons));
}

// A finished file with no company: it gets one here, and then shows up under that company.
function looseFileNode(file) {
  const input = el("input", { type: "text", maxlength: "80", placeholder: t("Company name"), value: suggestCompany(file.name),
    "aria-label": t("Company for {name}", { name: file.name }) });
  const save = el("button", { type: "button", class: "primary", text: t("Save") });
  save.addEventListener("click", () => coAct(save, async () => {
    if (!input.value.trim()) throw new Error(t("Type the company's name first."));
    await api("PUT", `/api/jobs/${encodeURIComponent(file.id)}/company`, { company: input.value });
  }));
  return el("li", { class: "need" }, el("strong", { text: t("{file}: which company is this for?", { file: file.name }) }),
    el("div", { class: "need-buttons" }, input, save, openCardButton(file.id)));
}

const EMPLOYEE_WORDS = { ready: "Ready", million: "Waiting for Million", needs: "Needs you" };
const EMPLOYEE_HEADS = ["Employee No.", "Name", "Days Worked", "OT 1.5 (hours)", "Rest day (days)", "Status"];

function drawCompany() {
  const files = (coView.files || []).map(looseFileNode);
  const items = coView.items.map(itemNode);
  const count = files.length + items.length;
  $("co-status").textContent = count ? tn(count, "Needs you: {n} thing", "Needs you: {n} things")
    : coView.employees.length ? statusText({ status: coView.status, needs: 0, waiting: coView.waiting }) : "";
  $("co-items").replaceChildren(count ? el("ol", { class: "needs" }, ...files, ...items)
    : el("p", { class: "muted", text: coView.employees.length ? t("Nothing needs you here.") : t("Nothing here for this month.") }));
  const rows = coView.employees.map((e) => {
    const open = () => openEmployee(e.id);
    return el("tr", { class: `company-row ${e.status}`, tabindex: "0", onclick: open, onkeydown: (ev) => { if (ev.key === "Enter") open(); } },
      el("td", { text: e.emp_no }), el("td", { text: e.name || t("An employee") }), el("td", { text: fmt(e.days_worked) }),
      el("td", { text: fmt(e.ot_1_5) }), el("td", { text: fmt(e.ot_rest_day) }), el("td", { text: t(EMPLOYEE_WORDS[e.status]) }));
  });
  $("co-employees").replaceChildren(rows.length
    ? el("table", { class: "daytable companies" }, el("tr", {}, ...EMPLOYEE_HEADS.map((h) => el("th", { text: t(h) }))), ...rows)
    : el("p", { class: "muted", text: t("No employees for this company in this month yet.") }));
  $("co-csv").disabled = !coView.employees.length;
  drawOtherFiles();
  drawMillionNew();
}

// Files of the company on nobody in this month: set aside as "Not a time card", or read as another month and on nobody
// there. Folded (they do not need the user); "It is for <month>" puts a mistake right.
function drawOtherFiles() {
  const files = coView.other_files || [];
  const box = $("co-other");
  box.hidden = !files.length;
  if (!files.length) { box.replaceChildren(); return; }
  const rows = files.map((f) => {
    const here = el("button", { type: "button", text: t("It is for {month}", { month: monthTitle(moMonth) }) });
    here.addEventListener("click", () => coAct(here, () => api("POST", "/api/payroll/file-month", { id: f.doc, month: moMonth })));
    const why = f.month === "none" ? t("Set aside as not a time card.") : t("Read as a file of {month}.", { month: monthTitle(f.month) });
    return el("li", { class: "need" }, el("strong", { text: f.name }), el("p", { class: "legend", text: why }),
      el("div", { class: "need-buttons" }, here, openCardButton(f.doc)));
  });
  box.replaceChildren(el("summary", { text: tn(files.length, "{n} other file of this company", "{n} other files of this company") }),
    el("p", { class: "legend", text: t("Files set aside as not a time card, or read as another month, that are on nobody this month. If one is a time card of this month, take it in.") }),
    el("ol", { class: "needs" }, ...rows));
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
$("co-csv").addEventListener("click", () => downloadFile(`/api/payroll/${moMonth}/csv?company=${encodeURIComponent(coCompany)}`, coError));

$("co-back").addEventListener("click", () => { location.hash = `#/payroll/${moMonth}`; });

// Back in this tab after fixing something in another one: show what is true now.
let lastReturn = 0;
async function refreshOnReturn() {
  if (document.hidden || Date.now() - lastReturn < 1000) return;      // the two events below often come together
  const typing = document.activeElement && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName);
  if (typing) return;                                                  // do not wipe a box the user is typing in
  lastReturn = Date.now();
  if (!$("company").hidden) loadCompany();
  else if (!$("look").hidden) refreshLook();
  else if (!$("employee").hidden) { if (emView && !Object.keys(emPending).length) emLoad(); }      // nothing waiting to be sent
  else if (!$("layout").hidden) return;                                // the user is choosing: leave it as it is
  else if (!$("month").hidden) {
    try { drawMonth(await api("GET", `/api/payroll/${moMonth}/companies`)); } catch (e) { moError(e.message); }
  }
}
document.addEventListener("visibilitychange", refreshOnReturn);
window.addEventListener("focus", refreshOnReturn);
