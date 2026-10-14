"use strict";
// The company panel's Pay preview table (each employee's pay basis, Basic Rate and the pay they give, worked out by the
// server) and its "Add employee". Basis and rate are saved one key at a time through the employee view's endpoint.
// Loaded after people.js and uses its helpers (moMonth, coCompany, coError, employeeHash, ...).

let ptRows = [];                     // what the server last sent (GET /pay?company=)
let ptChain = Promise.resolve();     // the saves, one after the other

async function loadPayTable() {
  const month = moMonth, company = coCompany;
  try {
    const got = await api("GET", `/api/payroll/${month}/pay?company=${encodeURIComponent(company)}`);
    if (month === moMonth && company === coCompany) { ptRows = got.rows; drawPayTable(); }
  } catch (e) { coError(e.message); }
}

// The figures DAILY_COLUMNS reads, from a pay table row.
function ptResult(row) { return { values: { days_worked: { value: row.days_worked } }, pay: row.pay }; }

function ptSave(row, changes) {
  const month = moMonth;
  ptChain = ptChain.then(async () => {
    try {
      await api("PUT", `/api/payroll/${month}/employee/${encodeURIComponent(row.id)}`, { changes });
      coError("");
    } catch (e) { coError(e.message); }
    if (month === moMonth) await loadPayTable();
  });
}

function drawPayTable() {
  const host = $("co-pay-table");
  $("co-pay-download").disabled = !ptRows.length;
  // a box being typed in keeps its place: only the figures change while the same rows are there
  const same = host.querySelectorAll("tbody tr").length === ptRows.length
    && ptRows.every((r, k) => host.querySelectorAll("tbody tr")[k].dataset.id === r.id);
  if (host.contains(document.activeElement) && same) return fillPayTable(host);
  if (!ptRows.length) { host.replaceChildren(el("p", { class: "muted", text: t("No employees for this company in this month yet.") })); return; }
  const rows = ptRows.map((r) => {
    const fromMillion = r.rate_source === "million";
    const shown = fromMillion ? r.pay_basis : (r.typed_basis || "monthly");
    const basis = el("select", { "aria-label": t("Pay basis"), disabled: fromMillion },
      ...PAY_BASES.map(([value, label]) => el("option", { value, text: t(label), selected: shown === value })));
    basis.addEventListener("change", () => ptSave(r, { pay_basis: basis.value }));
    const rate = el("input", { type: "number", min: "0", step: "0.01", value: r.typed_rate ? String(r.typed_rate) : "",
      placeholder: fromMillion ? fmt(r.basic_rate) : "0.00", style: "width:100px", "aria-label": t("Basic rate (RM)") });
    rate.addEventListener("change", () => {
      const v = rate.value === "" ? 0 : Number(rate.value);
      if (v >= 0 && v <= 100000) ptSave(r, { basic_rate: v }); else rate.value = r.typed_rate ? String(r.typed_rate) : "";
    });
    return el("tr", { "data-id": r.id }, el("td", { class: "d-who" }), el("td", {}, basis), el("td", {}, rate), el("td", { class: "d-from" }),
      ...DAILY_COLUMNS.map(() => el("td", { class: "n d-fig" })), el("td", { class: "d-state" }));
  });
  host.replaceChildren(el("table", { class: "daytable daily" },
    el("thead", {}, el("tr", {}, ...[t("Employee"), t("Pay basis"), t("Basic rate (RM)"), t("Rate from"), ...DAILY_COLUMNS.map(([label]) => t(label)), ""].map((h) => el("th", { text: h })))),
    el("tbody", {}, ...rows),
    el("tfoot", {}, el("tr", {}, el("td", { text: t("Total") }), el("td"), el("td"), el("td"), ...DAILY_COLUMNS.map(() => el("td", { class: "n d-sum" })), el("td")))));
  fillPayTable(host);
}

// The figures of the pay table (the boxes are left alone, so one being typed in keeps its place)
function fillPayTable(host) {
  const sums = DAILY_COLUMNS.map(() => 0);
  const byId = Object.fromEntries(ptRows.map((r) => [r.id, r]));
  for (const tr of host.querySelectorAll("tbody tr")) {
    const r = byId[tr.dataset.id];
    if (!r) continue;
    tr.querySelector(".d-who").textContent = [r.emp_no, r.name].filter(Boolean).join(" ") || "—";
    tr.querySelector(".d-from").textContent = r.rate_source === "million" ? "Million" : r.rate_source === "typed" ? "Table Reader" : "";
    const basis = tr.querySelector("select");
    if (basis !== document.activeElement) {
      basis.disabled = r.rate_source === "million";
      basis.value = r.rate_source === "million" ? r.pay_basis : (r.typed_basis || "monthly");
    }
    tr.querySelectorAll(".d-fig").forEach((td, k) => {
      const v = DAILY_COLUMNS[k][1](ptResult(r));
      td.textContent = v === null || v === undefined ? "" : fmt(v);
      if (DAILY_COLUMNS[k][2]) sums[k] += v || 0;
    });
    tr.querySelector(".d-state").textContent = r.complete ? "" : t("Needs checking");
    tr.className = r.complete ? "" : "bad";
  }
  host.querySelectorAll(".d-sum").forEach((td, k) => { td.textContent = DAILY_COLUMNS[k][2] ? fmt(sums[k]) : ""; });
}

$("co-pay-download").addEventListener("click", () => ptChain.then(() =>
  downloadFile(`/api/payroll/${moMonth}/basic-pay?company=${encodeURIComponent(coCompany)}`, coError)));

// An employee typed in by hand, in this company (a new Employee No. from its name), opened right away.
$("co-add").addEventListener("click", async () => {
  const button = $("co-add"), month = moMonth;
  button.disabled = true;
  try {
    const { employee } = await api("POST", `/api/payroll/${month}/employee`, { company: coCompany });
    coError(""); ppView = null;                  // step 3 asks the server again, so the list has the new employee
    location.hash = employeeHash(month, employee);
  } catch (e) { coError(e.message); }
  finally { button.disabled = false; }
});
