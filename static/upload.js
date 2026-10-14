"use strict";
// Step 1, Upload: the drop box, the Inbox and Tables folders, and "Just added": the files added in this tab and every
// file still waiting or being read, each with its company and progress, then "Check them →" (step 2).
// Loaded after app.js and uses its helpers.

let uploading = false;
let upFirst = null;            // the first file added in this tab that is still there (where "Check them →" goes)

// The Inbox folder (files saved there are read by themselves) and the Tables folder (every finished table as a CSV)
for (const [id, name] of [["open-inbox", "inbox"], ["open-tables", "tables"]]) {
  $(id).addEventListener("click", async () => {
    try { await api("POST", `/api/folders/${name}/open`); }
    catch (e) { showMessages([e.message], "error"); }
  });
}

function updateDropState() {
  const drop = $("drop");
  drop.classList.toggle("disabled", !claudeReady || uploading);
  drop.setAttribute("aria-disabled", String(!claudeReady || uploading));
}

function showMessages(items, kind) {
  $("upload-messages").replaceChildren(...items.map((m) => el("div", { class: `banner ${kind}`, text: m })));
}

function addedHere() {
  try { const ids = JSON.parse(recall("added") || "[]"); return Array.isArray(ids) ? ids : []; } catch (_) { return []; }
}

async function upload(fileList) {
  const files = [...fileList];
  if (!files.length || uploading) return;
  if (!claudeReady) { showMessages([t("Connect your Claude account first (top right), then add your files.")], "error"); return; }
  uploading = true; updateDropState();
  showMessages([tn(files.length, "Adding {n} file…", "Adding {n} files…")], "info");
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));
  try {
    const r = await api("POST", "/api/jobs", form);
    showMessages(r.rejected.map((x) => tm(x.message)), "error");
    remember("added", JSON.stringify([...r.created.map((c) => c.id), ...addedHere()].slice(0, 200)));
  } catch (e) { showMessages([e.message], "error"); }
  uploading = false; updateDropState();
  loadJustAdded();
}

function setupDrop() {
  const drop = $("drop"), input = $("file-input");
  drop.addEventListener("click", () => {
    if (!claudeReady) showMessages([t("Connect your Claude account first (top right), then add your files.")], "error");
    else if (!uploading) input.click();
  });
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); drop.click(); } });
  input.addEventListener("change", () => { upload(input.files); input.value = ""; });
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); });
  // a file dropped beside the box must not make the browser leave the page
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());
}

function fileRow(j, companies) {
  const cancelled = j.status === "failed" && j.error && j.error.code === "CANCELLED";
  const active = j.status === "queued" || j.status === "reading";
  const cls = j.status === "done" ? "pill good" : j.status === "failed" && !cancelled ? "pill bad" : "pill";
  const li = el("li", {},
    el("span", { class: "name", text: j.name }),
    el("button", { class: j.company ? "company" : "company unset", text: j.company || t("Set company"),
      title: j.company ? t("Click to change the company") : t("Choose the client company of this file"),
      onclick: () => {
        editingCompany = j.id;
        document.querySelectorAll("#recent .company-edit").forEach((n) => n.remove());
        li.append(companyBox(j, companies, loadJustAdded, (text, kind) => showMessages([text], kind)));
      } }),
    el("span", { class: "when", text: new Date(j.created).toLocaleString(LOCALE) }),
    el("span", { class: cls, text: cancelled ? t("Cancelled") : progressText(j) }),
    active && el("button", { text: t("Cancel"), onclick: async () => {
      try { await api("POST", `/api/jobs/${encodeURIComponent(j.id)}/cancel`); } catch (e) { showMessages([e.message], "error"); }
      loadJustAdded();
    } }),
    j.status === "done" && el("button", { text: t("Open"), onclick: () => { location.hash = `#/check/${encodeURIComponent(j.id)}`; } }));
  if (j.status === "failed" && j.error && !cancelled) li.append(el("div", { class: "muted", style: "flex-basis:100%", text: tm(j.error.message) }));
  return li;
}

async function loadJustAdded() {
  if (editingCompany) return;
  let jobs;
  try { jobs = await api("GET", "/api/jobs"); } catch (e) { showMessages([e.message], "error"); return; }
  refreshCheckBadge(jobs);
  const mine = new Set(addedHere());
  const busy = (j) => j.status === "queued" || j.status === "reading";
  const shown = jobs.filter((j) => mine.has(j.id) || busy(j));
  const companies = companyNames(jobs);
  $("recent").replaceChildren(...shown.map((j) => fileRow(j, companies)));
  $("recent-empty").hidden = shown.length > 0;
  $("up-state").textContent = jobs.some(busy) ? t("Reading…") : shown.length ? t("Everything is read.") : "";
  const first = shown.find((j) => mine.has(j.id));
  upFirst = first ? first.id : null;
}

$("up-check").addEventListener("click", () => { location.hash = upFirst ? `#/check/${encodeURIComponent(upFirst)}` : "#/check"; });

function showUpload() { loadJustAdded(); }

setInterval(() => { if (!$("upload").hidden) loadJustAdded(); }, 4000);
setupDrop();
