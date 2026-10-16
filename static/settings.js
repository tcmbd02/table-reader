"use strict";
// Month and company settings: normal hours, break and calendar. One editor, used by "Month settings" on the month
// bar of step 3 (the month's default) and by "Company settings" in a company's panel (follow the default, or its own
// set). Loaded after people.js and uses its state (moMonth, ppView, coCompany, coView) and helpers.

// The editor works on a copy; nothing is saved until Save is pressed. values() gives what is on the screen now.
function settingsEditor(month, start) {
  const types = { ...start.day_types };
  const [y, m] = month.split("-").map(Number);
  const hours = el("input", { type: "number", min: "1", max: "24", step: "0.25", value: String(start.normal_hours), style: "width:90px" });
  const rest = el("input", { type: "number", min: "0", max: "5", step: "0.25", value: String(start.break_hours), style: "width:90px" });
  const summary = el("p", { class: "legend" });
  const paintSummary = () => {
    const counts = { work: 0, rest: 0, holiday: 0 };
    Object.values(types).forEach((k) => { counts[k] += 1; });
    summary.textContent = tn(counts.holiday, "{w} working days, {r} rest days, {h} public holiday.",
      "{w} working days, {r} rest days, {h} public holidays.", { w: counts.work, r: counts.rest, h: counts.holiday });
  };
  const paint = (btn, d) => {
    const type = types[String(d)];
    btn.className = `day ${type}`;
    btn.replaceChildren(String(d), el("small", { text: t(WEEKDAYS[new Date(y, m - 1, d).getDay()]) }));
    btn.title = t("{d}: {w} (click to change)", { d, w: DAY_WORDS[type] });
    btn.setAttribute("aria-label", t("Day {d}, {w}. Click to change.", { d, w: DAY_WORDS[type] }));
  };
  // Rest days every week: one tick per weekday, read from the calendar (ticked: every one of its days that is not a
  // public holiday is a rest day; half-ticked: some are). Ticking makes them all rest days, unticking all working days;
  // public holidays are left as they are.
  const daysOf = (weekday) => Object.keys(types)
    .filter((d) => new Date(y, m - 1, Number(d)).getDay() === weekday && types[d] !== "holiday");
  const weekly = [1, 2, 3, 4, 5, 6, 0].map((weekday) => {
    const box = el("input", { type: "checkbox", "data-weekday": String(weekday) });
    box.addEventListener("change", () => {
      for (const d of daysOf(weekday)) types[d] = box.checked ? "rest" : "work";
      paintAll();
    });
    return { weekday, box };
  });
  const paintWeekly = () => weekly.forEach(({ weekday, box }) => {
    const days = daysOf(weekday);
    const resting = days.filter((d) => types[d] === "rest").length;
    box.checked = days.length > 0 && resting === days.length;
    box.indeterminate = resting > 0 && resting < days.length;
  });
  const grid = el("div", { class: "days" });
  const lead = (new Date(y, m - 1, 1).getDay() + 6) % 7;             // the calendar starts on Monday
  for (let k = 0; k < lead; k++) grid.append(el("span", { class: "blank", "aria-hidden": "true" }));
  const buttons = [];
  const paintAll = () => { buttons.forEach((btn, i) => paint(btn, i + 1)); paintSummary(); paintWeekly(); };
  for (let d = 1; d <= Object.keys(types).length; d++) {
    const btn = el("button", { type: "button" });
    btn.addEventListener("click", () => {
      types[String(d)] = DAY_ORDER[(DAY_ORDER.indexOf(types[String(d)]) + 1) % DAY_ORDER.length];
      paint(btn, d); paintSummary(); paintWeekly();
    });
    paint(btn, d);
    buttons.push(btn);
    grid.append(btn);
  }
  paintSummary();
  paintWeekly();
  const node = el("div", { class: "settings-editor" },
    el("div", { class: "row" },
      el("label", { class: "num", title: t("Normal hours in a working day (overtime starts after this)") }, icon("clock"), t("Normal hours"), hours),
      el("label", { class: "num", title: t("Break taken off IN/OUT time cards (hours)") }, t("Break (hours)"), rest)),
    el("p", { class: "sec", text: t("Rest days every week") }),
    el("div", { class: "weekly" },
      ...weekly.map(({ weekday, box }) => el("label", { class: "wd" }, box, el("span", { text: t(WEEKDAYS[weekday]) })))),
    el("p", { class: "sec" }, t("Days") + " ",
      el("span", { class: "muted", text: t("Click a day: working → rest → holiday") })),
    grid, summary);
  return { node, values: () => ({ normal_hours: Number(hours.value), break_hours: rest.value === "" ? -1 : Number(rest.value), day_types: { ...types } }) };
}

