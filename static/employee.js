"use strict";
// The employee view inside step 3 (#/payroll/<month>/e/<employee id>): one employee's Edit Payroll window, their time
// cards (check in step 2, move to another employee, take off), the Hours column, and Remove.
// Every change goes to the server as that one key ({"changes": {key: value}}), one request after the other, so a view
// opened before another tab changed something else on the employee never undoes it. Nothing keeps a copy of the plan.
// Loaded after people.js and uses its helpers (monthTitle, employeeHash, ppDrawEmployeeNeeds, ppDrawWalk, ppRefreshSoon)
// and paycommon.js's.
// The window copies Million Payroll's Edit Payroll screen, so its labels stay in English in both languages.

let emMonth = null;         // the month ("2026-09")
let emId = null;            // the employee's id
let emView = null;          // what the server last sent (GET / PUT /employee/<id>)
let emTab = "basic";        // the tab of the window that is open
let emPane = null;          // the tab of the employee shown: "fix", "cards", "hours" or "pay" (null: emPickPane chooses)
const emPending = {};       // key -> value sent or about to be sent, shown until the server's answer has it
const emTimers = {};        // key -> timer of a text box waiting for the user to stop typing
let emChain = Promise.resolve();      // the requests, one after the other

function emUrl(suffix = "") { return `/api/payroll/${encodeURIComponent(emMonth)}${suffix}`; }
function emEmployeeUrl() { return emUrl(`/employee/${encodeURIComponent(emId)}`); }
function emError(message) { $("em-error").hidden = !message; $("em-error").textContent = message || ""; }
function emState(text) { $("em-save").textContent = text; }

// The employee as the screen shows them: what the server has, with what was typed and not answered yet on top.
function emPerson() { return { ...emView.employee, ...emPending }; }

async function showEmployee(month, id) {
  if (emView && (month !== emMonth || id !== emId)) await emFlush();     // what was typed for the last one goes first
  emMonth = month;
  emId = id;
  emView = null; emTab = "basic"; emPane = null; emPickedDay = null;
  for (const k of Object.keys(emTimers)) { clearTimeout(emTimers[k]); delete emTimers[k]; }
  for (const k of Object.keys(emPending)) delete emPending[k];
  $("em-title").textContent = monthTitle(emMonth);
  $("em-cards").hidden = true; $("em-window").replaceChildren();
  emError(""); emState("");
  await emLoad();
}

// The server's view again, after the requests before it (so an older answer never draws over a newer save).
function emLoad() {
  const month = emMonth, id = emId;
  emChain = emChain.then(async () => {
    if (month !== emMonth || id !== emId) return;
    try {
      const view = await api("GET", emEmployeeUrl());
      if (month === emMonth && id === emId) { emView = view; emError(""); emDraw(); }
    } catch (e) { if (month === emMonth && id === emId) emFail(e); }
  });
  return emChain;
}

// An employee removed in another tab: say so and show nothing that could be changed.
function emFail(e) {
  emError(e.message);
  if (e.code === "EMPLOYEE_NOT_FOUND") {             // removed in another tab: step 3 starts again from its list
    emView = null;
    $("em-cards").hidden = true; $("em-window").replaceChildren(); emState("");
    forget("place.payroll"); ppView = null;
    location.replace(`#/payroll/${emMonth}`);
  }
}

// Send some keys now (after the requests before them). The answer redraws the window.
function emSend(changes) {
  Object.assign(emPending, changes);
  emState(t("Saving…"));
  const month = emMonth, id = emId;
  emChain = emChain.then(async () => {
    if (month !== emMonth || id !== emId || !emView) return;
    try {
      const view = await api("PUT", emEmployeeUrl(), { changes });
      if (month !== emMonth || id !== emId) return;
      for (const [k, v] of Object.entries(changes)) if (emPending[k] === v) delete emPending[k];
      emView = { ...view, addable: view.addable || (emView && emView.addable) };   // a change answers without the list
      emError("");
      emState(Object.keys(emTimers).length ? t("Saving…") : t("Saved"));
      emDraw();
      ppRefreshSoon();
    } catch (e) {
      if (month !== emMonth || id !== emId) return;
      for (const [k, v] of Object.entries(changes)) if (emPending[k] === v) delete emPending[k];   // back to the server's
      emState(t("Not saved")); emFail(e);
      if (emView) emDraw();
    }
  });
  return emChain;
}

