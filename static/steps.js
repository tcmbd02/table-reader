"use strict";
// The three steps: 1 Upload, 2 Check reading, 3 Payroll. The step buttons at the top, the addresses, where the user last
// was in each step (this tab only), the month steps 2 and 3 share, and drawing again on coming back to the tab.
// Loaded last: it draws the first screen.
//   #/                                                         1 Upload
//   #/check[/<file>[/columns/<page>[/h/<hours column>]]]       2 Check reading (a file; its column choice open)
//   #/payroll[/<month>[/e/<employee>[/look] | /c/<company>]]   3 Payroll (an employee; their Look panel; a company)
// Addresses of the screens before the three steps open the matching place.

const OLD_ADDRESSES = [
  [/^#\/doc\/(.+)$/, (m) => `#/check/${m[1]}`],
  [/^#\/payroll\/(\d{4}-\d{2})\/look\/([^/]+)$/, (m) => `#/payroll/${m[1]}/e/${m[2]}/look`],
  [/^#\/payroll\/(\d{4}-\d{2})\/layout\/([^/]+)\/(\d+)(\/h\/[^/]+)?$/, (m) => `#/check/${m[2]}/columns/${m[3]}${m[4] || ""}`],
  [/^#\/payroll\/(\d{4}-\d{2})\/old(?:\/e\/([^/]+))?$/, (m) => (m[2] ? `#/payroll/${m[1]}/e/${m[2]}` : `#/payroll/${m[1]}`)],
];

function workMonth() {
  const m = recall("workMonth");
  return /^\d{4}-\d{2}$/.test(m || "") ? m : defaultPayrollMonth();
}
function setWorkMonth(month) { remember("workMonth", month); }

function showStep(step) {
  for (const s of ["upload", "check", "payroll"]) {
    const button = $(`step-${s}`);
    button.classList.toggle("on", s === step);
    if (s === step) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  }
  for (const [id, s] of [["upload", "upload"], ["check", "check"], ["people", "payroll"]]) $(id).hidden = s !== step;
}

function route() {
  const hash = location.hash;
  for (const [re, to] of OLD_ADDRESSES) {
    const m = hash.match(re);
    if (m) { location.replace(to(m)); return; }               // the hashchange that follows draws it
  }
  if (typeof emLeave === "function") emLeave();               // what was typed in an employee and not sent yet: now
  const ck = hash.match(/^#\/check(?:\/([^/]+)(?:\/columns\/(\d+)(?:\/h\/([^/]+))?)?)?$/);
  const pp = hash.match(/^#\/payroll(?:\/(\d{4}-\d{2})(?:\/e\/([^/]+)(\/look)?|\/c\/(.*))?)?$/);
  if (ck && typeof showCheck === "function") {
    showStep("check");
    if (ck[1]) remember("place.check", hash);
    showCheck(ck[1] ? decodeURIComponent(ck[1]) : null,
      ck[2] ? { page: Number(ck[2]), hours: ck[3] ? decodeURIComponent(ck[3]) : null } : null);
  } else if (pp && typeof showPeople === "function") {
    showStep("payroll");
    if (pp[1]) setWorkMonth(pp[1]);
    if (pp[2] || pp[4] !== undefined) remember("place.payroll", hash);
    showPeople(pp[1] || workMonth(), { employee: pp[2] ? decodeURIComponent(pp[2]) : null, look: Boolean(pp[3]),
      company: pp[4] !== undefined ? decodeURIComponent(pp[4]) : null });
  } else {
    showStep("upload");
    showUpload();
  }
}

// A step button opens the step where the user last was in this tab (step 3: in the working month).
for (const [step, first] of [["upload", "#/"], ["check", "#/check"], ["payroll", "#/payroll"]]) {
  $(`step-${step}`).addEventListener("click", (e) => {
    e.preventDefault();
    let to = step === "upload" ? first : recall(`place.${step}`) || first;
    if (step === "payroll" && !to.startsWith(`#/payroll/${workMonth()}/`)) to = `#/payroll/${workMonth()}`;
    if (location.hash === to) route(); else location.hash = to;
  });
}

// Back in this tab after fixing something in another one: show what is true now (never over a box being typed in).
let lastReturn = 0;
async function refreshOnReturn() {
  if (document.hidden || Date.now() - lastReturn < 1000) return;      // the two events below often come together
  const typing = document.activeElement && ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
  if (typing) return;
  lastReturn = Date.now();
  if (!$("people").hidden && typeof ppLoad === "function") {
    await ppLoad();
    if (!$("look").hidden && typeof refreshLook === "function") refreshLook();
    else if (!$("employee").hidden && typeof emLoad === "function" && emView && !Object.keys(emPending).length) emLoad();
  } else if (!$("check").hidden && $("layout").hidden && typeof ckLoad === "function") {
    await ckLoad();
    if (currentId) ckDrawFile();
  } else if (!$("upload").hidden) showUpload();
}
document.addEventListener("visibilitychange", refreshOnReturn);
window.addEventListener("focus", refreshOnReturn);

window.addEventListener("hashchange", route);
route();
