"use strict";
// What the payroll screens share: month and day words, the figure format, the Results window's tables, the messages
// about files added by themselves and about the month's Million file. Loaded after app.js (uses $, el, t/tn/tm) and
// before every payroll screen; a top-level const may be declared in one script only.

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAY_ORDER = ["work", "rest", "holiday"];
const DAY_WORDS = { work: t("Working day"), rest: t("Rest day"), holiday: t("Public holiday") };
const STATUS_WORDS = { ok: "", unclear: t("unclear: fix it in the document"), conflict: t("written twice, differs"), missing: t("no entry") };

function defaultPayrollMonth() {
  const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1);          // payroll is usually for last month
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthTitle(month) {
  const [y, m] = month.split("-").map(Number);
  return `${t(MONTH_NAMES[m - 1])} ${y}`;
}

function shiftMonth(month, by) {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + by, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Files read since the last visit that went into this month's payroll by themselves (the month is printed in the
// file name or on the card), and the ones that could not be put in a month.
function addedByThemselves(info) {
  if (!info) return "";
  const cards = (list) => list.map((a) => `${a.name} (${tn(a.cards, "{n} file", "{n} files")})`).join("; ");
  const parts = [];
  if (info.added.length) parts.push(t("Added by themselves from newly read files of this month: {list}.", { list: cards(info.added) }));
  if (info.joined.length) parts.push(t("Newly read files added to: {list}.", { list: cards(info.joined) }));
  if (info.skipped.length) {
    parts.push(tn(info.skipped.length, "{n} newly read file was not added because Table Reader cannot work out the days from it yet:",
      "{n} newly read files were not added because Table Reader cannot work out the days from them yet:"), info.skipped.join("; "));
  }
  if (info.unnamed.length) {
    parts.push(tn(info.unnamed.length,
      "{n} worker row was left out because the name in it is unclear (fix the name in the document, or tick the row for the right employee yourself):",
      "{n} worker rows were left out because the names in them are unclear (fix the names in the document, or tick the rows for the right employees yourself):"),
    info.unnamed.join("; "));
  }
  if (info.no_month.length) {
    parts.push(tn(info.no_month.length, "{n} newly read file was not put in a payroll month, so tick it for an employee yourself:",
      "{n} newly read files were not put in a payroll month, so tick them for an employee yourself:"),
    info.no_month.map((f) => `${f.name} (${tm(f.why)})`).join("; "));
  }
  if (info.added.length) parts.push(...employeeNoHint(info.from_million, info.new_numbers));
  return parts.join(" ");
}

// After employees were made from files: how many got their Employee No. from Million's list, how many got a new one,
// and what is left to type.
function newNumbersText(n) {
  return tn(n,
    "{n} employee without an Employee No. was given a new one (the company's first 7 letters and a number). Create that employee in Million with this number before you import.",
    "{n} employees without an Employee No. were given new ones (the company's first 7 letters and a number). Create those employees in Million with these numbers before you import.");
}

// What opening a month did by itself (files that joined, new Employee Nos.). The server says it once, to whichever step
// opened the month (step 2 usually does it first), so it is kept in this tab until step 3 shows it.
function monthNotes(month) {
  try { const list = JSON.parse(recall(`notes.${month}`) || "[]"); return Array.isArray(list) ? list : []; } catch (_) { return []; }
}
function keepMonthNote(month, added, numbered) {
  if (!added && !numbered) return;
  remember(`notes.${month}`, JSON.stringify([...monthNotes(month), { added, numbered }].slice(-10)));
}
function takeMonthNotes(month) { const list = monthNotes(month); forget(`notes.${month}`); return list; }
function monthNotesText(notes) {
  return notes.flatMap((n) => [addedByThemselves(n.added), n.numbered ? newNumbersText(n.numbered) : ""]).filter(Boolean).join(" ");
}

function employeeNoHint(fromMillion, newNumbers) {
  const parts = [];
  if (newNumbers) parts.push(newNumbersText(newNumbers));
  if (fromMillion) {
    parts.push(tn(fromMillion,
      "{n} Employee No. was filled in from Million's list, because the name on the card is that employee's whole name there. Check it.",
      "{n} Employee Nos. were filled in from Million's list, because the name on the card is that employee's whole name there. Check them."));
  }
  parts.push(t("Type the Employee No. where it is empty; it is remembered for next month."));
  return parts;
}

function fmt(v) { return (Math.round(v * 100) / 100).toFixed(2); }

const OT_ROWS = [["1 Time", "Hour", "ot_1"], ["1.5 Times", "Hour", "ot_1_5"], ["2 Times", "Hour", "ot_2"],
  ["3 Times (Overtime on Holiday)", "Hour", "ot_3"], ["1 Time (Work on Rest Day)", "Day", "ot_rest_day"],
  ["2 Times (Work on Holiday)", "Day", "ot_holiday"]];

// A clock-system report's figures for one day, named as on the Edit Payroll screen: "Lateness 0.25, OT 1.5 2.00"
const PRINTED_NAMES = { lateness: "Lateness", early_departure: "Early Departure", ot_1: "OT 1", ot_1_5: "OT 1.5", ot_2: "OT 2", ot_3: "OT 3" };
function printedText(p) {
  return Object.entries(p).map(([k, v]) => `${PRINTED_NAMES[k] || k} ${fmt(v)}`).join(", ");
}

// How a day's hours were worked out from the IN and OUT times of a time card
function clockText(c) {
  if (!c) return "";
  // an OUT written without pm and earlier than IN was read as afternoon (the user's rule): say so
  const pm = (c.afternoon || []).map((out) => " " + t("(OUT {out} read as afternoon)", { out })).join("");
  if (c.pairs > 1) return t("{h} hours: the IN/OUT pairs added up, no break taken off", { h: fmt(c.hours) }) + pm;
  return (c.break ? t("{h} hours: OUT minus IN, less {b} for the break", { h: fmt(c.hours), b: fmt(c.break) })
    : t("{h} hours: OUT minus IN, no break taken off", { h: fmt(c.hours) })) + pm;
}

// A reason from the month run, translated. Some are a line of the "file was not made" list without its "- who: "
// start; those are translated as that line.
function runReason(text) {
  const line = "- \u0001: " + text, viaLine = tm(line);
  return viaLine !== line ? viaLine.replace(/^- \u0001: /, "") : tm(text);
}

// Each employee's Basic Rate is meant per month or per day (chosen by the user, as in Million's employee file).
// Daily: basic pay = rate x Days Worked. Monthly: the rate is the month's basic pay. Nothing else is turned into money.
const PAY_BASES = [["monthly", "Monthly"], ["daily", "Daily"]];
function payBasisWord(basis) { return t(basis === "daily" ? "Daily" : "Monthly"); }

// The figures of the pay table (the boxes are left alone, so one being typed in keeps its place)
const DAILY_COLUMNS = [["Days Worked", (r) => r.values.days_worked.value, false], ["Basic pay (RM)", (r) => r.pay && r.pay.basic, true],
  ["Overtime pay (RM)", (r) => r.pay && r.pay.overtime, true], ["Allowances", (r) => r.pay && r.pay.allowances, true],
  ["Deductions", (r) => r.pay && r.pay.deductions, true], ["Estimated pay (RM)", (r) => r.pay && r.pay.total, true]];

// Who the month's Million file holds back, company by company, each with the reasons (also shown before it is made).
function heldNodes(run) {
  if (!run.held) return [];
  return [el("p", {}, el("strong", { text: tn(run.held, "{n} employee is not in the file yet:", "{n} employees are not in the file yet:") })),
    ...run.companies.filter((x) => x.held.length).map((c) => el("div", { class: "run-company" }, el("strong", { text: c.company || t("No company") }),
      el("ul", {}, ...c.held.map((h) => el("li", { text: `${[h.emp_no, h.name].filter(Boolean).join(" ") || t("An employee")}: ${h.reasons.map(runReason).join(" ")}` })))))];
}

// One Million file for the whole month: everyone who can go in, and for the others the reason, company by company.
// The × that closes a message at the top of a screen.
function closeX(onclose) {
  return el("button", { type: "button", class: "banner-close", text: "×", title: t("Close"), "aria-label": t("Close"), onclick: onclose });
}

function showMonthRun(run, box) {
  const withFile = run.companies.filter((c) => c.ready).length;
  const files = run.files || (run.file ? [run.file] : []);
  const c = tn(withFile, "{n} company", "{n} companies");
  const head = !files.length ? t("No Million file was made: no employee is ready yet.")
    : files.length > 1 ? t("{n} Million files made, one per company: {names}.", { n: files.length, names: files.join("; ") })
      : run.every !== false
        ? tn(run.ready, "Million file made for the whole month: {name}, with {n} employee from {c}.", "Million file made for the whole month: {name}, with {n} employees from {c}.", { name: files[0], c })
        : tn(run.ready, "Million file made: {name}, with {n} employee from {c}.", "Million file made: {name}, with {n} employees from {c}.", { name: files[0], c });
  const parts = [closeX(() => { box.hidden = true; }), el("strong", { text: head })];
  if (files.length > 1) parts.push(el("p", { class: "legend", text: t("They are saved in {folder}. Back up Million, then import each file.", { folder: run.folder }) }));
  else if (files.length && run.every !== false) parts.push(el("p", { class: "legend", text: t("It is saved in {folder}. Back up Million, then import this one file: it covers every company.", { folder: run.folder }) }));
  else if (files.length) parts.push(el("p", { class: "legend", text: t("It is saved in {folder}. Back up Million, then import this file.", { folder: run.folder }) }));
  if (!run.checked_with_million) parts.push(el("p", { class: "legend", text: t("The Employee Nos. were not checked against Million: import Million's employee list first.") }));
  parts.push(...heldNodes(run));
  if (run.held) {
    parts.push(el("p", { class: "legend", text: t("Fix what is listed and press the button again. Each run makes the whole file again; importing it again is harmless.") }));
  } else if (files.length && run.every !== false) {
    parts.push(el("p", { class: "legend", text: t("Every employee of the month is in the file.") }));
  }
  box.replaceChildren(...parts); box.hidden = false;
  box.scrollIntoView({ block: "nearest" });
}
