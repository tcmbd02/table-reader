"use strict";
// Payroll screen: the month's days, the employees with their time-card files, and the figures Table Reader works out.
// Uses $, el and api from app.js, t/tn/tm from i18n.js. Text from the server is always inserted with textContent.
// The results window copies Million Payroll's Edit Payroll screen, so its labels stay in English in both languages.

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAY_ORDER = ["work", "rest", "holiday"];
const DAY_WORDS = { work: t("Working day"), rest: t("Rest day"), holiday: t("Public holiday") };
const STATUS_WORDS = { ok: "", unclear: t("unclear: fix it in the document"), conflict: t("written twice, differs"), missing: t("no entry") };

let pr = null;          // { plan, documents, results, fields } as last sent by the server
let prMonth = null;
let prSaveTimer = null;
let prDirty = false;

function defaultPayrollMonth() {
  const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1);          // payroll is usually for last month
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function payrollUrl(suffix = "") { return `/api/payroll/${encodeURIComponent(prMonth)}${suffix}`; }

function prShowError(message) {
  const box = $("pr-error");
  box.hidden = !message; box.textContent = message || "";
}

async function showPayroll(month) {
  clearTimeout(docTimer); currentId = null; currentDoc = null;
  $("home").hidden = true; $("doc").hidden = true; $("payroll").hidden = false;
  prMonth = month || defaultPayrollMonth();
  prShowError("");
  try {
    pr = await api("GET", payrollUrl());
    prDirty = false;
    renderPayroll();
  } catch (e) { prShowError(e.message); }
}

function setSaveState(text) { $("pr-save").textContent = text; }

// Redraw without losing the box the user is typing in (the results window is rebuilt after every save).
function keepFocus(redraw) {
  const a = document.activeElement;
  const id = a && $("pr-results").contains(a) ? a.id : "";
  let sel = null;
  try { if (id && a.selectionStart !== null) sel = [a.selectionStart, a.selectionEnd]; } catch (_) { /* number boxes */ }
  redraw();
  const again = id && $(id);
  if (!again) return;
  again.focus();
  try { if (sel) again.setSelectionRange(sel[0], sel[1]); } catch (_) { /* number boxes */ }
}

function schedulePayrollSave() {
  prDirty = true; setSaveState(t("Saving…"));
  clearTimeout(prSaveTimer);
  prSaveTimer = setTimeout(savePayroll, 500);
}

async function savePayroll() {
  clearTimeout(prSaveTimer);
  if (!prDirty) return true;
  prDirty = false;
  try {
    const view = await api("PUT", payrollUrl(), pr.plan);
    pr.documents = view.documents; pr.results = view.results;
    // the server takes off time cards that no longer exist: keep the page's copy the same
    view.plan.employees.forEach((saved, k) => { if (pr.plan.employees[k]) pr.plan.employees[k].jobs = saved.jobs; });
    prShowError(""); setSaveState(t("Saved"));
    keepFocus(renderResults); renderDaysSummary();
    if (!$("pr-employees").contains(document.activeElement)) renderEmployees();     // refresh the "Hours column" choices
    return true;
  } catch (e) { prShowError(e.message); setSaveState(t("Not saved")); prDirty = true; return false; }
}

// ------------------------------------------------------------------------------------------------------ month + days
function monthParts() { const [y, m] = prMonth.split("-").map(Number); return { y, m, n: new Date(y, m, 0).getDate() }; }

