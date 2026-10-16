"use strict";
// Table Reader page. Plain JS, no build step. All text from the server is inserted with textContent (never innerHTML).
// Text shown to the user goes through t()/tn() (page text) or tm() (server messages) from i18n.js.

const $ = (id) => document.getElementById(id);
let claudeReady = false;

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== false && v !== null && v !== undefined) node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children) if (c) node.append(c);
  return node;
}

// An icon from static/icons.svg (Tabler Icons, MIT; tools/make_icon_sprite.py adds more).
function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ico"); svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `icons.svg#ti-${name}`);
  svg.append(use);
  return svg;
}

// A button that shows only an icon: its words are its tooltip, and stay in it for screen readers.
function iconButton(name, label, props = {}) {
  return el("button", { type: "button", title: label, ...props, class: `icon-btn ${props.class || ""}`.trim() },
    icon(name), el("span", { class: "sr-only", text: label }));
}

// The pop-up (one at a time, over the page): a title with its icon, a ×, the body and the buttons. Esc and × close it.
let popupClosed = null;
function openPopup({ title, icon: name, body, buttons = [], onClose }) {
  closePopup();
  const box = $("popup");
  $("popup-title").replaceChildren(icon(name), " ", title);
  $("popup-body").replaceChildren(...body);
  $("popup-foot").replaceChildren(...buttons);
  $("popup-foot").hidden = !buttons.length;
  popupClosed = onClose || null;
  if (typeof box.showModal === "function") box.showModal(); else box.setAttribute("open", "");
  box.scrollTop = 0; $("popup-body").scrollTop = 0;
}
// Emptied here and not on the "close" event, which comes later and would empty a pop-up opened straight after.
function closePopup() {
  const box = $("popup");
  if (!box || !box.open) return;
  const done = popupClosed; popupClosed = null;
  if (typeof box.close === "function") box.close(); else box.removeAttribute("open");
  $("popup-body").replaceChildren(); $("popup-foot").replaceChildren();
  if (done) done();
}
function popupOpen() { return Boolean($("popup") && $("popup").open); }
// An error inside the pop-up, at the top of its body ("" takes it away).
function popupError(message) {
  $("popup-body").querySelector(":scope > .banner.error")?.remove();
  if (message) $("popup-body").prepend(el("div", { class: "banner error", text: message }));
}

function setupPopup() {
  const box = $("popup");
  $("popup-close").replaceWith(iconButton("x", t("Close"), { id: "popup-close", class: "popup-x", onclick: closePopup }));
  box.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); closePopup(); } });

}

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
  let res;
  try { res = await fetch(url, opts); }
  catch { throw new Error(t("Table Reader is not running any more. Close this tab and open Table Reader again.")); }
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    if (data && data.message) throw Object.assign(new Error(tm(data.message)), { code: data.code });   // code: for a screen that acts on it
    if (res.status === 404 || res.status === 405) {
      throw new Error(t("Table Reader was updated while it was open. Close its window, open Table Reader again, then reload this page."));
    }
    throw new Error(t("Something went wrong. Reload the page and try again."));
  }
  return data;
}

// ------------------------------------------------------------------------------------------------ Claude status
let loginTimer = null;

async function refreshClaude() {
  const box = $("claude-box");
  let s;
  try { s = await api("GET", "/api/status"); }
  catch (e) { box.replaceChildren(el("span", { class: "problem", text: e.message })); return; }
  claudeReady = s.logged_in;
  if (s.logged_in) {
    clearInterval(loginTimer); loginTimer = null;
    const plan = s.plan ? ` (${s.plan[0].toUpperCase()}${s.plan.slice(1)})` : "";
    box.replaceChildren(el("span", { class: "ok", text: t("✓ Claude connected") }),
      el("span", { class: "muted", text: `${s.email || ""}${plan}` }));
  } else {
    const kids = [el("span", { class: "problem", text: tm(s.message) || t("Claude is not connected.") })];
    if (s.installed) kids.push(el("button", { class: "primary", text: t("Sign in"), onclick: startLogin }));
    box.replaceChildren(...kids);
  }
  updateDropState();
}

async function startLogin() {
  try { await api("POST", "/api/login"); }
  catch (e) { $("claude-box").replaceChildren(el("span", { class: "problem", text: e.message })); return; }
  $("claude-box").replaceChildren(el("span", { text: t("Finish signing in in the browser window that just opened…") }));
  clearInterval(loginTimer);
  let tries = 0;
  loginTimer = setInterval(() => { if (++tries > 100) { clearInterval(loginTimer); refreshClaude(); } else refreshClaude(); }, 3000);
}

// ------------------------------------------------------------------------------------------------ files and companies
function progressText(j) {
  if (j.status === "queued") return t("Waiting…");
  if (j.status === "reading") return j.pages_total ? t("Reading page {a} of {b}…", { a: Math.min(j.pages_done + 1, j.pages_total), b: j.pages_total }) : t("Preparing…");
  if (j.status === "done") return t("Finished");
  return t("Stopped");
}

// --- client companies: each file is filed under a company the user confirmed once; the list can be filtered by it
const NO_COMPANY = "\u0000none";
const MONTH_WORD = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?$/i;
let companyFilter = "";       // "" = all companies
let editingCompany = null;    // id of the file whose company box is open (the list is not redrawn meanwhile)
try { companyFilter = localStorage.getItem("companyFilter") || ""; } catch (_) { /* private window */ }

