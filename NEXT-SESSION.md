# Next session — start here

Handoff written 2026-10-07, updated 2026-10-09 (session 7b). Read this first, then `PROGRESS.md` (newest entries at the top,
sessions 5–7b) and `PLAN.md`. Project rules are in `CLAUDE.md` (never guess; personal data stays on this PC).

**To continue, paste this into the new session:**

> Read NEXT-SESSION.md (section 0 first) and PROGRESS.md (sessions 9 to 12), then let's continue.

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
- **Still open:** September itself is Processed and still lacks the two workers (un-process / re-create: the user
  decides). October holds September figures as test data — clear or overwrite before the real October payroll.
- Built in session 9: the warning before download when an Employee No. is not in `employees.txt` (which now lists
  all 3 codes of this laptop's Million).

## 1. Where things stand

| Area | State |
|---|---|
| Reading scans/photos → table → CSV | Working. Packaged app in `dist\Table Reader\` (rebuilt 2026-10-09, latest code). |
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
| **Million import file (.xls)** for the office | **Done (session 7).** Button "Download Million file (.xls)"; the office checker says READY on invented figures. Real September file not made yet (needs Employee Nos.). |
| Browser check | Never clicked through by Claude (Chrome extension was not connected). All checks were tests + API + real-data scripts. |

Tests: **365 pass** (`.venv\Scripts\python -m pytest -q`). Package rebuilt in session 9. Session 9 is committed and pushed (02ebcfc); **session 9b is not committed.**

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
   (Add employees from files, Employee Nos., mark PH) → "Download Million file (.xls)" → drag it onto
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
- Employee No. is **never** taken from the clock system's Emp Code; typed once by the user, then remembered.
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
