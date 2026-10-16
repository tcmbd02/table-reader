# Next session — start here

Handoff written 2026-10-07, updated 2026-10-09 (session 7b). Read this first, then `PROGRESS.md` (newest entries at the top,
sessions 5–7b) and `PLAN.md`. Project rules are in `CLAUDE.md` (never guess; personal data stays on this PC).

**To continue, paste this into the new session:**

> Read NEXT-SESSION.md (the "Next" box first) and PROGRESS.md (sessions 9 to 25), then let's continue.

> **State at the end of session 25 (16 Oct):** `pdf-text` is pushed up to 24d, and the `download` branch has that build
> (8b1b984). The yellow-cell question (step 2) and the closable step 3 messages are merged into `pdf-text`
> (bd1c781), **not pushed**; the app was rebuilt with the first only. Windows' Application Control blocked starting the
> rebuilt exe from the session. The step 3 redesign (tabs, bell, pop-ups) is **built on branch `step3-tabs`**
> (from `pdf-text`; not merged, app not rebuilt), all 10 tasks of `docs/superpowers/plans/2026-10-16-step3-tabs-bell-popups.md`
> done, pytest 560 and every click-through "No problems". **Still to do:** the whole-branch review by one fresh
> reviewer (started in session 25, result not received before the session ended: run it again), one fix pass for its
> Critical/Important findings (each with a test that fails first), then report rulings and deferred minors. Ledger with
> every ruling: `.superpowers/sdd/2026-10-16-step3-tabs-bell-popups/progress.md` in the worktree
> `.claude/worktrees/payroll-yellow-cells-confirm-b123ca` (git-ignored, not in the main folder). Then waiting for the
> user: look at it, merge / rebuild / push / `download` branch / PDF guide (each needs the user's OK). Details:
> PROGRESS.md 25.

Session 24 rearranged the app into three steps (Upload, Check reading, Payroll): merged into `pdf-text`, the app
rebuilt, pushed (PR #2), and the `download` branch updated, all on the user's OK. Sessions 24b-24d added to it (see
section 0). The PDF guide is not regenerated yet (its pictures and some text show the old start page; needs your OK).

---

## 0. Open problem from sessions 8–9 (2026-10-09) — read before anything else

A real September Million file (one company, 2 employees) imported on this laptop gave **"no record updated"**.
**Cause confirmed (session 9, seen in Million):** the file and both Employee Nos. are right and the two employees
exist in Million, but the **September payroll is already Processed and lists only one other employee** — the two
workers are not in that month's payroll, so there was nothing to update. Details: PROGRESS.md session 9.
- **Test passed on October (session 9):** the two workers were added to the October payroll (Edit > Add) and the
  Table Reader file imported: "Update complete", figures in Million equal the file. So the routine is: employee exists
  in Million -> is added to the month's payroll -> import with file type "Excel 97-2003 (*.xls)".
- A second company (4 new employees created in Million with Employee No. + Name only) passed the same test. Staff
  guide: `GUIDE - Table Reader to Million.html`. Million now has 7 employees; the 4 new ones still need their details.
- **Session 9b:** "Import employee list from Million" built (Employment Listing export -> Employee Nos. offered,
  unknown-number and name checks before download). Details and what is not done: PROGRESS.md session 9b.
- **Session 10:** text-only PDF pages are read from the PDF's own text after Claude has read one page of the
  document (`pdftext.py`, branch `pdf-text`, **not committed, not merged**). Measured: 16 of 27 real text pages
  need no Claude, 7,508 cells identical. Details: PROGRESS.md session 10.
- **Session 11 ("automate more", aim: fewer clicks; ~40 companies):** one Million file for the whole month
  (month run) and Employee No. suggestions are built, on branch `pdf-text`, **not committed**. An automatic check
  of the import is not possible with Million's reports (PROGRESS.md session 11). Ideas not built: public holidays
  filled in, watched folder, layouts remembered between months, faster yellow-cell checking.
- **Session 12:** section "4. Daily-rated pay" (basic pay = daily rate x Days Worked; OT/PH/rest-day money waits
  for HR's rules), the Inbox folder (files read by themselves) and the Tables folder (every table as CSV). Same
  branch, **not committed**. Details: PROGRESS.md session 12.
- **Sessions 12b-14:** Basic Rate with Monthly / Daily in Results; Million's functions surveyed; pay basis and rate
  read from Million's Payroll Information report; pay preview with Million's overtime formulas. Committed on
  `pdf-text` on 2026-10-12 (second commit of PR #2).
- **Sessions 15-15b (experiments in Million, October test month, employees 100-102):** Process Pay run once. Million
  works out Days Worked itself (Working Days - PH); daily overtime uses basic pay / days worked, not the rate (preview
  840.00 vs Million 874.92 with a PH in the month; Monthly matches). **Open with HR:** should Working Days sent to
  Million include the public holiday? Second test round not finished (102's PH to 0, Process Pay again). Details:
  PROGRESS.md sessions 15 and 15b.
- **Session 16 (2026-10-12):** IN/OUT cards with an empty Total column were counted as "not worked" (fixed);
  one IN + one later OUT = one span minus the break; OFF / PH / CUTI / MC on cards = day marks; "Use this" drops a
  leading / trailing "?". Session 16b: Phase B built (newly read files join their month's payroll when it is opened),
  committed and pushed on `pdf-text` (0045a5d), app rebuilt 2026-10-12.
  Not built: Phase C (Claude names unknown columns, text only; the calculation stays in code). Details: PROGRESS.md
  16, 16b.
- **Session 17 (2026-10-12):** a new worker's Employee No. is filled in from Million's list when the name read on the
  card is one employee's whole name there (marked on the page); otherwise a worker of a company gets a new number,
  company's first 7 letters + 3 digits (MAJUJAY001), to be created in Million before the import. Open: does Million
  accept 10 characters? Yellow cells now show only what Claude saw (Enter accepts); they are still unconfirmed in the
  CSV and payroll - the user was asked whether they should count without being accepted, no answer yet. Committed
  (390d7b0), app rebuilt, `download` branch (700dd47) and PR #2 description updated. None of the session's page changes
  were clicked through in a browser. Next, on the user's go-ahead: Phase C. Details: PROGRESS.md 17.
- **Session 18 (2026-10-12): company-first payroll, stage 1:** Payroll opens on a month overview (one row per
  company), each company has a "Needs you" list; the old page was behind "Old payroll page" (removed in session 23).
  **Merged into `pdf-text`
  and the app rebuilt** (by the user, after the session). Details: PROGRESS.md 18.
- **Session 19 (2026-10-12): stage 2, the one-look panel**, merged into `pdf-text` (local, **not pushed**) and the
  app rebuilt on the user's OK: a Look button on an employee's "cells to check" item opens all their
  lines that the calculation could not use, card by card beside the picture, with one Accept per card. Reviewed by a
  fresh reviewer, its one important finding fixed; 7 minor ones listed in PROGRESS.md 19. Nobody has used the panel
  on a real card picture yet.
- **Session 20 (2026-10-12): stage 3, month and company settings**, merged into `pdf-text` (local, **not pushed**)
  and the app rebuilt on the user's OK: Month settings on the overview, Company settings on a
  company screen (own hours, break, calendar; "next month" carry-over), an item when the default changes after a
  company's own settings. Reviewed, its one important finding fixed; 7 minor ones in PROGRESS.md 20.
- **Session 21 (2026-10-14): stage 4 planned and Part A built**, merged into `pdf-text` (fast-forward, local,
  **not pushed**) and the app rebuilt on the user's OK. Plan: `docs/superpowers/plans/2026-10-14-company-first-payroll-stage-4.md`, split in
  Part A (summary before the month's Million file, "New in Million" list with Copy, payroll CSV on the new screens) and
  Part B (employee view, pay preview tab, Add employee, then the old page and its endpoints removed). Details:
  PROGRESS.md 21.
- **Session 21b (2026-10-14): why read cards do not reach Million.** On the real September month: 8 of 84 employees go
  into the file. 67 are stopped first by Employee Nos. this laptop's test Million does not have. With every number
  known, 37 would go in. The conversion failures found: a wrong hours column on two layouts (can give wrong figures
  without warning), OUT without pm, SA / SU, a clock report whose OT and minutes never reach Million, and a door-system
  export. The user ruled on each, and the plan gained **Part C (conversion), Tasks 11-17, to do before Part B**, on
  branch `conversion` (plan only, nothing built). Still to answer: should the CSV buttons ask about "Needs checking"
  employees (the old page did)? Details: PROGRESS.md 21b.
- **Session 22 (2026-10-14): Part C built, merged into `pdf-text` (local, not pushed) and the app rebuilt**:
  - the hours column is never money or minutes;
  - the user's afternoon-OUT and SA/SU rules, and "530 pm";
  - weekday-headed grids;
  - layout maps, with Claude's text-only suggestion and the user's confirmation.

  Real September data: 6 employees changed, each for an expected reason; 78 identical. Reviewed: 2 critical and 5
  important findings fixed. Waiting for the user: merge / rebuild, one real Claude check, and the questions in
  PROGRESS.md 22. Next after merging: Part B.
- **Session 23 (2026-10-14): Part B built on branch `employee-view`, merged into `pdf-text` (local, not pushed) and
  the app rebuilt on the user's OK:**
  - the employee view (`#/payroll/<month>/e/<id>`, "Open employee"): the Edit Payroll window, the employee's cards
    (move to another employee, take off), the Hours column, Remove; each change saved as its own key;
  - the company screen's Pay preview tab and Add employee, and a folded list of the company's files set aside or read
    as another month ("It is for <month>");
  - the old payroll page and its endpoints are gone (an old address opens the overview or the employee view);
  - guides updated (not the PDF).

  Real September data: all 84 employees identical, 8 ready / 76 held as before. Reviewed: 3 important and 7 minor
  findings fixed. Waiting for the user: push / `download` branch / PDF guide. Details: PROGRESS.md 23.
- **Session 24 (2026-10-14): three steps, merged into `pdf-text`, the app rebuilt, pushed, `download` branch updated,
  all on the user's OK:** 1 Upload (Just added) → 2 Check reading (files list, the file with "This file needs you", columns in
  place) → 3 Payroll (companies and employees in one list, the employee or company on the right), step buttons at the
  top, same tab. New requests `/people` and `/files`; the company screen's two requests are gone. Real September data:
  87 employees identical, 9 ready / 78 held, same file problems. Click-throughs in `tools/clickthrough/`. Details:
  PROGRESS.md 24.
- **Session 24b (2026-10-14): "Add a time card"** on the employee view (any card of the employee's company; one on
  another employee is moved after a question). Merged into `pdf-text`, the app rebuilt, pushed, and the
  `download` branch updated (commit 14bd93b), all on the user's OK. Details: PROGRESS.md 24b.
- **Session 24c (2026-10-14): "Rest days every week"** ticks in Month / Company settings (Sunday ticked by default),
  and a fix for a stray "null" under an employee's cards (24b). Merged into `pdf-text` and the app rebuilt; **not
  pushed, `download` branch not updated** (its zip still has the "null"). Details: PROGRESS.md 24c.
- **Session 24d (2026-10-14): Export…** replaces "Download payroll CSV" and "Make the month's Million file": the
  payroll table (CSV or .xls) or the Million import file, for all or chosen companies, one file or one per company.
  Merged into `pdf-text` and the app rebuilt; **not pushed, `download` branch not updated** (24c and 24d). Details:
  PROGRESS.md 24d.
- **Still open:** September itself is Processed and still lacks the two workers (un-process / re-create: the user
  decides). October holds September figures as test data — clear or overwrite before the real October payroll.
- Built in session 9: the warning before download when an Employee No. is not in `employees.txt` (which now lists
  all 3 codes of this laptop's Million).

## 1. Where things stand

| Area | State |
|---|---|
| Reading scans/photos → table → CSV | Working. Packaged app in `dist\Table Reader\` (rebuilt 2026-10-12, latest code). |
| Company per file + Company chooser in the top bar | Done. Filters Recent files *and* the Payroll screen. Remembered in the browser. |
| Bahasa Melayu | Done (button in the top bar). Edit Payroll copy + CSVs stay English on purpose. |
| Payroll: Leave table, Allowance & Deduction tab, colour key on days | Done. |
| Payroll: save bug (results not updating) | **Fixed.** Cause: a ticked card that no longer existed blocked every save. |
| Payroll from **total-hours cards** (a "Total" column per day) | Working (worked out with the normal-hours rule). |
| Payroll from **clock-system reports** (Shift Details / OverTime columns) | **Done today.** Printed figures added up as-is (decimal hours); checked against the report's own totals: all 17 worker pages of the real report match exactly. |
| Reports with one worker per page | Done: picker lists each page separately ("… — page 3: CODE NAME"). |
| "Add employees from files" | Done. One employee per worker, cards ticked; Employee No. remembered per worker in `payroll\employees.json` for next months. Dry run on Sept A–D: 34 employees, 34 files left out (can't be calculated yet). |
| Payroll from **IN/OUT time cards** | **Done (session 9).** OUT − IN − break (1 h, box next to Normal hours); several pairs added up, no break. 4 points to confirm with the user: PROGRESS.md session 9. |
| Payroll from **month grids** ("Name \| 1 … 31", many workers per sheet) | **Done (session 7).** Each worker's row is offered separately; unclear marks are reported. |
| **Million import file (.xls)** for the office | **Done (session 7).** Since session 11 one file for the whole month ("Make the month's Million file", summary first since session 21); the per-company "Download Million file (.xls)" went with the old page (session 23). |
| Three steps (session 24, branch `three-steps`) | 1 Upload → 2 Check reading (files, and each file's problems for the payroll) → 3 Payroll (companies and employees in one list; employee or company on the right). Replaces the month overview, company screen and the separate Look / Layout pages of sessions 18-23. |
| Browser check | Click-throughs in headless Edge on made-up data, in the repo since session 24 (`tools/clickthrough/`, `sh tools/clickthrough/run.sh <scenario>`). Nobody has looked at the new screens with their eyes on a real card yet. |

Tests: **558 pass** on `pdf-text` (`.venv\Scripts\python -m pytest -q`; a worktree without its own `.venv` can use the main folder's). Package rebuilt in session 24 (14 Oct, with the three steps). Sessions up to 22 are committed on `pdf-text` (PR #2, base `main`, not merged; local commits not pushed); session 23 merged into `pdf-text` too; session 24 merged into `pdf-text` too. The `download` branch has the build of 14 Oct (three steps); its PDF guide is still the old one.

## 2. Git / GitHub

- Repo is **PUBLIC**: `tcmbd02/table-reader`. Never commit real names, documents, results or screenshots
  (`screenshots/` is git-ignored; examples use made-up names such as "MAJU JAYA", "ALI", "MJ(1)").
- **PR #1 was merged into `main` on 2026-10-09** (user asked; merge commit 626a4c5, includes sessions 9 and 9b). The
  local checkout is on `main`. New work: make a new branch from `main` first. The old branch was deleted.
- **Branch `download` (for normal users, made 2026-10-09):** an orphan branch with only `Table Reader.zip` (the built
  app), `Table Reader guide.pdf`, `GUIDE - Table Reader to Million.html` and a user README. No code, no notes. After a
  change that users should get: rebuild, then replace those files on `download` (use a separate worktree; update the
  build date and commit in its README), scan, commit, push. Link: https://github.com/tcmbd02/table-reader/tree/download
- **`download` is the repository's DEFAULT branch (user asked, 2026-10-09)**, so visitors see the installer first. The
  code stays on `main`. Consequences: a new pull request aims at `download` unless told otherwise — **always open
  PRs with `--base main`**; a fresh clone checks out `download` (`git checkout main` for the code); `origin/HEAD`
  points to `download` here.
- History of PR #1 (https://github.com/tcmbd02/table-reader/pull/1):
  - Pushed 2026-10-09 (user asked): everything up to session 7b (save-bug fix, clock reports, page-by-page picker,
    "Add employees from files", Company chooser, month grids, Million .xls, editable Employee No./Name in Results,
    script fingerprints). Scanned for real names first (clean).
- Before every later commit: scan the diff for personal data. **Merge only if the user says so.**

## 3. The user's data on this PC (personal data — do not paste contents into chat)

| What | Where |
|---|---|
| Source folder (September 2026, all companies A–Z) | `C:\Users\TENGA CEKAP\Documents\table-reader\9. SEPTEMBER 2026-20261006T081347Z-1-001\9. SEPTEMBER 2026` (git-ignored) |
| Read so far | Only names starting **A–D**: 62 files (85 pages), all finished. 4 Excel files skipped (not scans). **E–Z not read yet.** |
| Documents in the app | `Documents\Table Reader\jobs\` (61 of 62 have a company; 29 companies) |
| Old history (before the reset) | `Documents\Table Reader\jobs-backup-2026-10-07_1243\` (15 documents) — kept, not deleted |
| CSVs (snapshot taken right after reading) | `Documents\Table Reader\September 2026 A-D\` — 62 per-file CSVs + `September 2026 A-D (all files).csv` (1,274 rows, 492 columns) |
| Payroll plan | `Documents\Table Reader\payroll\2026-09.json`; remembered Employee Nos.: `payroll\employees.json` |

Open data points:
- **569 yellow cells** still to check across the 62 files (user's job; never auto-filled).
- The CSVs above are a snapshot: after the user corrects cells, **re-export** them and rebuild the merged file —
  and add a **Company** column next to **File** (promised to the user).
- One file is labelled AUGUST (cleaners' attendance) and has no company — user to decide.
- September payroll has 1 leftover empty employee (no cards, no company) — user may remove it.
- Possible same person with two spellings on two cards in one company (shown as two employees) — user to merge.

## 4. Next steps (agreed order)

> **New track (2026-10-09): replace Claude with open-source OCR so the app can be hosted on a server.** Plan only,
> nothing built: see `PLAN-OCR-ENGINE.md` (phases O0–O7). It waits on the user's answers to its §9 decisions;
> the first step will be the O0 bake-off on a hand-checked gold set.

1. **User:** check one employee from the clock report against Million Payroll (especially that report OT 2.0 belongs
   in "Overtime 2 Times (Hour)" and not in the "Work on Rest Day / Holiday (Day)" fields). Fix mapping first if wrong.
2. **User:** fix yellow cells in the date/hours columns of the cards going through payroll.
3. **IN/OUT time cards: done in session 9.** Open, for the user to decide (PROGRESS.md session 9): break on
   morning/afternoon pairs and on half days; rounding of overtime minutes; an option to read an OUT earlier than IN
   as afternoon (one real card writes 8.00 / 5.00 with no PM: 20 days are reported instead of guessed); night shifts.
   Possible next shapes: several stamps in one cell ("Times | Time"), day-per-column job sheets.
4. Month grids and the Million .xls: **done in session 7** (see PROGRESS.md). **User:** fill the September payroll
   (each company's Needs you, Employee Nos., mark PH in Month settings) → "Make the month's Million file" → drag it onto
   `Documents\learn-million\million-import-tools\Check Office File.bat` (its `employees.txt` must list the codes).
5. **Claude:** re-export CSVs (+ Company column); commit + update PR #1; later read letters E–Z with
   `tools\run_batch.py` (≈40 s/page of the user's Claude plan — tell the user the page count and time first).

## 5. How to run things

- Tests: `.venv\Scripts\python -m pytest -q`
- Build the app: `.\packaging\build.ps1` → `dist\Table Reader\` + `dist\Table Reader.zip`.
  **Table Reader must be closed first** (closing the window is not enough — use its Quit, or
  `Invoke-RestMethod -Method Post http://127.0.0.1:8765/api/quit`), and only when nothing is being read
  (check `GET /api/jobs` for status `queued`/`reading`). Start it again:
  `Start-Process "dist\Table Reader\Table Reader.exe"`. The user runs it from `dist\`, so rebuild after every change.
- Translation checks (need `.venv\Scripts\python -m pip install esprima`, dev only):
  `.venv\Scripts\python tools\check_i18n.py` and `tools\check_patterns.py`. **Every new UI text needs a Malay entry
  in `static/i18n.js`** (`MS` for page text, `MS_PATTERNS` for server sentences with names/numbers).
- Batch-read a folder through the running app: `tools\run_batch.py` (usage in its docstring).
- Real-data checks: write throwaway scripts that open `jobs.Jobs(jobs.default_root(), reader=lambda image: {})`
  read-only and print **counts / shapes only**, never names or values.

## 6. Decisions to keep (why things are the way they are)

- **Never guess** (CLAUDE.md). Unclear cells stay blank and flagged; payroll reports missing/unclear/conflicting days
  and marks the employee INCOMPLETE.
- Clock reports: daily figures are **decimal hours** (proved: sums match the printed totals; h.mm never did). On report
  days the normal-hours OT rule and rest/holiday day counts are **not** applied (no double pay). Flat OT and
  allowance columns are left to the user (reported).
- Employee No. is **never** taken from the clock system's Emp Code. Typed by the user, or (session 17, user's
  decision) taken from Million's list on a whole-name match, or made new from the company's name; then remembered.
- Same worker = same printed Emp Code → else same printed name → else same file name without
  company/month/year/copy numbers; a card with nothing printed joins the one worker whose other card has its file name.
- The Payroll results window copies Million Payroll's Edit Payroll screen: its labels stay English in both languages.
- Company of an employee = set on the employee, else the one company of their ticked files.
- Payroll CSV with a company chosen → only that company, file `Payroll <month> <company>.csv`.
- Known cosmetic caveat: in Windows dark mode the "white = working day" key is dark (swatch is still right).

## 7. Environment reminders

Windows, PowerShell 5.1 (no `&&`), Python 3.14 in `.venv`, no Node/npm. Bash tool available too (Git Bash).
`python -c "..."` loses quotes in PowerShell → write scripts to files. Heredocs in the Bash tool can fail on some
content → write files with the Write tool instead. Scratch files go in the session scratchpad, not the repo.