// Only a suggestion to start the box with: "MAJU JAYA ALI SEPT 26" -> "MAJU JAYA" (month, year and the worker's
// name taken off). The user checks it before it is saved.
function suggestCompany(name) {
  const words = name.replace(/\.[a-z0-9]{2,4}$/i, "").replace(/_/g, " ").trim().split(/\s+/);
  if (words.length && /^\d{2,4}$/.test(words[words.length - 1])) words.pop();
  if (!(words.length && MONTH_WORD.test(words[words.length - 1]))) return "";
  words.pop();
  return words.length >= 2 ? words.slice(0, -1).join(" ") : "";
}

function companyNames(jobs) {
  return [...new Set(jobs.map((j) => j.company).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

// The box that files a file under a company. ``done``: called when it closes (saved or not); ``say(text, kind)``:
// where the page shows what happened ("info" / "error").
function companyBox(j, companies, done, say) {
  const input = el("input", { type: "text", list: "company-names", maxlength: "80", value: j.company || suggestCompany(j.name),
    placeholder: t("Company name"), "aria-label": t("Company for {name}", { name: j.name }) });
  const close = () => { editingCompany = null; done(); };
  const save = async () => {
    try {
      const r = await api("PUT", `/api/jobs/${encodeURIComponent(j.id)}/company`, { company: input.value });
      if (r.moved) say(tn(r.moved, "{n} other file starting with “{c}” was put under this company too.", "{n} other files starting with “{c}” were put under this company too.", { c: input.value.trim() }), "info");
    } catch (e) { say(e.message, "error"); }
    close();
  };
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") save(); if (ev.key === "Escape") close(); });
  setTimeout(() => { input.focus(); input.select(); });
  return el("div", { class: "company-edit" },
    el("label", { text: t("Company") }), input,
    el("button", { class: "primary", text: t("Save"), onclick: save }), el("button", { text: t("Cancel"), onclick: close }),
    el("span", { class: "muted", text: t("Check the name. Other files that start with it will go under it too.") }),
    el("datalist", { id: "company-names" }, ...companies.map((c) => el("option", { value: c }))));
}

// Does a file's company pass the Company chooser?
function companyMatches(company) {
  return !companyFilter || (companyFilter === NO_COMPANY ? !company : company === companyFilter);
}

// The Company chooser of step 2's list (it filters step 3's list too). Remembered in this browser.
let companySignature = "";
function renderCompanyFilter(jobs, onChange) {
  const companies = companyNames(jobs);
  const count = (c) => jobs.filter((j) => (c === NO_COMPANY ? !j.company : j.company === c)).length;
  if (companyFilter && companyFilter !== NO_COMPANY && !companies.includes(companyFilter)) companyFilter = "";
  const none = count(NO_COMPANY);
  const options = [["", t("All companies ({n})", { n: jobs.length })], ...companies.map((c) => [c, `${c} (${count(c)})`]),
    ...(none ? [[NO_COMPANY, t("No company yet ({n})", { n: none })]] : [])];
  const signature = JSON.stringify([options, companyFilter]);
  $("company-box").hidden = jobs.length === 0;
  if (signature === companySignature) return companies;          // unchanged: do not close an open list
  companySignature = signature;
  const sel = el("select", { id: "company-filter", "aria-label": t("Show files of") },
    ...options.map(([value, text]) => el("option", { value, text, selected: value === companyFilter })));
  sel.addEventListener("change", () => {
    companyFilter = sel.value;
    companySignature = JSON.stringify([options, companyFilter]);
    try { localStorage.setItem("companyFilter", companyFilter); } catch (_) { /* private window */ }
    onChange();
  });
  $("company-box").replaceChildren(el("label", {}, t("Company"), sel));
  return companies;
}

// What this tab remembers (sessionStorage): where the user was in each step, the working month, the files added here.
// A private window may refuse it: then nothing is remembered and each step opens on its first screen.
function remember(key, value) { try { sessionStorage.setItem(key, value); } catch (_) { /* refused */ } }
function recall(key) { try { return sessionStorage.getItem(key); } catch (_) { return null; } }
function forget(key) { try { sessionStorage.removeItem(key); } catch (_) { /* refused */ } }

// The number beside a step button (0 hides it).
function stepBadge(step, n) {
  const badge = $(`step-${step}-n`);
  badge.hidden = !n; badge.textContent = n ? String(n) : "";
}

// "2 Check reading": the yellow cells left in the files step 2's list shows (every file until check.js is loaded).
function refreshCheckBadge(jobs) {
  const shown = typeof ckFilter === "function" ? jobs.filter(ckFilter) : jobs;
  stepBadge("check", shown.reduce((n, j) => n + (j.cells_to_check || 0), 0));
}

function setupQuit() {
  $("quit").addEventListener("click", async () => {
    let active = 0;
    try { active = (await api("GET", "/api/activity")).active; } catch { /* quit anyway */ }
    const warn = active ? tn(active, "{n} file is still being read. They will be stopped, and you can press Continue next time. ", "{n} files are still being read. They will be stopped, and you can press Continue next time. ") : "";
    if (!confirm(warn + t("Close Table Reader?"))) return;
    try { await api("POST", "/api/quit"); } catch { /* it may already be closing */ }
    document.body.replaceChildren(el("main", {}, el("h2", { text: t("Table Reader has closed.") }),
      el("p", { text: t("You can close this tab. To use it again, open Table Reader from your desktop.") })));
  });
}

setupQuit();
setupPopup();
refreshClaude();
setInterval(() => { if (!loginTimer) refreshClaude(); }, 60000);