// ------------------------------------------------------------------------------------------------ month settings
function openMonthSettings() {
  if (!ppView) return;
  const month = moMonth;
  const editor = settingsEditor(month, ppView.settings);
  const save = el("button", { type: "button", class: "primary", text: t("Save") });
  const cancel = el("button", { type: "button", text: t("Cancel"), onclick: closePopup });
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await api("PUT", `/api/payroll/${month}/settings`, editor.values());
      closePopup(); moError("");
      await ppLoad();
    } catch (e) { popupError(e.message); save.disabled = false; }
  });
  openPopup({ title: monthTitle(month), icon: "calendar-cog", buttons: [cancel, save],
    body: [el("p", { class: "legend", text: t("Every company follows these, except a company given its own settings.") }), editor.node] });
}

$("mo-settings-open").addEventListener("click", openMonthSettings);

// ---------------------------------------------------------------------------------------------- company settings
function openCompanySettings() {
  if (!coView || !coView.settings) return;
  const s = coView.settings, month = moMonth, company = coCompany;
  const name = `cs-${Date.now()}`;                                    // a radio group of its own
  const follow = el("input", { type: "radio", name, checked: !s.own });
  const own = el("input", { type: "radio", name, checked: s.own });
  // a company's own set starts as a copy of the month's default
  const editor = settingsEditor(month, s.own ? s : s.default);
  const keep = el("input", { type: "checkbox", checked: s.keep });
  const ownPart = el("div", { class: "own-settings" }, editor.node,
    el("label", { class: "check" }, keep, t("Use the same settings for this company next month")));
  const show = () => { ownPart.hidden = !own.checked; };
  follow.addEventListener("change", show);
  own.addEventListener("change", show);
  show();
  const save = el("button", { type: "button", class: "primary", text: t("Save") });
  const cancel = el("button", { type: "button", text: t("Cancel"), onclick: closePopup });
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await api("PUT", `/api/payroll/${month}/company-settings`, own.checked
        ? { company, own: true, keep: keep.checked, ...editor.values() } : { company, own: false });
      closePopup(); coError("");
      await loadCompany();
    } catch (e) { popupError(e.message); save.disabled = false; }
  });
  openPopup({ title: t("{company} - settings for {month}", { company, month: monthTitle(month) }), icon: "calendar-cog",
    buttons: [cancel, save], body: [
      ...(s.default_changed ? [el("p", { class: "banner info", text: t("The month's default was changed after this; check the calendar.") })] : []),
      el("label", { class: "check" }, follow, t("Same as the month's default")),
      el("label", { class: "check" }, own, t("This company is different:")),
      ownPart] });
}

// "It is right": the company's own settings stay as they are and are saved again, now on top of the current default
function keepCompanySettings(button) {
  const s = coView.settings;
  return coAct(button, () => api("PUT", `/api/payroll/${moMonth}/company-settings`, {
    company: coCompany, own: true, keep: s.keep, normal_hours: s.normal_hours, break_hours: s.break_hours, day_types: s.day_types }));
}

$("co-settings-open").addEventListener("click", openCompanySettings);
