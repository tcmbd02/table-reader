"use strict";
// The one-look panel: one employee's time cards, one card at a time, showing only the lines the calculation could not
// use, beside the card's picture. Accepting saves every box of the card as a correction, exactly as Enter in a cell of
// the document page does, marked "via": "look". Claude's reading is never changed.
// Loaded after companies.js and uses its helpers (monthTitle, companyHash).

let lkMonth = null;         // the month ("2026-09")
let lkEmployee = null;      // the employee's id
let lkView = null;          // what the server last sent: {name, company, cards: [{doc, name, lines}]}
let lkCard = 0;             // the card on the screen (index in lkView.cards)
let lkLine = 0;             // the line whose page the picture shows
let lkBoxes = [];           // the boxes of the card on the screen: {line, cell, input, original, yellow, mustType, empty}
const lkDraft = new Map();  // what was typed in a card not saved yet ("doc|page|row|column" -> text), kept while paging

function lkError(message) { $("lk-error").hidden = !message; $("lk-error").textContent = message || ""; }

async function showLook(month, employee) {
  clearTimeout(docTimer); currentId = null; currentDoc = null;
  hideScreens(); $("look").hidden = false;
  lkMonth = month || defaultPayrollMonth();
  lkEmployee = employee; lkView = null; lkCard = 0; lkLine = 0; lkDraft.clear();
  $("lk-title").textContent = ""; $("lk-body").hidden = true;
  lkError("");
  await loadLook(null, false);
}

// Ask the server what is still wrong. ``stayOn``: the card to stay on while it has lines left; ``saved``: it was just
// saved (and still has lines that cannot be used).
async function loadLook(stayOn, saved) {
  try { lkView = await api("GET", `/api/payroll/${lkMonth}/look?employee=${encodeURIComponent(lkEmployee)}`); }
  catch (e) { lkError(e.message); return; }
  $("lk-title").textContent = `${lkView.name || t("An employee")} - ${lkView.company || t("(no company)")} - ${monthTitle(lkMonth)}`;
  if (!lkView.cards.length) { backFromLook(); return; }
  const same = stayOn === null ? -1 : lkView.cards.findIndex((c) => c.doc === stayOn);
  lkCard = same >= 0 ? same : Math.min(lkCard, lkView.cards.length - 1);
  lkLine = 0;
  drawLookCard(saved && same >= 0);
}

function backFromLook() {
  location.hash = lkView ? companyHash(lkMonth, lkView.company) : `#/payroll/${lkMonth}`;
}

function draftKey(doc, line, column) { return `${doc}|${line.page}|${line.row}|${column}`; }

// What the box starts with: what Claude saw for a yellow cell, without a "?" at the start or end (Claude's doubt, as on
// the document page); the value as it is now for any other cell.
function shownText(cell) {
  return cell.needs_review ? (cell.raw_text || "").trim().replace(/^\?+|\?+$/g, "").trim() : cell.value ?? "";
}

function lineLabel(line) {
  return line.day === null ? t("Row {r}", { r: line.row + 1 })
    : `${t("Day {d}", { d: line.day })} (${t("row {r}", { r: line.row + 1 })})`;
}

function drawLookCard(left) {
  const card = lkView.cards[lkCard];
  $("lk-body").hidden = false;
  $("lk-count").textContent = t("Card {a} of {b}", { a: lkCard + 1, b: lkView.cards.length });
  $("lk-prev").disabled = lkCard === 0;
  $("lk-next").disabled = lkCard === lkView.cards.length - 1;
  $("lk-card").textContent = card.name;
  $("lk-note").hidden = !left;
  $("lk-note").textContent = left ? t("Saved. These lines can still not be used: type what the card shows.") : "";
  lkBoxes = [];
  $("lk-lines").replaceChildren(...card.lines.map((line, n) => lineNode(card, line, n)));
  showLinePicture(lkLine);
  paintAccept();
}

function lineNode(card, line, n) {
  const boxes = line.cells.map((cell) => boxNode(card, line, cell));
  const yellow = line.cells.some((c) => c.needs_review);
  const node = el("li", { class: "look-line", "data-line": String(n) },
    el("strong", { text: lineLabel(line) }), el("div", { class: "look-boxes" }, ...boxes),
    // a line with no yellow cell is there because of what is written on it: the calculation says what
    ...(yellow ? [] : line.texts.map((text) => el("p", { class: "legend", text: tm(text) }))));
  node.addEventListener("focusin", () => showLinePicture(n));
  node.addEventListener("click", () => showLinePicture(n));
  return node;
}

