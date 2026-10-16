"use strict";
// Step 3's bell: the messages of a month (what opening it did by itself, the Million file made, Million's employee
// list imported), one short line each, newest first. Kept in this browser tab (bell.<month>, at most 20); the number
// counts the ones not seen yet, and a new one shows for a moment under the bell. Loaded after paycommon.js.

const BELL_MAX = 20;
const bellMemory = {};          // month -> its messages, also when the tab's storage refuses them
let bellShown = null;           // the month whose bell is on the screen
let toastTimer = null;

function bellRead(month) {
  if (bellMemory[month]) return bellMemory[month];
  try { const list = JSON.parse(recall(`bell.${month}`) || "[]"); if (Array.isArray(list)) return (bellMemory[month] = list); }
  catch (_) { /* not readable: start again */ }
  return (bellMemory[month] = []);
}
function bellWrite(month, list) {
  bellMemory[month] = list.slice(0, BELL_MAX);
  remember(`bell.${month}`, JSON.stringify(bellMemory[month]));
}

// A message: { icon, line, detail ("" for none), action ("payroll-folder" or none) }.
function bellAdd(month, msg) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  bellWrite(month, [{ id, icon: msg.icon, line: msg.line, detail: msg.detail || "", action: msg.action || "", seen: false }, ...bellRead(month)]);
  if (month === bellShown) { bellToast(msg); bellDraw(month); }
}

// What opening the month did by itself, as one message ({added, numbered} as monthNotes keeps it).
function noteMessage(note) {
  return { icon: "file-plus", line: noteLine(note), detail: monthNotesText([note]) };
}

// The server says some notes on every load until the user acts (a file without a month): each one is said once in
// this tab, also after its × (bell-said.<month>, kept in memory too when the tab's storage refuses it).
const bellSaid = {};
function bellNote(month, note) {
  const msg = noteMessage(note), key = `${msg.line}\n${msg.detail}`;
  if (!bellSaid[month]) {
    try { const list = JSON.parse(recall(`bell-said.${month}`) || "[]"); bellSaid[month] = Array.isArray(list) ? list : []; }
    catch (_) { bellSaid[month] = []; }
  }
  if (bellSaid[month].includes(key)) return;
  bellSaid[month] = [...bellSaid[month], key].slice(-50);
  remember(`bell-said.${month}`, JSON.stringify(bellSaid[month]));
  bellAdd(month, msg);
}

function bellToast(msg) {
  const toast = $("bell-toast");
  toast.replaceChildren(icon(msg.icon), " ", msg.line);
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 4000);
}

async function bellAction(action) {
  if (action !== "payroll-folder") return;
  try { await api("POST", "/api/folders/payroll/open"); moError(""); } catch (e) { moError(e.message); }
}

function bellDraw(month) {
  bellShown = month;
  const list = bellRead(month);
  const unseen = list.filter((m) => !m.seen).length;
  $("bell-count").hidden = !unseen; $("bell-count").textContent = unseen ? String(unseen) : "";
  const box = $("bell-list");
  if (box.hidden) return;
  const rows = list.map((m) => el("li", { class: "msg" },
    el("div", { class: "msg-row" }, icon(m.icon), el("span", { class: "msg-line", text: m.line }),
      m.action ? el("button", { type: "button", class: "link", text: t("Open folder"), onclick: () => bellAction(m.action) }) : null,
      iconButton("x", t("Close"), { onclick: (e) => { e.stopPropagation(); bellWrite(month, bellRead(month).filter((x) => x.id !== m.id)); bellDraw(month); } })),
    m.detail ? el("details", {}, el("summary", { text: t("More") }), el("p", { class: "legend", text: m.detail })) : null));
  box.replaceChildren(rows.length ? el("ul", {}, ...rows) : el("p", { class: "muted", text: t("No messages.") }),
    rows.length ? el("button", { type: "button", class: "link", text: t("Clear all"),
      onclick: (e) => { e.stopPropagation(); bellWrite(month, []); bellDraw(month); } }) : null);
}

function bellOpen(open) {
  const box = $("bell-list");
  box.hidden = !open;
  if (open && bellShown) bellWrite(bellShown, bellRead(bellShown).map((m) => ({ ...m, seen: true })));
  if (bellShown) bellDraw(bellShown);
}

$("bell-open").replaceWith(iconButton("bell", t("Messages"), { id: "bell-open", onclick: (e) => { e.stopPropagation(); bellOpen($("bell-list").hidden); } }));
$("bell-list").addEventListener("click", (e) => e.stopPropagation());
document.addEventListener("click", () => { if (!$("bell-list").hidden) bellOpen(false); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("bell-list").hidden) bellOpen(false); });
