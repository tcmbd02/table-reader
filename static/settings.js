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
  const grid = el("div", { class: "days" });
  for (let d = 1; d <= Object.keys(types).length; d++) {
    const btn = el("button", { type: "button" });
    btn.addEventListener("click", () => {
      types[String(d)] = DAY_ORDER[(DAY_ORDER.indexOf(types[String(d)]) + 1) % DAY_ORDER.length];
      paint(btn, d); paintSummary();
    });
    paint(btn, d);
    grid.append(btn);
  }
  paintSummary();
  const node = el("div", { class: "settings-editor" },
    el("div", { class: "row" }, el("label", {}, t("Normal hours in a working day (overtime starts after this)"), hours),
      el("label", {}, t("Break taken off IN/OUT time cards (hours)"), rest)),
    el("p", { class: "legend", text: t("Click a day to change it: working day → rest day → public holiday.") }),
    el("p", { class: "legend day-key" }, t("Colours:"),
      ...DAY_ORDER.map((k) => el("span", {}, el("span", { class: `swatch day ${k}`, "aria-hidden": "true" }),
        t({ work: "white = working day", rest: "grey = rest day", holiday: "yellow = public holiday" }[k])))),
    grid, summary);
  return { node, values: () => ({ normal_hours: Number(hours.value), break_hours: rest.value === "" ? -1 : Number(rest.value), day_types: { ...types } }) };
}

// ------------------------------------------------------------------------------------------------ month settings
function openMonthSettings() {
  const box = $("mo-settings");
  if (!box.hidden) { box.hidden = true; return; }
  if (!ppView) return;
  const editor = settingsEditor(moMonth, ppView.settings);
  const save = el("button", { type: "button", class: "primary", text: t("Save") });
  const cancel = el("button", { type: "button", text: t("Cancel"), onclick: () => { box.hidden = true; } });
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await api("PUT", `/api/payroll/${moMonth}/settings`, editor.values());
      box.hidden = true; moError("");
      await ppLoad();
    } catch (e) { moError(e.message); save.disabled = false; }
  });
  box.replaceChildren(el("h3", { text: t("Settings for {month}", { month: monthTitle(moMonth) }) }),
    el("p", { class: "legend", text: t("Every company follows these, except a company given its own settings on its screen.") }),
    editor.node, el("div", { class: "need-buttons" }, save, cancel));
  box.hidden = false;
}

$("mo-settings-open").addEventListener("click", openMonthSettings);

// ---------------------------------------------------------------------------------------------- company settings
function openCompanySettings() {
  const box = $("co-settings");
  if (!coView || !coView.settings) return;
  const s = coView.settings;
  const name = `cs-${Date.now()}`;                                    // a radio group of its own
  const follow = el("input", { type: "radio", name, checked: !s.own });
  const own = el("input", { type: "radio", name, checked: s.own });
  // a company's own set starts as a copy of the month's default
  const editor = settingsEditor(moMonth, s.own ? s : s.default);
  const keep = el("input", { type: "checkbox", checked: s.keep });
  const ownPart = el("div", { class: "own-settings" }, editor.node,
    el("label", { class: "check" }, keep, t("Use the same settings for this company next month")));
  const show = () => { ownPart.hidden = !own.checked; };
  follow.addEventListener("change", show);
  own.addEventListener("change", show);
  show();
  const save = el("button", { type: "button", class: "primary", text: t("Save") });
  const cancel = el("button", { type: "button", text: t("Cancel"), onclick: () => { box.hidden = true; } });
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await api("PUT", `/api/payroll/${moMonth}/company-settings`, own.checked
        ? { company: coCompany, own: true, keep: keep.checked, ...editor.values() } : { company: coCompany, own: false });
      box.hidden = true; coError("");
      await loadCompany();
    } catch (e) { coError(e.message); save.disabled = false; }
  });
  box.replaceChildren(el("h3", { text: t("{company} - settings for {month}", { company: coCompany, month: monthTitle(moMonth) }) }),
    ...(s.default_changed ? [el("p", { class: "banner info", text: t("The month's default was changed after this; check the calendar.") })] : []),
    el("label", { class: "check" }, follow, t("Same as the month's default")),
    el("label", { class: "check" }, own, t("This company is different:")),
    ownPart, el("div", { class: "need-buttons" }, save, cancel));
  box.hidden = false;
  box.scrollIntoView({ block: "start" });
}

// "It is right": the company's own settings stay as they are and are saved again, now on top of the current default
function keepCompanySettings(button) {
  const s = coView.settings;
  return coAct(button, () => api("PUT", `/api/payroll/${moMonth}/company-settings`, {
    company: coCompany, own: true, keep: s.keep, normal_hours: s.normal_hours, break_hours: s.break_hours, day_types: s.day_types }));
}

$("co-settings-open").addEventListener("click", () => {
  if (!$("co-settings").hidden) $("co-settings").hidden = true; else openCompanySettings();
});