function boxNode(card, line, cell) {
  const shown = shownText(cell);
  const key = draftKey(card.doc, line, cell.column);
  const input = el("input", { type: "text", autocomplete: "off", spellcheck: "false",
    value: lkDraft.has(key) ? lkDraft.get(key) : shown, "aria-label": `${lineLabel(line)}, ${cell.column}` });
  const box = { line, cell, input, original: shown, yellow: cell.needs_review, empty: false,
    mustType: cell.needs_review && (shown === "" || shown.includes("?")) };
  lkBoxes.push(box);
  const parts = [el("label", { text: cell.column }), el("div", { class: "cell" + (box.yellow ? " flag" : "") }, input)];
  if (box.yellow) parts.push(el("small", { class: "why", text: tm(cell.unclear_reason) || t("Claude was not sure about this cell.") }));
  if (box.yellow && cell.raw_text && cell.raw_text.trim() !== shown) {
    parts.push(el("small", { class: "why", text: t("Claude saw: {x}", { x: cell.raw_text }) }));
  }
  let nothing = null;
  if (box.mustType) {
    parts.push(el("small", { class: "must", text: t("Must be typed") }));
    if (shown === "") {
      // an empty yellow box cannot be cleared to say "really empty": the user says it here, it is never assumed
      nothing = el("button", { type: "button", class: "small", text: t("Nothing written") });
      nothing.addEventListener("click", () => {
        box.empty = !box.empty; input.value = ""; lkDraft.set(key, "");
        nothing.classList.toggle("on", box.empty);
        nothing.setAttribute("aria-pressed", String(box.empty));
        paintAccept();
      });
      nothing.setAttribute("aria-pressed", "false");
      parts.push(nothing);
    }
  }
  input.addEventListener("input", () => {
    lkDraft.set(key, input.value);
    if (box.empty && input.value.trim()) { box.empty = false; nothing?.classList.remove("on"); nothing?.setAttribute("aria-pressed", "false"); }
    paintAccept();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {                                   // on to the next box, or to Accept after the last
      const next = lkBoxes[lkBoxes.indexOf(box) + 1];
      (next ? next.input : $("lk-accept")).focus();
    } else if (e.key === "Escape") { input.value = box.original; lkDraft.delete(key); paintAccept(); }
  });
  return el("div", { class: "look-box" + (box.mustType ? " must-type" : "") }, ...parts);
}

function typed(box) { return box.input.value.trim(); }
function untyped(box) { return box.mustType && !box.empty && typed(box) === box.original; }
function changed(box) { return box.empty || typed(box) !== box.original; }

function paintAccept() {
  const yellow = lkBoxes.filter((b) => b.yellow).length;
  const waiting = lkBoxes.filter(untyped).length;
  const button = $("lk-accept");
  button.textContent = yellow ? tn(yellow, "Accept this cell", "Accept all {n} cells") : t("Save");
  button.disabled = waiting > 0 || (!yellow && !lkBoxes.some(changed));
  $("lk-left").textContent = waiting ? tn(waiting, "{n} box still needs typing.", "{n} boxes still need typing.") : "";
}

// The picture of the page the line is on. A click on it shows it closer (and again back to the whole page).
function showLinePicture(n) {
  const card = lkView.cards[lkCard];
  const line = card.lines[n] || card.lines[0];
  lkLine = n;
  for (const node of $("lk-lines").children) node.classList.toggle("on", node.dataset.line === String(n));
  const src = `/api/jobs/${encodeURIComponent(card.doc)}/pages/${line.page}`;
  const box = $("lk-picture");
  const img = box.querySelector("img");
  if (img && img.getAttribute("src") === src) return;
  const picture = el("img", { src, alt: t("Original, page {n}", { n: line.page }) });
  picture.addEventListener("click", () => box.classList.toggle("zoom"));
  box.replaceChildren(picture, el("p", { class: "hint", text: t("Page {n}. Click the picture to see it closer.", { n: line.page }) }));
}

$("lk-accept").addEventListener("click", async () => {
  const card = lkView.cards[lkCard];
  const seen = new Set();
  const changes = [];
  for (const box of lkBoxes) {
    if (!box.yellow && !changed(box)) continue;               // a cell that was fine and was not touched stays as it is
    const key = draftKey(card.doc, box.line, box.cell.column);
    if (seen.has(key)) continue;
    seen.add(key);
    // how the cell looked when it was shown: if it was corrected since (another window), the server saves nothing
    const asShown = { edited: box.cell.edited, value: box.cell.edited ? box.cell.value : null };
    changes.push({ page: box.line.page, row: box.line.row, column: box.cell.column,
      value: box.empty ? "" : typed(box), via: "look", seen: asShown });
  }
  const button = $("lk-accept");
  button.disabled = true;
  try {
    await api("PUT", `/api/jobs/${encodeURIComponent(card.doc)}/cells`, { changes });
    for (const key of [...lkDraft.keys()]) if (key.startsWith(`${card.doc}|`)) lkDraft.delete(key);
    lkError("");
    await loadLook(card.doc, true);
  } catch (e) {
    await loadLook(card.doc, false);                           // show what is saved now; what was typed here is kept
    lkError(e.message);
    paintAccept();
  }
});

$("lk-prev").addEventListener("click", () => { if (lkCard > 0) { lkCard -= 1; lkLine = 0; drawLookCard(false); } });
$("lk-next").addEventListener("click", () => {
  if (lkCard < lkView.cards.length - 1) { lkCard += 1; lkLine = 0; drawLookCard(false); }
});
$("lk-back").addEventListener("click", backFromLook);

// Back in this tab after changing a cell somewhere else: show what is still wrong (what was typed here is kept).
function refreshLook() { if (lkView) loadLook(lkView.cards[lkCard]?.doc ?? null, false); }

if (location.hash.startsWith("#/payroll")) route();      // the page was opened on a payroll screen: app.js ran before this file
