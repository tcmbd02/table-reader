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

// Task 6 replaces this with the company screen.
function showCompany(month, company) { showMonth(month); }

if (location.hash.startsWith("#/payroll")) route();      // the page was opened on a payroll screen: app.js ran before this file