// A text box: sent 500 ms after the user stops typing.
function emLater(key, value) {
  emPending[key] = value;
  emState(t("Saving…"));
  clearTimeout(emTimers[key]);
  emTimers[key] = setTimeout(() => { delete emTimers[key]; emSend({ [key]: emPending[key] }); }, 500);
}

// Send what is still waiting for the user to stop typing, and wait for every request (before leaving the view).
function emFlush() {
  for (const key of Object.keys(emTimers)) { clearTimeout(emTimers[key]); delete emTimers[key]; emSend({ [key]: emPending[key] }); }
  return emChain;
}

// Leaving the employee (another address): what is still waiting for the user to stop typing goes now.
function emLeave() { if (emView) emFlush(); }

// After a change that is not one of the employee's keys (cards, lines): the server's view again.
async function emAct(button, action) {
  if (button) button.disabled = true;
  try { await emFlush(); await action(); await emLoad(); ppRefreshSoon(); }
  catch (e) { emFail(e); if (button) button.disabled = false; }
}

// Redraw without losing the box the user is in, nor what they typed in it and not sent yet.
function emKeepFocus(redraw) {
  const a = document.activeElement;
  const id = a && $("employee").contains(a) ? a.id : "";
  const typed = id && "value" in a && a.dataset.drawn !== undefined && a.value !== a.dataset.drawn ? a.value : null;
  const spaced = id && a.type === "text" && a.value !== a.value.trim() ? a.value : null;   // the server trims names
  let sel = null;
  try { if (id && a.selectionStart !== null) sel = [a.selectionStart, a.selectionEnd]; } catch (_) { /* number boxes */ }
  redraw();
  const again = id && $(id);
  if (!again) return;
  if (typed !== null) again.value = typed;
  else if (spaced !== null && again.value === spaced.trim()) again.value = spaced;
  again.focus();
  try { if (sel) again.setSelectionRange(sel[0], sel[1]); } catch (_) { /* number boxes */ }
}

// A box that remembers what it was drawn with (emKeepFocus keeps what was typed over it).
function emBox(props) {
  const input = el(props.tag || "input", { ...props, tag: null });
  if (props.text !== undefined) input.value = props.text;
  input.dataset.drawn = input.value;
  return input;
}

function emDraw() {
  if (!emView) return;
  const e = emPerson();
  $("em-title").textContent = `${e.name || t("An employee")} - ${emView.company || t("(no company)")} - ${monthTitle(emMonth)}`;
  $("em-million-list").replaceChildren(...(emView.million || []).map((x) => el("option", { value: x.emp_no, label: x.name })));
  if (!emPane) emPane = emPickPane(ppItemsOf(emId).length > 0);
  emKeepFocus(() => { emDrawCards(); emDrawWindow(); });
  emDrawHours();
  ppDrawEmployeeNeeds(); ppDrawWalk(); emDrawTabs();
}

// The Hours tab: four figures and the month as a calendar; a clicked day says how it was read (hours.js).
let emPickedDay = null;
function emDrawHours() {
  const r = emView.result;
  const note = el("p", { id: "cal-note", class: "legend" });
  const pick = (d) => {
    emPickedDay = d.day;
    $("em-hours").querySelectorAll(".cal .d").forEach((b) => b.classList.toggle("on", b.dataset.day === String(d.day)));
    const written = d.code ?? (d.hours === null ? "" : String(d.hours));
    note.textContent = [`${d.day} · ${DAY_WORDS[d.type]}`, written ? t("written: {x}", { x: written }) : "", emDayNote(d)].filter(Boolean).join(" · ");
  };
  $("em-hours").replaceChildren(hoursFigures(r.values), hoursCalendar(emMonth, r.days, pick), note);
  const again = r.days.find((d) => d.day === emPickedDay);
  if (again) pick(again);
}

// ------------------------------------------------------------------------------------------------ the four tabs
const EM_PANES = [["fix", "alert-triangle", "To fix", "em-needs"], ["cards", "id", "Cards", "em-cards"],
  ["hours", "clock", "Hours", "em-hours"], ["pay", "cash", "Pay", "em-pay"]];

// An employee with something to fix opens on To fix; another on the tab chosen last in this browser tab (Pay at first).
function emPickPane(hasItems) {
  if (hasItems) return "fix";
  const last = recall("em.tab");
  return ["cards", "hours", "pay"].includes(last) ? last : "pay";
}