function renderMonth() {
  const { y, m, n } = monthParts();
  const monthSel = el("select", { id: "pr-m", "aria-label": t("Month") },
    ...MONTH_NAMES.map((name, i) => el("option", { value: String(i + 1), text: t(name), selected: i + 1 === m })));
  const yearIn = el("input", { id: "pr-y", type: "number", min: "2000", max: "2100", value: String(y), style: "width:90px" });
  const go = () => {
    const yy = Number(yearIn.value);
    if (yy >= 2000 && yy <= 2100) location.hash = `#/payroll/${yy}-${String(monthSel.value).padStart(2, "0")}`;
  };
  monthSel.addEventListener("change", async () => { await savePayroll(); go(); });
  yearIn.addEventListener("change", async () => { await savePayroll(); go(); });
  const hours = el("input", { type: "number", min: "1", max: "24", step: "0.25", value: String(pr.plan.normal_hours), style: "width:90px" });
  hours.addEventListener("change", () => {
    const v = Number(hours.value);
    if (v >= 1 && v <= 24) { pr.plan.normal_hours = v; schedulePayrollSave(); } else hours.value = String(pr.plan.normal_hours);
  });
  // IN/OUT time cards: the break taken off a day that has one IN and one OUT time
  const rest = el("input", { type: "number", min: "0", max: "5", step: "0.25", value: String(pr.plan.break_hours ?? 1), style: "width:90px" });
  rest.addEventListener("change", () => {
    const v = Number(rest.value);
    if (rest.value !== "" && v >= 0 && v <= 5) { pr.plan.break_hours = v; schedulePayrollSave(); } else rest.value = String(pr.plan.break_hours ?? 1);
  });
  const grid = el("div", { class: "days", id: "pr-days" });
  for (let d = 1; d <= n; d++) {
    const btn = el("button", { type: "button", class: "day" });
    btn.addEventListener("click", () => {
      const cur = pr.plan.day_types[String(d)];
      pr.plan.day_types[String(d)] = DAY_ORDER[(DAY_ORDER.indexOf(cur) + 1) % DAY_ORDER.length];
      paintDay(btn, d); renderDaysSummary(); schedulePayrollSave();
    });
    paintDay(btn, d);
    grid.append(btn);
  }
  $("pr-month").replaceChildren(
    el("div", { class: "row" }, el("label", {}, t("Month"), monthSel), el("label", {}, t("Year"), yearIn),
      el("label", {}, t("Normal hours in a working day (overtime starts after this)"), hours),
      el("label", {}, t("Break taken off IN/OUT time cards (hours)"), rest)),
    el("p", { class: "legend", text: t("Time cards with IN and OUT times: the hours of a day are OUT minus IN, less the break. A day with more than one IN/OUT pair (morning and afternoon) is added up and no break is taken off.") }),
    el("p", { class: "legend", text: t("Click a day to change it: working day → rest day → public holiday. Sundays start as rest days. Mark every public holiday of the month.") }),
    el("p", { class: "legend day-key" }, t("Colours:"),
      ...DAY_ORDER.map((k) => el("span", {}, el("span", { class: `swatch day ${k}`, "aria-hidden": "true" }),
        t({ work: "white = working day", rest: "grey = rest day", holiday: "yellow = public holiday" }[k])))),
    grid, el("p", { id: "pr-days-summary", class: "legend" }));
  renderDaysSummary();
}

function paintDay(btn, d) {
  const { y, m } = monthParts();
  const type = pr.plan.day_types[String(d)];
  btn.className = `day ${type}`;
  btn.replaceChildren(String(d), el("small", { text: t(WEEKDAYS[new Date(y, m - 1, d).getDay()]) }));
  btn.title = t("{d}: {w} (click to change)", { d, w: DAY_WORDS[type] });
  btn.setAttribute("aria-label", t("Day {d}, {w}. Click to change.", { d, w: DAY_WORDS[type] }));
}

function renderDaysSummary() {
  const counts = { work: 0, rest: 0, holiday: 0 };
  Object.values(pr.plan.day_types).forEach((k) => { counts[k] += 1; });
  const node = $("pr-days-summary");
  if (node) node.textContent = tn(counts.holiday, "{w} working days, {r} rest days, {h} public holiday.", "{w} working days, {r} rest days, {h} public holidays.", { w: counts.work, r: counts.rest, h: counts.holiday });
}

