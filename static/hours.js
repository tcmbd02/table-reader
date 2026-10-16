"use strict";
// Step 3's Hours tab: the employee's month as a calendar (Monday first), each day with its hours or its mark, and four
// figures above it. Replaces the day-by-day table; clicking a day says what that table said for it. Loaded after
// paycommon.js (DAY_WORDS, STATUS_WORDS, fmt).

// One day needs a look when it was not read cleanly, except a rest day nobody worked (as the day-by-day table had it).
function dayNeedsLook(d) { return !(d.status === "ok" || (d.status === "missing" && d.type === "rest")); }

function dayMark(d) {
  if (d.code) return d.code;
  if (d.hours !== null && d.hours !== undefined) return fmt(d.hours).replace(/\.00$/, "");
  if (d.status === "missing") return d.type === "work" ? "—" : "";
  return "?";
}

// days: the calculation's rows ({day, type, status, hours, code, …}); onPick(d) when a day is clicked.
function hoursCalendar(month, days, onPick) {
  const [y, m] = month.split("-").map(Number);
  const lead = (new Date(y, m - 1, 1).getDay() + 6) % 7;
  const grid = el("div", { class: "cal" },
    ...[1, 2, 3, 4, 5, 6, 0].map((w) => el("span", { class: "wday", text: t(WEEKDAYS[w]) })),
    ...Array.from({ length: lead }, () => el("span", { class: "blank", "aria-hidden": "true" })));
  for (const d of days) {
    const word = d.type === "rest" ? t("rest") : d.type === "holiday" ? t("holiday") : "";
    grid.append(el("button", { type: "button", class: `d ${d.type}${dayNeedsLook(d) ? " bad" : ""}`, "data-day": String(d.day),
      title: `${d.day} · ${DAY_WORDS[d.type]}${STATUS_WORDS[d.status] ? ` · ${STATUS_WORDS[d.status]}` : ""}`,
      onclick: () => onPick(d) }, el("b", { text: String(d.day) }), el("span", { text: dayMark(d) || word })));
  }
  return grid;
}

// Days Worked, Hours of Worked, overtime hours (all the hour lines) and public holidays, from the employee's figures.
function hoursFigures(values) {
  const v = (key) => (values[key] ? values[key].value : 0);
  const fig = (label, value) => el("div", { class: "fig" }, el("small", { text: label }), el("b", { text: value }));
  return el("div", { class: "figs" },
    fig(t("Days worked"), fmt(v("days_worked")).replace(/\.00$/, "")),
    fig(t("Hours"), fmt(v("hours_worked")).replace(/\.00$/, "")),
    fig(t("Overtime hours"), fmt(v("ot_1") + v("ot_1_5") + v("ot_2") + v("ot_3")).replace(/\.00$/, "")),
    fig(t("Public holidays"), fmt(v("public_holiday")).replace(/\.00$/, "")));
}