function emShowPane(name) {
  if (name !== emPane) emFlush();                    // what was typed goes before the tab changes
  emPane = name;
  if (name !== "fix") remember("em.tab", name);
  emDrawTabs();
}

function emDrawTabs() {
  if (!emView || !emPane) return;
  const counts = { fix: ppItemsOf(emId).length, cards: emView.cards.length };
  $("em-tabs").replaceChildren(...EM_PANES.map(([key, name, label]) => el("button", { type: "button", role: "tab",
    class: "tab" + (key === emPane ? " on" : ""), "data-pane": key, "aria-selected": String(key === emPane),
    onclick: () => emShowPane(key) }, icon(name), " ", t(label), key in counts ? el("span", { class: "count", text: String(counts[key]) }) : null)));
  for (const [key, , , id] of EM_PANES) $(id).hidden = key !== emPane;
}

// ------------------------------------------------------------------------------------------- the employee's cards
function emDrawCards() {
  const e = emPerson();
  const cards = emView.cards.map((card) => {
    const off = iconButton("x", t("Take off"), { onclick: () => {
      if (!confirm(t("Take this card off the employee? It goes back to step 2 as a card whose employee is not known."))) return;
      emAct(off, () => api("POST", emUrl("/take-off"), { ref: card.ref, from: emId }));
    } });
    return el("li", { class: "card-row" }, icon("photo"),
      el("div", { class: "card-name" }, el("strong", { text: card.name || card.doc }),
        card.mapped ? el("p", { class: "legend", text: t("Read with the saved card layout: the Hours column list does not apply to this card.") }) : null),
      iconButton("eye", t("Check this card"), { onclick: () => { location.hash = `#/check/${encodeURIComponent(card.doc)}`; } }),
      iconButton("arrows-exchange", t("Move to"), { onclick: () => emMovePopup(card) }), off);
  });
  const columns = emView.result.columns || [];
  const colSel = el("select", { id: "em-hours-column", "aria-label": t("Column with the daily hours"),
    title: t("Automatic (the Total column; the IN/OUT times on days it is empty)") },
  el("option", { value: "", text: t("Automatic") }),
  ...columns.map((c) => el("option", { value: c, text: c, selected: e.hours_column === c })));
  colSel.addEventListener("change", () => emSend({ hours_column: colSel.value || null }));
  $("em-cards").replaceChildren(
    cards.length ? el("ul", { class: "card-rows" }, ...cards) : el("p", { class: "muted", text: t("This employee has no time card yet.") }),
    ...[emAddCardRow(e)].filter(Boolean),             // replaceChildren would write a missing one as "null"
    el("div", { class: "need-buttons small" }, el("label", {}, icon("table"), " ", t("Hours from:"), " ", colSel)));
  emDrawMenu();
}

// "Move to": another employee of the company, or a new one, in a pop-up.
function emMovePopup(card) {
  const target = el("select", { "aria-label": t("Move to") },
    ...emView.others.map((o) => el("option", { value: o.id, text: [o.emp_no, o.name].filter(Boolean).join(" ") || t("An employee") })),
    el("option", { value: "", text: t("A new employee") }));
  const move = el("button", { type: "button", class: "primary", text: t("Move") });
  move.addEventListener("click", () => {
    const to = target.value || null;
    closePopup();
    emAct(null, () => api("POST", emUrl("/place"), { ref: card.ref, employee: to, move: true, from: emId }));
  });
  openPopup({ title: t("Move to"), icon: "arrows-exchange", body: [el("p", { text: card.name || card.doc }), target],
    buttons: [el("button", { type: "button", text: t("Cancel"), onclick: closePopup }), move] });
}

// The More menu (…): Remove employee.
function emDrawMenu() {
  const remove = el("button", { type: "button", class: "danger", text: t("Remove employee") });
  remove.addEventListener("click", () => {
    $("em-menu").hidden = true;
    if (!confirm(t("Remove this employee from the payroll? Their documents are not deleted."))) return;
    const back = `#/payroll/${emMonth}`;
    remove.disabled = true;
    emFlush().then(() => api("DELETE", emEmployeeUrl())).then(() => { forget("place.payroll"); ppView = null; location.hash = back; })
      .catch((err) => { emFail(err); remove.disabled = false; });
  });
  $("em-menu").replaceChildren(remove);
}