// ---------------------------------------------------------------------------------------------------------- employees
function newEmployeeId() { return "e" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

const prCompany = {};   // employee id -> company chosen in their file picker (screen only, not saved)

// The company an employee's picker starts on: the company of the files already ticked, if they share one.
function startCompany(e) {
  const docOf = (ref) => pr.documents.find((d) => d.id === ref || (d.parts || []).some((p) => p.ref === ref)) || {};
  const of = new Set(e.jobs.map((ref) => docOf(ref).company).filter(Boolean));
  return of.size === 1 ? [...of][0] : "";
}

// What can be ticked: each document, each page of a document whose pages show different workers, or each worker's
// row of a month grid that lists several workers.
function partName(d, p) {
  if (!p.row) return t("{name} — page {n}: {who}", { name: d.name, n: p.page, who: p.label || "?" });
  const who = p.label || t("name unclear");
  return d.parts.some((q) => q.page !== p.page)
    ? t("{name} — page {n}, row {r}: {who}", { name: d.name, n: p.page, r: p.row, who })
    : t("{name} — row {r}: {who}", { name: d.name, r: p.row, who });
}

function payrollChoices() {
  const ticked = (ref) => pr.plan.employees.some((x) => x.jobs.includes(ref));
  const out = [];
  pr.documents.forEach((d) => {
    const doc = { id: d.id, base: d.id, whole: true, company: d.company, name: d.name };
    if (!(d.parts && d.parts.length)) { out.push(doc); return; }
    d.parts.forEach((p) => out.push({ id: p.ref, base: d.id, whole: false, company: d.company, name: partName(d, p) }));
    if (ticked(d.id)) out.push(doc);                         // chosen whole before: still shown so it can be unticked
  });
  return out;
}

// --- the Company chosen in the top bar (app.js: companyFilter, companyMatches) decides which employees are shown
const chosenCompany = () => (companyFilter && companyFilter !== NO_COMPANY ? companyFilter : "");
// the employee's company: set on the employee, else the one company of their ticked files (as payroll.employee_company)
function empCompany(e) { return e.company || startCompany(e); }
function visibleIndexes() {
  return pr.plan.employees.map((e, i) => (companyMatches(empCompany(e)) ? i : -1)).filter((i) => i >= 0);
}

function renderAutoCompany() {
  const c = chosenCompany();
  $("pr-auto-company").textContent = companyFilter === NO_COMPANY ? t("Choose a company at the top (or “All companies”).")
    : c ? t("for {c}", { c }) : t("for all companies");
  $("pr-auto").disabled = companyFilter === NO_COMPANY;
}

// Called by app.js when the Company at the top changes while this screen is open.
function payrollCompanyChanged() {
  prShowInfo("");
  renderAutoCompany(); renderEmployees(); renderResults();
}

function prShowInfo(message) {
  const box = $("pr-info");
  box.hidden = !message; box.textContent = message || "";
}

function renderEmployees() {
  const used = {}, wholeBy = {}, partsBy = {};
  const choices = payrollChoices();
  const baseOf = Object.fromEntries(choices.map((c) => [c.id, c]));
  pr.plan.employees.forEach((e) => e.jobs.forEach((j) => {
    used[j] = e;
    const c = baseOf[j];
    if (c) (c.whole ? wholeBy : partsBy)[c.base] = e;
  }));
  const companies = [...new Set(pr.documents.map((d) => d.company).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const list = pr.plan.employees.map((e, i) => {
    if (!companyMatches(empCompany(e))) return null;            // another company: hidden, not removed
    const filter = el("input", { type: "text", placeholder: t("Find a file…"), "aria-label": t("Find a file"), style: "flex:1 1 200px" });
    if (!(e.id in prCompany)) prCompany[e.id] = empCompany(e) || chosenCompany();
    if (prCompany[e.id] && prCompany[e.id] !== NO_COMPANY && !companies.includes(prCompany[e.id])) prCompany[e.id] = "";
    const company = el("select", { "aria-label": t("Show files of company") },
      el("option", { value: "", text: t("All companies") }),
      ...companies.map((c) => el("option", { value: c, text: c, selected: prCompany[e.id] === c })),
      el("option", { value: NO_COMPANY, text: t("No company yet"), selected: prCompany[e.id] === NO_COMPANY }));
    company.addEventListener("change", () => { prCompany[e.id] = company.value; paintDocs(); });
    const docs = el("div", { class: "docs" });
    const paintDocs = () => {
      const q = filter.value.trim().toLowerCase();
      const c = prCompany[e.id];
      const fits = (d) => (!q || d.name.toLowerCase().includes(q))
        && (!c || (c === NO_COMPANY ? !d.company : d.company === c));
      const items = choices.filter((d) => fits(d) || e.jobs.includes(d.id)).map((d) => {
        // taken by another employee, or the whole document / one of its pages is already chosen
        const clash = d.whole ? partsBy[d.base] : wholeBy[d.base];
        const other = (used[d.id] && used[d.id] !== e) ? used[d.id] : (!e.jobs.includes(d.id) && clash) || null;
        const box = el("input", { type: "checkbox", checked: e.jobs.includes(d.id), disabled: !!other });
        box.addEventListener("change", () => {
          e.jobs = box.checked ? [...e.jobs, d.id] : e.jobs.filter((j) => j !== d.id);
          schedulePayrollSave(); renderEmployees();
        });
        const who = other ? t(" (used for {who})", { who: other.emp_no || other.name || t("another employee") }) : "";
        return el("label", { class: other ? "used" : "" }, box, `${d.name}${who}`);
      });
      docs.replaceChildren(...(items.length ? items : [el("span", { class: "muted", text: pr.documents.length ? t("No file matches.") : t("No finished files yet. Read your time cards on the start page first.") })]));
    };
    filter.addEventListener("input", paintDocs);
    paintDocs();

    const empNo = el("input", { type: "text", value: e.emp_no, placeholder: t("e.g. MJ(1)"), maxlength: "100" });
    const name = el("input", { type: "text", value: e.name, placeholder: t("Name as in Million Payroll"), maxlength: "100" });
    empNo.addEventListener("input", () => { e.emp_no = empNo.value; schedulePayrollSave(); });
    name.addEventListener("input", () => { e.name = name.value; schedulePayrollSave(); });
    const columns = (pr.results[i] && pr.results[i].columns) || [];
    const colSel = el("select", { "aria-label": t("Column with the daily hours") },
      el("option", { value: "", text: t("Automatic (the Total column)") }),
      ...columns.map((c) => el("option", { value: c, text: c, selected: e.hours_column === c })));
    colSel.addEventListener("change", () => { e.hours_column = colSel.value || null; schedulePayrollSave(); });
    const remove = el("button", { type: "button", text: t("Remove employee") });
    remove.addEventListener("click", () => {
      if (!confirm(t("Remove this employee from the payroll? Their documents are not deleted."))) return;
      pr.plan.employees.splice(i, 1); pr.results.splice(i, 1);
      schedulePayrollSave(); renderEmployees(); renderResults();
    });
    return el("div", { class: "emp" },
      el("div", { class: "row" }, el("label", {}, t("Employee No."), empNo), el("label", {}, t("Name"), name),
        el("label", {}, t("Hours column"), colSel), remove),
      el("div", { class: "legend", text: t("Time-card files for this employee (tick every card of the month):") }),
      el("div", { class: "pick-bar" }, el("label", {}, t("Company "), company), filter), docs);
  }).filter(Boolean);
  const empty = pr.plan.employees.length
    ? t("No employees for this company yet. Press “Add employees from files” or “Add employee”.")
    : t("No employees yet. Press “Add employee”.");
  $("pr-employees").replaceChildren(...(list.length ? list : [el("p", { class: "muted", text: empty })]));
}

// ------------------------------------------------------------------------------------------------------------ results
function fmt(v) { return (Math.round(v * 100) / 100).toFixed(2); }

let prIndex = 0;       // which employee the Results window shows

const OT_ROWS = [["1 Time", "Hour", "ot_1"], ["1.5 Times", "Hour", "ot_1_5"], ["2 Times", "Hour", "ot_2"],
  ["3 Times (Overtime on Holiday)", "Hour", "ot_3"], ["1 Time (Work on Rest Day)", "Day", "ot_rest_day"],
  ["2 Times (Work on Holiday)", "Day", "ot_holiday"]];

// One figure box. Typing over a worked-out figure saves it as the user's own figure (blue edge) until reset.
function figureInput(i, r, key) {
  const e = pr.plan.employees[i];
  const v = r.values[key];
  const input = el("input", { type: "number", min: "0", step: "0.01", value: fmt(v.value), id: `f-${i}-${key}`, class: v.edited ? "edited" : "" });
  input.addEventListener("change", () => {
    if (input.value === "" || Math.abs(Number(input.value) - v.computed) < 0.005) delete e.overrides[key];
    else e.overrides[key] = Number(input.value);
    schedulePayrollSave();
  });
  return input;
}

function resetLink(i, r, key) {
  const v = r.values[key];
  if (!v.edited) return null;
  const e = pr.plan.employees[i];
  const b = el("button", { type: "button", class: "reset", text: t("Worked out: {v} – use it", { v: fmt(v.computed) }) });
  b.addEventListener("click", () => { delete e.overrides[key]; schedulePayrollSave(); });
  return b;
}

function labelledRow(i, r, key, label, unit, bold) {
  const input = figureInput(i, r, key);
  return el("div", { class: "pf" }, el("label", { for: input.id, class: bold ? "b" : "", text: label }), input,
    el("span", { class: "unit", text: unit || "" }), resetLink(i, r, key));
}

// --- company lines (Leave, Allowance, Deduction, BIK): the same lines for every employee, a figure per employee
let prTab = "basic";   // which tab of the results window is open

function entryInput(i, kind, name, n) {
  const e = pr.plan.employees[i];
  e.entries = e.entries || {};
  const v = (e.entries[kind] || {})[name] || 0;
  const input = el("input", { type: "number", min: "0", step: "0.01", value: fmt(v), id: `x-${i}-${kind}-${n}`,
    "aria-label": t("{name} for this employee", { name }) });
  input.addEventListener("change", () => {
    const num = Number(input.value);
    const list = (e.entries[kind] = e.entries[kind] || {});
    if (input.value === "" || !(num > 0)) { delete list[name]; input.value = fmt(0); } else list[name] = num;
    schedulePayrollSave();
  });
  return input;
}

function removeLine(kind, name) {
  const used = pr.plan.employees.filter((e) => ((e.entries || {})[kind] || {})[name]).length;
  const warn = used ? tn(used, " {n} employee has a figure on it this month; it will be cleared.", " {n} employees have a figure on it this month; it will be cleared.") : "";
  if (!confirm(t("Remove “{name}” from the list for every employee?", { name }) + warn)) return;
  pr.plan.lists[kind] = pr.plan.lists[kind].filter((l) => l.name !== name);
  pr.plan.employees.forEach((e) => { if (e.entries && e.entries[kind]) delete e.entries[kind][name]; });
  schedulePayrollSave(); renderResults();
}

// A Million Payroll style table: name | type | the employee's figure (| Balance for leave), with "Add a line" under it.
function linesTable(i, kind) {
  const heads = pr.list_heads[kind];
  const lines = pr.plan.lists[kind];
  const isLeave = kind === "leave";
  const rows = lines.map((l, n) => {
    const del = el("button", { type: "button", class: "del", text: "×", title: t("Remove “{name}” from the list", { name: l.name }), "aria-label": t("Remove {name}", { name: l.name }) });
    del.addEventListener("click", () => removeLine(kind, l.name));
    return el("tr", {}, el("td", {}, el("label", { for: `x-${i}-${kind}-${n}`, text: l.name })), el("td", { text: l.type }),
      el("td", { class: "n" }, entryInput(i, kind, l.name, n)),
      isLeave ? el("td", { class: "n" }, el("input", { disabled: true, placeholder: "—", title: t("Leave balance is kept in Million Payroll"), "aria-label": t("{name} balance (kept in Million Payroll)", { name: l.name }) })) : null,
      el("td", { class: "x" }, del));
  });
  if (!rows.length) rows.push(el("tr", {}, el("td", { colspan: isLeave ? "5" : "4", class: "muted", text: t("No lines yet.") })));

  const name = el("input", { type: "text", placeholder: t("Name, exactly as in Million Payroll"), maxlength: "80", "aria-label": t("New {title} line", { title: heads.title }) });
  const type = isLeave
    ? el("select", { "aria-label": heads.type }, el("option", { text: "Pay Leave" }), el("option", { text: "Non Pay Leave" }))
    : el("input", { type: "text", value: kind === "deduction" ? "" : "Ordinary", placeholder: heads.type, maxlength: "60", "aria-label": heads.type });
  const add = el("button", { type: "button", text: t("Add") });
  const addLine = () => {
    const n = name.value.trim();
    if (!n) { name.focus(); return; }
    if (lines.some((l) => l.name.toLowerCase() === n.toLowerCase())) { prShowError(t("“{n}” is already in the {title} list.", { n, title: heads.title })); return; }
    prShowError("");
    lines.push({ name: n, type: type.value.trim() });
    schedulePayrollSave(); renderResults();
  };
  add.addEventListener("click", addLine);
  name.addEventListener("keydown", (ev) => { if (ev.key === "Enter") addLine(); });
  const adder = el("details", { class: "addline" }, el("summary", { text: t("+ Add a {what} line", { what: t(kind === "bik" ? "benefit" : heads.title.toLowerCase()) }) }),
    el("div", { class: "row" }, name, type, add),
    el("p", { class: "legend", text: t("The line is added for every employee. Use the same name as in Million Payroll so the import matches.") }));

  return el("div", {},
    el("table", { class: "pw-table lines" },
      el("thead", {}, el("tr", {}, el("th", { text: heads.title }), el("th", { text: heads.type }),
        el("th", { text: isLeave ? "Taken" : "Rate" }), isLeave ? el("th", { text: "Balance" }) : null, el("th", { class: "x" }))),
      el("tbody", {}, ...rows)),
    adder);
}

function moneyBox(i, key, label) {
  const e = pr.plan.employees[i];
  const input = el("input", { type: "number", min: "0", step: "0.01", value: fmt(e[key] || 0), id: `u-${i}-${key}` });
  input.addEventListener("change", () => {
    const num = Number(input.value);
    e[key] = num > 0 ? num : 0; input.value = fmt(e[key]);
    schedulePayrollSave();
  });
  return el("div", { class: "pf" }, el("label", { for: input.id, text: label }), input, el("span"));
}

function allowanceTab(i) {
  const e = pr.plan.employees[i];
  const msg = el("textarea", { id: `m-${i}`, rows: "4", maxlength: "2000", "aria-label": "Message", text: e.message || "" });
  msg.addEventListener("input", () => { e.message = msg.value; schedulePayrollSave(); });
  return el("div", { class: "pw-two" },
    el("div", {}, linesTable(i, "allowance"), el("div", { class: "gap" }), linesTable(i, "bik")),
    el("div", {}, linesTable(i, "deduction"),
      el("div", { class: "pw-user" }, el("div", { class: "pw-sub", text: "User Defined Entry" }),
        moneyBox(i, "zakat", "Zakat paid by individual"), moneyBox(i, "levy", "Levy paid by individual"),
        el("label", { for: msg.id, class: "b", text: "Message" }), msg)));
}

// A clock-system report's figures for one day, named as on the Edit Payroll screen: "Lateness 0.25, OT 1.5 2.00"
const PRINTED_NAMES = { lateness: "Lateness", early_departure: "Early Departure", ot_1: "OT 1", ot_1_5: "OT 1.5", ot_2: "OT 2", ot_3: "OT 3" };
function printedText(p) {
  return Object.entries(p).map(([k, v]) => `${PRINTED_NAMES[k] || k} ${fmt(v)}`).join(", ");
}

// How a day's hours were worked out from the IN and OUT times of a time card
function clockText(c) {
  if (!c) return "";
  if (c.pairs > 1) return t("{h} hours: the IN/OUT pairs added up, no break taken off", { h: fmt(c.hours) });
  return c.break ? t("{h} hours: OUT minus IN, less {b} for the break", { h: fmt(c.hours), b: fmt(c.break) })
    : t("{h} hours: OUT minus IN, no break taken off", { h: fmt(c.hours) });
}

function renderResults() {
  const host = $("pr-results");
  const vis = visibleIndexes().filter((k) => k < pr.results.length);   // only the chosen company's employees
  $("pr-download").disabled = vis.length === 0;
  $("pr-download-xls").disabled = vis.length === 0;
  if (!vis.length) {
    host.replaceChildren(el("p", { class: "muted", text: t("Results appear here once you add an employee.") }));
    return;
  }
  if (!vis.includes(prIndex)) prIndex = vis.find((k) => k >= prIndex) ?? vis[vis.length - 1];
  const pos = vis.indexOf(prIndex);
  const i = prIndex, r = pr.results[i];
  const { y, m } = monthParts();

  // Employee No. and Name can be typed here too: the same two boxes as in section 2 (which follows after the save).
  const e = pr.plan.employees[i];
  const idBox = (id, key, label, placeholder) => {
    const input = el("input", { type: "text", id, value: e[key], placeholder, maxlength: "100" });
    input.addEventListener("input", () => { e[key] = input.value; schedulePayrollSave(); });
    return el("div", { class: "pw-id" }, el("label", { for: id, text: label }), input);
  };
  const head = el("div", { class: "pw-head" },
    el("div", { class: "pw-ids" },
      idBox("pw-empno", "emp_no", "Employee No.", t("e.g. MJ(1)")),
      idBox("pw-name", "name", "Name", t("Name as in Million Payroll"))),
    el("div", { class: "pw-month", text: `Month End Pay - ${MONTH_NAMES[m - 1]}, ${y}` }),
    el("span", { class: r.complete ? "pill good" : "pill check", text: r.complete ? t("Complete") : t("Needs checking") }));

  const basic = el("div", { class: "pw-panel" },
    el("div", { class: "pf" }, el("label", { class: "b", text: "Basic Rate" }), el("input", { disabled: true, placeholder: "—", "aria-label": "Basic Rate (kept in Million Payroll)" }), el("span", { class: "unit b", text: "Monthly" })),
    el("div", { class: "pf" }, el("label", { text: "Director Fee" }), el("input", { disabled: true, placeholder: "—", "aria-label": "Director Fee (kept in Million Payroll)" })),
    el("div", { class: "pf" }, el("label", { text: "Back Pay" }), el("input", { disabled: true, placeholder: "—", "aria-label": "Back Pay (kept in Million Payroll)" })),
    el("p", { class: "legend", text: t("Not on a time card: keep these in Million Payroll.") }));
  const days = el("div", { class: "pw-panel" },
    labelledRow(i, r, "working_days", "Working Days", "", true), labelledRow(i, r, "public_holiday", "Public Holiday", ""),
    labelledRow(i, r, "days_worked", "Days Worked", "", true), labelledRow(i, r, "hours_worked", "Hours of Worked", ""));
  const time = el("div", { class: "pw-panel" },
    labelledRow(i, r, "lateness", "Lateness", "Hour(s)"), labelledRow(i, r, "early_departure", "Early Departure", "Hour(s)"),
    labelledRow(i, r, "no_pay_hour", "No Pay Hour", "Hour(s)"), labelledRow(i, r, "encashing_leave", "Encashing Leave", "Day(s)"));

  const otRows = OT_ROWS.map(([label, unit, key]) => {
    const input = figureInput(i, r, key);
    return el("tr", {}, el("td", {}, el("label", { for: input.id, text: label })), el("td", { class: "c", text: unit }),
      el("td", { class: "n" }, input, resetLink(i, r, key)));
  });
  const otTable = el("table", { class: "pw-table" },
    el("thead", {}, el("tr", {}, el("th", { text: "Overtime" }), el("th", { text: "Unit" }), el("th", { text: "Hrs/Days" }))),
    el("tbody", {}, ...otRows));

  const issues = r.issues.length
    ? el("div", { class: "issues" }, el("strong", { text: t("Please check:") }), el("ul", {}, ...r.issues.map((x) => el("li", { text: tm(x.text) }))))
    : el("p", { class: "legend", text: t("Nothing to check for this employee.") });
  const dayRows = r.days.map((d) => el("tr", { class: d.status === "ok" || (d.status === "missing" && d.type === "rest") ? "" : "bad" },
    el("td", { text: String(d.day) }), el("td", { text: DAY_WORDS[d.type] }),
    el("td", { text: d.code ?? (d.hours === null ? "" : String(d.hours)) }),       // a grid mark (✓, PH…) or the hours
    el("td", { text: STATUS_WORDS[d.status] || (d.printed ? t("From the report: {x}", { x: printedText(d.printed) }) : clockText(d.clock)) })));
  const details = el("details", {}, el("summary", { text: t("Day by day (how the figures were worked out)") }),
    el("table", { class: "daytable" }, el("thead", {}, el("tr", {}, ...["Day", "Type", "Written on the card", "Note"].map((h) => el("th", { text: t(h) })))), el("tbody", {}, ...dayRows)));

  const go = (n) => { prIndex = n; renderResults(); };
  const last = vis.length - 1;                                  // First/Previous/Next/Last move within the shown company
  const navBtn = (text, target, disabled) => {
    const b = el("button", { type: "button", text, disabled });
    b.addEventListener("click", () => go(vis[target]));
    return b;
  };
  const foot = el("div", { class: "pw-foot" },
    el("div", { class: "pw-nav" }, navBtn("⏮ First", 0, pos === 0), navBtn("◀ Previous", pos - 1, pos === 0),
      el("span", { class: "muted", text: t("Employee {a} of {b}", { a: pos + 1, b: vis.length }) }),
      navBtn("Next ▶", pos + 1, pos === last), navBtn("Last ⏭", last, pos === last)),
    el("span", { class: "muted", text: t("Changes are saved automatically.") }));

  const tab = (key, text) => {
    const b = el("button", { type: "button", role: "tab", class: prTab === key ? "tab active" : "tab", "aria-selected": String(prTab === key), text });
    b.addEventListener("click", () => { prTab = key; renderResults(); });
    return b;
  };
  const body = prTab === "allow"
    ? allowanceTab(i)
    : el("div", {}, el("div", { class: "pw-panels" }, basic, days, time),
      el("div", { class: "pw-lower" }, el("div", {}, linesTable(i, "leave")), el("div", {}, otTable)),
      el("div", { class: "pw-check" }, issues, details));

  host.replaceChildren(el("div", { class: "pw" },
    el("div", { class: "pw-title", text: `Edit Payroll # ${e.emp_no || "(no Employee No.)"} - ${e.name}` }),
    head,
    el("div", { class: "pw-tabs", role: "tablist" }, tab("basic", "Basic Pay & Overtime"), tab("allow", "Allowance & Deduction")),
    el("div", { class: "pw-body" }, body),
    foot));
}

function renderPayroll() {
  renderMonth(); renderAutoCompany(); renderEmployees(); renderResults();
  setSaveState("");
}

// ------------------------------------------------------------------------------------------------------------ buttons
$("pr-back").addEventListener("click", async () => { await savePayroll(); location.hash = ""; });
$("nav-payroll").addEventListener("click", () => { if (location.hash.startsWith("#/payroll")) route(); });
$("pr-add").addEventListener("click", () => {
  const prev = pr.plan.employees[pr.plan.employees.length - 1];
  const id = newEmployeeId();
  if (prev && prCompany[prev.id]) prCompany[id] = prCompany[prev.id];   // usually the next worker of the same company
  pr.plan.employees.push({ id, emp_no: "", name: "", jobs: [], hours_column: null, overrides: {},
    entries: {}, zakat: 0, levy: 0, message: "", company: chosenCompany() });   // stays under the company chosen above
  prIndex = pr.plan.employees.length - 1;                      // show the new employee in the results window
  schedulePayrollSave(); renderEmployees(); renderResults();
});
$("pr-auto").addEventListener("click", async () => {
  if (!(await savePayroll())) return;                        // keep what was typed before adding
  const btn = $("pr-auto");
  btn.disabled = true; prShowInfo("");
  try {
    const view = await api("POST", payrollUrl("/auto"), { company: chosenCompany() });
    pr = view; prDirty = false;
    const { added, skipped } = view.auto;
    const unnamed = view.auto.unnamed || [];
    const parts = [added ? tn(added, "Added {n} employee.", "Added {n} employees.")
      : t("No new workers found: every readable file is already chosen for an employee.")];
    if (skipped.length) {
      parts.push(tn(skipped.length,
        "{n} file was left out because Table Reader cannot work out the days from it yet (for example IN/OUT cards):",
        "{n} files were left out because Table Reader cannot work out the days from them yet (for example IN/OUT cards):"),
      skipped.join("; "));
    }
    if (unnamed.length) {
      parts.push(tn(unnamed.length,
        "{n} worker row was left out because the name in it is unclear (fix the name in the document, or tick the row for the right employee yourself):",
        "{n} worker rows were left out because the names in them are unclear (fix the names in the document, or tick the rows for the right employees yourself):"),
      unnamed.join("; "));
    }
    if (added) parts.push(t("Type the Employee No. where it is empty; it is remembered for next month."));
    prShowInfo(parts.join(" "));
    prIndex = Math.max(0, pr.plan.employees.length - added);   // show the first new employee
    renderPayroll();
  } catch (e) { prShowError(e.message); }
  renderAutoCompany();
});
$("pr-download").addEventListener("click", async () => {
  if (!(await savePayroll())) return;
  const unfinished = visibleIndexes().filter((k) => pr.results[k] && !pr.results[k].complete).length;
  if (unfinished && !confirm(tn(unfinished, "{n} employee is marked \"Needs checking\". In the file they are marked INCOMPLETE in the Notes column. Download anyway?", "{n} employees are marked \"Needs checking\". In the file they are marked INCOMPLETE in the Notes column. Download anyway?"))) return;
  const c = chosenCompany();                                   // only the company chosen at the top, if one is
  location.href = payrollUrl("/csv") + (c ? `?company=${encodeURIComponent(c)}` : "");
});

// The Million import file (.xls) for the office. Fetched rather than opened as a link, so that a refusal (what would
// import wrong, listed one problem per line) is shown on this page; Employee Nos. that are not in employees.txt and
// INCOMPLETE employees only after the user agrees (each is asked once).
const MILLION_ASKS = { MILLION_UNKNOWN: "allow_unknown", MILLION_INCOMPLETE: "allow_incomplete" };
async function downloadMillion(allowed = []) {
  const q = new URLSearchParams();
  const c = chosenCompany();
  if (c) q.set("company", c);
  for (const a of allowed) q.set(a, "true");
  let res;
  try { res = await fetch(payrollUrl("/xls") + (q.toString() ? `?${q}` : "")); }
  catch { prShowError(t("Table Reader is not running any more. Close this tab and open Table Reader again.")); return; }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    const ask = data && MILLION_ASKS[data.code];
    if (ask && !allowed.includes(ask)) {
      if (confirm(tm(data.message) + "\n\n" + t("Make the Million file anyway?"))) await downloadMillion([...allowed, ask]);
      return;
    }
    prShowError(data && data.message ? tm(data.message) : t("Something went wrong. Reload the page and try again."));
    return;
  }
  const blob = await res.blob();
  const m = /filename\*=utf-8''([^;]+)|filename="?([^";]+)"?/i.exec(res.headers.get("content-disposition") || "");
  const name = m ? decodeURIComponent(m[1] || m[2]) : "Payroll (Million).xls";
  const a = el("a", { href: URL.createObjectURL(blob), download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 30000);
  prShowError("");
  prShowInfo(t("Million file made: {name}. A copy is kept in Documents\\Table Reader\\payroll. Back up Million before you import it. Million only updates employees who are already in that month's payroll (Transaction > Payroll > Edit).", { name }));
}

$("pr-download-xls").addEventListener("click", async () => {
  if (!(await savePayroll())) return;
  const btn = $("pr-download-xls");
  btn.disabled = true;
  try { await downloadMillion(); } finally { btn.disabled = false; }
});

if (location.hash.startsWith("#/payroll")) route();      // the page was opened on this screen: app.js ran before this file
