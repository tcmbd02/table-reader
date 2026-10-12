"use strict";
// Payroll by company: the month overview (one row per company) and a company's screen ("Needs you" + employees).
// Loaded after app.js and payroll.js and uses their helpers. The old payroll page stays at #/payroll/<month>/old.

let moMonth = null;        // the month the overview / company screen shows ("2026-09")

function monthTitle(month) {
  const [y, m] = month.split("-").map(Number);
  return `${t(MONTH_NAMES[m - 1])} ${y}`;
}

function shiftMonth(month, by) {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + by, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

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
  $("mo-old").href = `#/payroll/${moMonth}/old`;
  $("mo-run-result").hidden = true;
  moError("");
  try { drawMonth(await api("GET", `/api/payroll/${moMonth}/companies`)); }
  catch (e) { moError(e.message); }
}

function drawMonth(over) {
  const info = [addedByThemselves(over.added_by_themselves), over.numbered ? newNumbersText(over.numbered) : ""].filter(Boolean).join(" ");
  $("mo-info").hidden = !info; $("mo-info").textContent = info;
  const rows = over.companies.map((c) => {
    const open = () => { location.hash = companyHash(moMonth, c.company); };
    return el("tr", { class: `company-row ${c.status}`, tabindex: "0", onclick: open,
      onkeydown: (e) => { if (e.key === "Enter") open(); } },
    el("td", { text: c.company || t("(no company)") }), el("td", { text: String(c.employees) }), el("td", { text: statusText(c) }));
  });
  $("mo-companies").replaceChildren(rows.length
    ? el("table", { class: "daytable companies" },
      el("tr", {}, el("th", { text: t("Company") }), el("th", { text: t("Employees") }), el("th", { text: t("Status") })), ...rows)
    : el("p", { class: "muted", text: t("No files for this month yet. Add time cards on the start page or in the Inbox folder.") }));
  const total = over.companies.filter((c) => c.status !== "none").length;
  $("mo-total").textContent = [
    t("{a} of {b} companies ready.", { a: over.ready_companies, b: total }),
    tn(over.ready_employees, "{n} employee would be in the file now.", "{n} employees would be in the file now."),
    over.checked_with_million ? "" : t("The Employee Nos. are not being checked against Million: import Million's employee list."),
  ].filter(Boolean).join(" ");
}

$("mo-back").addEventListener("click", () => { location.hash = ""; });
$("mo-old").addEventListener("click", () => { window.prOpenCompany = ""; });      // the old page on every company
$("mo-prev").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, -1)}`; });
$("mo-next").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, 1)}`; });

$("mo-run").addEventListener("click", async () => {
  const btn = $("mo-run");
  btn.disabled = true;
  try { showMonthRun(await api("POST", `/api/payroll/${moMonth}/run`), $("mo-run-result")); moError(""); }
  catch (e) { moError(e.message); }
  finally { btn.disabled = false; }
});

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
  coError("");
  await loadCompany();
}

async function loadCompany() {
  try {
    coView = await api("GET", `/api/payroll/${moMonth}/company?name=${encodeURIComponent(coCompany)}`);
    drawCompany();
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

// Open the old payroll page on this company and this employee: every figure, the cards, the number, the overrides.
function openEmployee(id) {
  window.prOpenCompany = coCompany || NO_COMPANY;
  window.prOpenEmployee = id;
  location.hash = `#/payroll/${moMonth}/old`;
}

function openEmployeeButton(id) {
  return el("button", { type: "button", text: t("Open employee"), onclick: () => openEmployee(id) });
}

function openCardButton(doc) {
  return el("button", { type: "button", text: t("Open the card"), onclick: () => { location.hash = `#/doc/${encodeURIComponent(doc)}`; } });
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
    if (item.kind === "look") {
      item.cards.forEach((c, n) => buttons.push(el("button", { type: "button", title: c.name,
        text: item.cards.length > 1 ? t("Open card {n}", { n: n + 1 }) : t("Open the card"),
        onclick: () => { location.hash = `#/doc/${encodeURIComponent(c.id)}`; } })));
    } else buttons.push(openEmployeeButton(item.employee));
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
  if (coView.million_new.length) {
    $("co-employees").append(el("p", { class: "legend", text: tn(coView.million_new.length,
      "{n} employee is not in Million yet: {list}. Create them in Million with exactly this number, then import Million's employee list on the month page.",
      "{n} employees are not in Million yet: {list}. Create them in Million with exactly these numbers, then import Million's employee list on the month page.",
      { list: coView.million_new.map((m) => `${m.emp_no} ${m.name}`.trim()).join("; ") }) }));
  }
}

$("co-back").addEventListener("click", () => { location.hash = `#/payroll/${moMonth}`; });

if (location.hash.startsWith("#/payroll")) route();      // the page was opened on a payroll screen: app.js ran before this file