// "Add a time card": any card of the employee's company that is not theirs (GET /employee/<id> lists them). One on
// another employee is moved here after a question; one of another month, set aside or with no month is first said to
// be for this month (as "It is for <month>" in step 2), so the other month does not count it too.
function emAddCardRow(e) {
  const addable = emView.addable || [];
  if (!addable.length) return null;
  const label = (k) => {
    const notes = [k.month === "none" ? t("set aside") : k.month === null ? t("no month")
      : k.month !== emMonth ? t("read as {month}", { month: monthTitle(k.month) }) : "",
    k.on ? t("now on {name}", { name: k.on.name || t("An employee") }) : ""].filter(Boolean);
    return notes.length ? `${k.name} (${notes.join(", ")})` : k.name;
  };
  const group = (title, list) => (list.length
    ? el("optgroup", { label: title }, ...list.map((k) => el("option", { value: k.ref, text: label(k) }))) : null);
  const pick = el("select", { id: "em-add", "aria-label": t("Add a time card") },
    group(t("on nobody"), addable.filter((k) => !k.on)), group(t("on another employee"), addable.filter((k) => k.on)));
  const add = el("button", { type: "button", text: t("Add") });
  add.addEventListener("click", () => {
    const card = addable.find((k) => k.ref === pick.value);
    if (!card) return;
    if (card.on && !confirm(t("Move this card from {from} to {to}?",
      { from: card.on.name || t("An employee"), to: e.name || t("this employee") }))) return;
    emAct(add, async () => {
      if (card.month !== emMonth) await api("POST", "/api/payroll/file-month", { id: card.doc, month: emMonth });
      await api("POST", emUrl("/place"), { ref: card.ref, employee: emId, ...(card.on ? { move: true, from: card.on.id } : {}) });
    });
  });
  return el("div", { class: "need-buttons" }, el("label", {}, t("Add a time card"), pick), add);
}

// ------------------------------------------------------------------------------------------------ the window
// One figure box. Typing over a worked-out figure saves it as the user's own figure (blue edge) until reset.
function emFigure(key) {
  const v = emView.result.values[key];
  const input = emBox({ type: "number", min: "0", step: "0.01", value: fmt(v.value), id: `ef-${key}`, class: v.edited ? "edited" : "" });
  input.addEventListener("change", () => {
    const overrides = { ...emPerson().overrides };
    if (input.value === "" || Math.abs(Number(input.value) - v.computed) < 0.005) delete overrides[key];
    else overrides[key] = Number(input.value);
    emSend({ overrides });
  });
  return input;
}

function emReset(key) {
  const v = emView.result.values[key];
  if (!v.edited) return null;
  const b = el("button", { type: "button", class: "reset", text: t("Worked out: {v} – use it", { v: fmt(v.computed) }) });
  b.addEventListener("click", () => { const overrides = { ...emPerson().overrides }; delete overrides[key]; emSend({ overrides }); });
  return b;
}

function emRow(key, label, unit, bold) {
  const input = emFigure(key);
  return el("div", { class: "pf" }, el("label", { for: input.id, class: bold ? "b" : "", text: label }), input,
    el("span", { class: "unit", text: unit || "" }), emReset(key));
}

// The allowance, deduction, benefit and leave lines are the same for every employee: one line is added or removed at
// a time, so a view opened before another tab added a line does not take it away.
function emSaveLine(change, button) { return emAct(button, () => api("PUT", emUrl("/lists"), change)); }

function emEntry(kind, name, n) {
  const v = ((emPerson().entries || {})[kind] || {})[name] || 0;
  const input = emBox({ type: "number", min: "0", step: "0.01", value: fmt(v), id: `ex-${kind}-${n}`,
    "aria-label": t("{name} for this employee", { name }) });
  input.addEventListener("change", () => {
    const entries = JSON.parse(JSON.stringify(emPerson().entries || {}));
    const num = Number(input.value);
    const list = (entries[kind] = entries[kind] || {});
    if (input.value === "" || !(num > 0)) delete list[name]; else list[name] = num;
    emSend({ entries });
  });
  return input;
}

