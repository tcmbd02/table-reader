"use strict";
// The column choice of a card layout, opened under the file in step 2 (#/check/<file>/columns/<page>): the user says
// once what each column means (a layout map). Claude may suggest it (text only: the headings and the shapes of the
// values), but nothing is used until the user saves it. The map is kept for every card with the same headings.
// Loaded after check.js and uses its helpers.

let lyDoc = null;          // the file the choice is opened from
let lyView = null;         // what the server sent: {doc, page, name, labels, shapes, saved, suggestion, as_read, ...}
let lySelects = [];        // per column: {label, role, unit}
let lyHours = null;        // the hours column the card's employee chose (kept by "It is right as it is")

const ROLE_WORDS = {
  date: "Date", hours: "Hours worked that day", in: "Clock in (IN)", out: "Clock out (OUT)",
  stamps: "Several clock times in one cell", lateness: "Lateness", early_departure: "Early departure",
  ot_1: "Overtime 1.0", ot_1_5: "Overtime 1.5", ot_2: "Overtime 2.0", ot_3: "Overtime 3.0", ignore: "Not used",
};
const UNIT_WORDS = { hours: "hours", minutes: "minutes", none: "—" };
const COUNTED = ["hours", "lateness", "early_departure", "ot_1", "ot_1_5", "ot_2", "ot_3"];

function lyError(message) { $("ly-error").hidden = !message; $("ly-error").textContent = message || ""; }

async function showLayout(doc, page, hours) {
  lyDoc = doc;
  lyHours = hours || null;
  $("layout").hidden = false;
  for (const id of ["ly-save", "ly-as-is", "ly-ask"]) $(id).disabled = false;   // a save made before left them off
  $("ly-title").textContent = ""; $("ly-body").hidden = true; $("ly-note").hidden = true;
  lyError("");
  $("layout").scrollIntoView({ block: "start" });
  await loadLayout(doc, page, false);
}

async function loadLayout(doc, page, ask) {
  try {
    const hours = lyHours ? `&hours=${encodeURIComponent(lyHours)}` : "";
    lyView = await api("GET", `/api/layouts?doc=${encodeURIComponent(doc)}&page=${page}${ask ? "&ask=true" : ""}${hours}`);
  } catch (e) { lyError(e.message); return; }
  drawLayout();
}

function drawLayout() {
  const v = lyView;
  $("ly-title").textContent = t("{file}: what do the columns mean?", { file: v.name });
  $("ly-body").hidden = false;
  const start = v.saved || v.suggestion || v.as_read || {};
  const note = v.saved ? t("Saved before. Change it if it is not right.")
    : v.suggestion ? t("Claude's suggestion: check every row against the card before you save.")
      : t("This is how Table Reader reads the card now. Columns marked “Not used” are left out of the payroll.");
  $("ly-note").hidden = false; $("ly-note").textContent = note;
  if (v.error) lyError(tm(v.error));
  $("ly-picture").replaceChildren(el("img", { src: `/api/jobs/${encodeURIComponent(v.doc)}/pages/${v.page}`, alt: v.name }));
  lySelects = v.labels.map((label) => {
    const chosen = start[label] || { role: "ignore", unit: "none" };
    const role = el("select", { "aria-label": t("What {column} holds", { column: label }) },
      ...v.roles.map((r) => el("option", { value: r, text: t(ROLE_WORDS[r]), selected: r === chosen.role })));
    const unit = el("select", { "aria-label": t("Unit of {column}", { column: label }) },
      ...v.units.map((u) => el("option", { value: u, text: t(UNIT_WORDS[u]), selected: u === chosen.unit })));
    const fitUnit = () => {                       // a figure is in hours or minutes; anything else has no unit
      const counted = COUNTED.includes(role.value);
      if (!counted) unit.value = "none";
      else if (unit.value === "none") unit.value = "hours";
      unit.disabled = !counted;
    };
    role.addEventListener("change", fitUnit);
    fitUnit();
    return { label, role, unit };
  });
  const sample = (label) => v.shapes.map((row) => row[label]).filter(Boolean).slice(0, 3).join("  ·  ");
  $("ly-rows").replaceChildren(el("table", { class: "daytable layout-table" },
    el("tr", {}, el("th", { text: t("Column") }), el("th", { text: t("Written like") }), el("th", { text: t("Means") }),
      el("th", { text: t("Unit") })),
    ...lySelects.map((s) => el("tr", {}, el("td", { text: s.label }), el("td", { class: "muted", text: sample(s.label) }),
      el("td", {}, s.role), el("td", {}, s.unit)))));
  $("ly-ask").hidden = Boolean(v.saved);
}

async function saveLayout(button, body) {
  button.disabled = true;
  try {
    await api("PUT", "/api/layouts", { doc: lyView.doc, page: lyView.page, ...body });
    await ckLoad();                              // the file's problems change
    backFromLayout();
  } catch (e) { lyError(e.message); button.disabled = false; }
}

function backFromLayout() { location.hash = `#/check/${encodeURIComponent(lyDoc)}`; }

$("ly-back").addEventListener("click", backFromLayout);
$("ly-ask").addEventListener("click", async () => {
  const button = $("ly-ask");
  button.disabled = true; lyError("");
  button.textContent = t("Asking Claude…");
  await loadLayout(lyView.doc, lyView.page, true);
  button.textContent = t("Ask Claude"); button.disabled = false;
});
$("ly-save").addEventListener("click", () => saveLayout($("ly-save"), {
  columns: Object.fromEntries(lySelects.map((s) => [s.label, { role: s.role.value, unit: s.unit.value }])) }));
$("ly-as-is").addEventListener("click", () => saveLayout($("ly-as-is"), { as_is: true, hours_column: lyHours }));