function emLines(kind) {
  const heads = emView.list_heads[kind];
  const lines = emView.lists[kind];
  const isLeave = kind === "leave";
  const rows = lines.map((l, n) => {
    const del = el("button", { type: "button", class: "del", text: "×", title: t("Remove “{name}” from the list", { name: l.name }), "aria-label": t("Remove {name}", { name: l.name }) });
    del.addEventListener("click", () => {
      if (!confirm(t("Remove “{name}” from the list for every employee?", { name: l.name }) + " " + t("Any figures on it this month are cleared."))) return;
      emSaveLine({ kind, remove: l.name }, del);
    });
    return el("tr", {}, el("td", {}, el("label", { for: `ex-${kind}-${n}`, text: l.name })), el("td", { text: l.type }),
      el("td", { class: "n" }, emEntry(kind, l.name, n)),
      isLeave ? el("td", { class: "n" }, el("input", { disabled: true, placeholder: "—", title: t("Leave balance is kept in Million Payroll"), "aria-label": t("{name} balance (kept in Million Payroll)", { name: l.name }) })) : null,
      el("td", { class: "x" }, del));
  });
  if (!rows.length) rows.push(el("tr", {}, el("td", { colspan: isLeave ? "5" : "4", class: "muted", text: t("No lines yet.") })));

  const name = emBox({ type: "text", id: `en-${kind}`, placeholder: t("Name, exactly as in Million Payroll"), maxlength: "80", "aria-label": t("New {title} line", { title: heads.title }) });
  const type = isLeave
    ? el("select", { id: `et-${kind}`, "aria-label": heads.type }, el("option", { text: "Pay Leave" }), el("option", { text: "Non Pay Leave" }))
    : emBox({ type: "text", id: `et-${kind}`, value: kind === "deduction" ? "" : "Ordinary", placeholder: heads.type, maxlength: "60", "aria-label": heads.type });
  const add = el("button", { type: "button", text: t("Add") });
  const addLine = () => {
    const n = name.value.trim();
    if (!n) { name.focus(); return; }
    if (lines.some((l) => l.name.toLowerCase() === n.toLowerCase())) { emError(t("“{n}” is already in the {title} list.", { n, title: heads.title })); return; }
    emSaveLine({ kind, add: { name: n, type: type.value.trim() } }, add);
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

function emMoney(key, label) {
  const input = emBox({ type: "number", min: "0", step: "0.01", value: fmt(emPerson()[key] || 0), id: `eu-${key}` });
  input.addEventListener("change", () => { const num = Number(input.value); emSend({ [key]: num > 0 ? num : 0 }); });
  return el("div", { class: "pf" }, el("label", { for: input.id, text: label }), input, el("span"));
}

function emAllowanceTab() {
  const msg = emBox({ tag: "textarea", id: "em-msg", rows: "4", maxlength: "2000", "aria-label": "Message", text: emPerson().message || "" });
  msg.addEventListener("input", () => emLater("message", msg.value));
  return el("div", { class: "pw-two" },
    el("div", {}, emLines("allowance"), el("div", { class: "gap" }), emLines("bik")),
    el("div", {}, emLines("deduction"),
      el("div", { class: "pw-user" }, el("div", { class: "pw-sub", text: "User Defined Entry" }),
        emMoney("zakat", "Zakat paid by individual"), emMoney("levy", "Levy paid by individual"),
        el("label", { for: msg.id, class: "b", text: "Message" }), msg)));
}

// Under the Basic Rate box: where the rate comes from, and the pay preview worked out the way Million's own overtime
// tables do it (the server does the sums: payroll.pay_preview).
function emBasicPayLine() {
  const r = emView.result, pay = r.pay, m = r.million;
  const parts = [];
  if (r.rate_source === "million") {
    parts.push(el("p", { class: "legend", text: t("From Million: {basis}, Basic Rate {rate}. Type a rate here to use another.", { basis: payBasisWord(r.pay_basis), rate: fmt(r.basic_rate) }) }));
  } else if (r.rate_source === "typed" && m && m.basic_rate && (m.basic_rate !== r.basic_rate || m.pay_basis !== r.pay_basis)) {
    parts.push(el("p", { class: "legend warn", text: t("Million has {basis}, Basic Rate {rate} for this employee: not what is typed here.", { basis: payBasisWord(m.pay_basis), rate: fmt(m.basic_rate) }) }));
  }
  if (!pay) {
    parts.push(el("p", { class: "legend", text: m && m.pay_basis && !["monthly", "daily"].includes(m.pay_basis)
      ? t("In Million this employee is paid {basis}: Table Reader works out Monthly and Daily pay only.", { basis: m.pay_basis })
      : t("Type the Basic Rate and choose Monthly or Daily to see the pay.") }));
  } else {
    const row = (label, how, amount, cls) => el("tr", { class: cls || "" }, el("td", { text: label }), el("td", { class: "muted", text: how }), el("td", { class: "n", text: fmt(amount) }));
    const rows = [row(t("Basic pay"), r.pay_basis === "daily" ? `${fmt(r.basic_rate)} × ${fmt(r.values.days_worked.value)} ${t("days")}` : t("the monthly rate"), pay.basic)];
    for (const line of pay.lines) rows.push(row(line.label, `${fmt(line.quantity)} ${t(line.unit === "hour" ? "hours" : "days")} × ${fmt(line.each)}`, line.amount));
    if (pay.allowances) rows.push(row(t("Allowances"), "", pay.allowances));
    if (pay.deductions) rows.push(row(t("Deductions"), "", -pay.deductions));
    rows.push(row(t("Estimated pay before EPF, SOCSO and tax"), "", pay.total, "total"));
    parts.push(el("table", { class: "daytable pay-preview" }, el("tbody", {}, ...rows)),
      el("p", { class: "legend", text: t("Overtime as in Million's overtime tables: an hour = a day's pay ÷ 8, × 1, 1.5, 2 or 3; a Rest Day worked = a day's pay × 2; a Holiday Day worked = × 3. A day's pay = the daily rate, or the monthly rate ÷ 26. Absence, lateness and unpaid leave are not taken off.") }));
  }
  return el("div", {}, ...parts);
}

// How a day was read: the figures printed on it (a clock report, or a card layout's mapped columns) and how its IN/OUT
// times were worked out (also an OUT read as afternoon).
function emDayNote(d) {
  if (STATUS_WORDS[d.status]) return STATUS_WORDS[d.status];
  return [d.printed ? t("From the report: {x}", { x: printedText(d.printed) }) : "", clockText(d.clock)].filter(Boolean).join(" · ");
}

function emDrawWindow() {
  const e = emPerson(), r = emView.result;
  const [y, m] = emMonth.split("-").map(Number);

  // Employee No. and Name, with where the number came from while it is still the one Table Reader filled in
  const idBox = (id, key, label, placeholder) => {
    const input = emBox({ type: "text", id, value: e[key], placeholder, maxlength: "100", list: key === "emp_no" ? "em-million-list" : null });
    input.addEventListener("input", () => { emLater(key, input.value); notes(); });
    return el("div", { class: "pw-id" }, el("label", { for: id, text: label }), input);
  };
  const empNo = idBox("ew-empno", "emp_no", "Employee No.", t("e.g. MJ(1)"));
  const source = el("span", { class: "muted from-million", text: t("From Million's list (same name). Change it if this is another person.") });
  const made = el("span", { class: "muted from-million", text: t("New number made by Table Reader. Create this employee in Million with this number before you import.") });
  const notes = () => {
    const no = (emPerson().emp_no || "").trim();
    source.hidden = !(e.emp_no_million && no === e.emp_no_million);
    made.hidden = !(e.emp_no_new && no === e.emp_no_new);
  };
  notes();
  const head = el("div", { class: "pw-head" },
    el("div", { class: "pw-ids" }, empNo, idBox("ew-name", "name", "Name", t("Name as in Million Payroll"))),
    el("div", { class: "pw-month", text: `Month End Pay - ${MONTH_NAMES[m - 1]}, ${y}` }),
    el("span", { class: r.complete ? "pill good" : "pill check", text: r.complete ? t("Complete") : t("Needs checking") }));

  // Basic Rate and Monthly / Daily: what is typed here counts; while no rate is typed, Million's own are shown and used
  const fromMillion = r.rate_source === "million";
  const rateBox = emBox({ type: "number", id: "ew-rate", min: "0", step: "0.01", value: e.basic_rate ? String(e.basic_rate) : "",
    placeholder: fromMillion ? fmt(r.basic_rate) : "0.00", "aria-label": "Basic Rate" });
  rateBox.addEventListener("change", () => {
    const v = rateBox.value === "" ? 0 : Number(rateBox.value);
    if (v >= 0 && v <= 100000) emSend({ basic_rate: v }); else rateBox.value = e.basic_rate ? String(e.basic_rate) : "";
  });
  const shownBasis = fromMillion ? r.pay_basis : (e.pay_basis || "monthly");
  const basisSel = el("select", { id: "ew-basis", class: "unit b", "aria-label": "Pay Basis", disabled: fromMillion },
    ...PAY_BASES.map(([value, label]) => el("option", { value, text: label, selected: shownBasis === value })));
  basisSel.addEventListener("change", () => emSend({ pay_basis: basisSel.value }));
  const basic = el("div", { class: "pw-panel" },
    el("div", { class: "pf" }, el("label", { class: "b", for: "ew-rate", text: "Basic Rate" }), rateBox, basisSel),
    emBasicPayLine(),
    el("div", { class: "pf" }, el("label", { text: "Director Fee" }), el("input", { disabled: true, placeholder: "—", "aria-label": "Director Fee (kept in Million Payroll)" })),
    el("div", { class: "pf" }, el("label", { text: "Back Pay" }), el("input", { disabled: true, placeholder: "—", "aria-label": "Back Pay (kept in Million Payroll)" })),
    el("p", { class: "legend", text: t("Basic Rate is for the pay preview; it is not sent to Million Payroll. Director Fee and Back Pay: keep them in Million Payroll.") }));
  const days = el("div", { class: "pw-panel" },
    emRow("working_days", "Working Days", "", true), emRow("public_holiday", "Public Holiday", ""),
    emRow("days_worked", "Days Worked", "", true), emRow("hours_worked", "Hours of Worked", ""));
  const time = el("div", { class: "pw-panel" },
    emRow("lateness", "Lateness", "Hour(s)"), emRow("early_departure", "Early Departure", "Hour(s)"),
    emRow("no_pay_hour", "No Pay Hour", "Hour(s)"), emRow("encashing_leave", "Encashing Leave", "Day(s)"));

  const otRows = OT_ROWS.map(([label, unit, key]) => {
    const input = emFigure(key);
    return el("tr", {}, el("td", {}, el("label", { for: input.id, text: label })), el("td", { class: "c", text: unit }),
      el("td", { class: "n" }, input, emReset(key)));
  });
  const otTable = el("table", { class: "pw-table" },
    el("thead", {}, el("tr", {}, el("th", { text: "Overtime" }), el("th", { text: "Unit" }), el("th", { text: "Hrs/Days" }))),
    el("tbody", {}, ...otRows));

  const issues = r.issues.length
    ? el("div", { class: "issues" }, el("strong", { text: t("Please check:") }), el("ul", {}, ...r.issues.map((x) => el("li", { text: tm(x.text) }))))
    : el("p", { class: "legend", text: t("Nothing to check for this employee.") });

  const tab = (key, text) => {
    const b = el("button", { type: "button", role: "tab", class: emTab === key ? "tab active" : "tab", "aria-selected": String(emTab === key), text });
    b.addEventListener("click", () => { emTab = key; emDraw(); });
    return b;
  };
  const body = emTab === "allow"
    ? emAllowanceTab()
    : el("div", {}, el("div", { class: "pw-panels" }, basic, days, time),
      el("div", { class: "pw-lower" }, el("div", {}, emLines("leave")), el("div", {}, otTable)),
      el("div", { class: "pw-check" }, issues));

  $("em-window").replaceChildren(el("div", { class: "pw" },
    el("div", { class: "pw-title", text: `Edit Payroll # ${e.emp_no || "(no Employee No.)"} - ${e.name}` }),
    head, el("div", { class: "row" }, source, made),
    el("div", { class: "pw-tabs", role: "tablist" }, tab("basic", "Basic Pay & Overtime"), tab("allow", "Allowance & Deduction")),
    el("div", { class: "pw-body" }, body),
    el("div", { class: "pw-foot" }, el("span", { class: "muted", text: t("Changes are saved automatically.") }))));
}

// a box whose change was sent: what is in it is no longer "typed and not sent" (emKeepFocus would keep it over the answer)
$("employee").addEventListener("change", (ev) => { if (ev.target.dataset && ev.target.dataset.drawn !== undefined) ev.target.dataset.drawn = ev.target.value; });

// a tab closed or left right after typing: what is still waiting goes now
document.addEventListener("visibilitychange", () => { if (document.hidden && !$("employee").hidden) emFlush(); });

iconize($("em-more"), "dots", t("More"));
$("em-more").addEventListener("click", (ev) => { ev.stopPropagation(); $("em-menu").hidden = !$("em-menu").hidden; });
$("em-menu").addEventListener("click", (ev) => ev.stopPropagation());
document.addEventListener("click", () => { $("em-menu").hidden = true; });
