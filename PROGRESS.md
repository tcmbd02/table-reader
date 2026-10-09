# Progress log

## Session 7b — 2026-10-09 — Office checker run, package rebuilt, ready to commit
303 tests pass. **Package rebuilt** (10:25, includes month grids + Million .xls). **Not committed yet** (waiting for the
user's OK; repo is public).
- **Office checker run** on Million files made from invented figures (`payroll.build_xls` + the office mapping):
  "READY TO IMPORT", all 51 headers match, every figure in the column the office setting reads (D/E 25, K 25, O 1,
  Q 2, AC 50, AK 30, AY 12.5). With invented Employee Nos. it reports each one as "not in employees.txt" — as it should.
  Only the real September file is still to be checked (needs the user's Employee Nos. first).
- **Rebuilt package checked** on an empty scratch data folder: the packaged .exe makes the .xls (xlwt and
  `million\office-mapping.csv` are inside), refuses an INCOMPLETE employee without allow_incomplete.
- `.gitignore`: `*.csv` was hiding the bundled `million/office-mapping.csv` (a fresh clone could not build or pass the
  mapping test) -> exception added.
- Before committing to the public repo: real client-company names taken out of this log and of a docstring in
  `payroll.py` (invented names instead). Scan of all added lines: no worker names, no document contents.
- Note: "Hours of Worked" is never worked out (0 unless the user types it) — by design since session 5.
- **3. Results: Employee No. and Name are typing boxes** (`pw-empno`, `pw-name` in `static/payroll.js`; same plan
  fields as section 2, which follows after the save).
- **"Download Million file (.xls)" did nothing** (user's report). The server answered correctly (September: 400
  MILLION_INCOMPLETE, 200 with allow_incomplete). Likely cause: the page and scripts were served with no Cache-Control,
  so after the rebuild the browser showed the new page (with the button) beside an old `payroll.js` (no click handler).
  Now every non-API answer has `Cache-Control: no-cache` (test added, 304 pass). Package rebuilt again (10:4x).
  Checked in headless Edge on the real plan: both boxes drawn, button enabled. **Not clicked in a browser** (Chrome
  extension still not connected) — the user should confirm the button now works.
- **User: "both still not working".** Only one app was running and it served the new code, so the browser was still
  running an old script (a plain reload keeps scripts it already has). Now `app.page_html` serves index.html with each
  script/style address stamped with the file's fingerprint (`payroll.js?v=…`), so an update always loads. Test added
  (305 pass); package rebuilt and restarted (opens a fresh tab).
- **Type-and-click test in headless Edge** (scratch data, app from source, test script added to the page): typing in
  the Results boxes keeps focus through the save, section 2 + title + server follow; the Million button asks about the
  INCOMPLETE employee, then downloads `Payroll 2026-09 (Million).xls`; no script errors. Scripts for this are scratch
  only (not in the repo).
- **Next:** user's OK -> commit + push + update PR #1. User: fill September payroll (Employee Nos., PH) -> download the
  Million .xls -> `Check Office File.bat`. Then IN/OUT time cards (still not started; rule in NEXT-SESSION.md §4).

## Session 7 — 2026-10-09 — Month grids (several workers per sheet) + Million .xls export
303 tests pass; Malay checks pass (96 server messages, 0 missing). **Not committed, package NOT rebuilt, office checker
NOT run yet.**
- **Month grids** ("Name | 1…31 | Remark", one row per worker): `payroll.grid_columns/grid_mark/document_parts`, refs
  `<id>#p<page>r<row>` (`split_part`, `part_suffix`). Each worker's row is offered separately in the picker and by
  "Add employees from files" (name from the row, never from the header; unclear-name rows listed as `unnamed`). Marks:
  ✓ / P / 1 = worked (normal day, no OT), hours = hours, 0/O/-/x = absent, PH, OFF/RO/RD, leave AL/MC/… ; anything
  else (S, SU…) = unclear, reported. PH on a calendar working day -> `daytype` (blocks Complete). Remark/Total checked
  against worked or worked+PH. Whole multi-worker grid on one employee -> issue. Real data: one company's grid -> 4 workers,
  each 25 working / 25 worked / 1 PH, complete (scan checked by eye: all four rows really identical). All files: 12
  multi-worker grids, 43 rows offered, 12 with an unclear name.
- **Million .xls** (`payroll.build_xls`, `GET /api/payroll/{month}/xls?company=&allow_incomplete=`, button "Download
  Million file (.xls)"): xlwt BIFF8, sheet "Import", columns from office-mapping.csv (learn-million, else bundled
  `million/office-mapping.csv`, else `OFFICE_MAPPING`), A text, C–AY numbers (0 written), AZ Notes. Refuses with every
  problem listed (empty/spaced/duplicate Employee No., bad numbers, non-zero figure with no office column: Encashing
  Leave, Maternity Leave, loan cleaner, Zakat/Levy paid by individual, unknown lines); INCOMPLETE only with
  allow_incomplete. New default lines: Transport Allowance, use and claim, PENALTY, RENTAL CAR, rental hostel, ZAKAT.
  Saved as `Payroll <month> [<company>] (Million).xls` in Documents\Table Reader\payroll. `xlwt` + `xlrd` (tests) added.
- Real September plan (2 employees: one empty leftover, one INCOMPLETE) is refused, as it should be.
- **Next:** user fills the September payroll (Add employees from files, Employee Nos., mark PH) -> make the .xls ->
  run the office checker (`million-import-checker.ps1 -Mapping office-mapping.csv -Path <xls> -NoOpen -NoPause`) ->
  rebuild with `packaging\build.ps1` (quit the running app first) -> commit. OCR engine bake-off (session 6, `ocr-lab\`)
  is paused.

## Session 6 — 2026-10-09 — Plan: open-source OCR instead of Claude (for server hosting)
Plan only, no code changed: `PLAN-OCR-ENGINE.md`. Sample folder counted (counts only): 91 photos, 82 scanned PDFs,
30 digital PDFs with a real text layer (79 of 220 PDF pages), 10 Excel files. Key points: Tesseract cannot keep
today's handwriting quality, so the plan uses engines chosen per page (Excel/text layer exact → classic OCR for print →
self-hosted document model on a GPU for handwriting, Claude kept as a fallback), all feeding the existing never-guess
normaliser. First step is a measured bake-off (O0). Waiting on the user's decisions in its §9.

## Session 5f — 2026-10-07 — Payroll: save bug, clock-system reports, one worker per page
261 tests pass; package rebuilt. Not committed yet (branch `payroll-companies-malay`, PR #1).
- **Bug:** a ticked document that no longer existed (history reset) made `validate_plan` refuse *every* save, so the
  results never changed. Now `app.drop_gone_documents` takes such documents off the employee (on GET and PUT) with an
  issue of kind `removed`; the page copies the cleaned `jobs` back after each save.
- Real Sept A–D data (85 pages): only 29 pages had a daily-total column. Card types: clock-system reports (17 pages,
  printed Actual/Late/EarlyOut/OverTime per day), IN/OUT cards, month grids "Name | 1…31" (many workers per sheet).
- **Clock-system reports** (user's choice, done): columns matched by label (`REPORT_*` in payroll.py). Printed daily
  figures are decimal hours — proved by the report totals (h.mm reading never matched). Late→lateness,
  EarlyOut→early_departure, OverTime 1.0/1.5/2.0/3.0→ot_1/ot_1_5/ot_2/ot_3, Actual→days worked; normal-hours rule and
  rest/holiday day counts not applied on report days (no double pay). Column sums checked against printed totals
  (kind `total`, blocks Complete); Flat OT reported (kind `flat`), allowance columns not used. Real data: all 17
  worker pages give exactly the printed totals.
- **One worker per page:** a document whose pages show different Emp Code/Name is offered page by page in the
  picker (`payroll.worker_parts`, refs `<id>#p<page>`, `split_ref`); a page and its whole document cannot both be chosen.
- **"Add employees from files"** (section 2 of Payroll, per company or all): `payroll.auto_employees` makes one
  employee per worker among the readable documents (those with an hours column), cards ticked; documents it cannot
  read yet are listed. Same worker = same printed Emp Code, else same printed name (`_WORKER_LABEL`: Name, Nama / name,
  Cleaner Name, Emp Code…), else same file name without company/month/year/copy numbers (`name_from_file`); a card
  with nothing printed joins the one worker whose other card has its file name. `worker_key` is kept on the employee;
  `remember_employees` saves Employee No./name per worker_key in `payroll/employees.json` on every save and the next
  month's auto-add fills them in. Employee No. is never taken from the clock system's Emp Code.
  Dry run on Sept A–D: 34 employees (one company 17 by code, two others 3×2 and 6×2 cards), 34 files left
  out (IN/OUT cards, grids, other forms). 266 tests.
- **Company chooser in the top bar** (user's request; replaces the filter above Recent files): `#company-box`,
  remembered in localStorage (`companyFilter`), redrawn only when its options change. It filters Recent files and the
  Payroll screen: employees list + results navigation show only that company's employees (`empCompany`: the
  employee's `company`, else the one company of their ticked files — same rule as `payroll.employee_company`);
  "Add employees from files" uses it; new employees get it as `company`; "Download payroll CSV" sends `?company=` and
  the file is "Payroll <month> <company>.csv". 268 tests.
- **Next (user chose 1-hour break rule for later):** IN/OUT cards (hours = OUT − IN − break, rule shown and
  changeable); month grids (pick a row per employee).

## Session 5e — 2026-10-07 — Bahasa Melayu
253 tests pass; package rebuilt. Not checked in a browser (Chrome extension not connected).
- Header button "Bahasa Melayu" / "English" switches the language (kept in the browser's localStorage, page reloads).
- `static/i18n.js` (loaded first): `t(text, vars)` page text keyed by the English text, `tn(n, one, many)` plurals,
  `tm(text)` server messages: exact entries, then `MS_PATTERNS` for sentences with names/numbers (also old error messages
  saved in job.json). Unknown text stays English. `index.html` text marked `data-t` / `data-t-title` / `data-t-aria`.
  Server and CSV unchanged (English).
- Kept in English on purpose: the payroll results window (copy of Million Payroll's Edit Payroll screen) and both CSVs
  (import into Million Payroll), and Claude's own notes/cell reasons (Claude's reading). The guide PDF is English only.
- Checks (scratch scripts, not in tests/): all scripts parse (esprima); every `t()`/`tn()`/`data-t` text has a Malay
  entry (167 texts); 49 server messages incl. real payroll issues match an entry or pattern. When adding UI text, add
  the Malay entry to `MS` in `static/i18n.js`.

## Session 5d — 2026-10-07 — Recent files filtered by client company
252 tests pass (3 new); package rebuilt. Not checked in a browser (Chrome extension not connected).
- Each file has a `company` in `job.json` ("" = none; older files read as ""). The company is **never worked out from the
  name on its own**: the user sets it once ("Set company" chip → box pre-filled with a suggestion: month/year and the last
  word taken off, e.g. "MAJU JAYA ALI SEPT 26" → "MAJU JAYA"). Then `Jobs.set_company` also files every file with no
  company whose name starts with that company (whole words, any capitals/spaces), and new uploads are matched against
  known companies (`company_for`, longest first). Same company typed differently joins the existing spelling.
- `PUT /api/jobs/{id}/company {"company": "..."}` → `{"moved": n}`.
- Home: "Company" dropdown beside "Recent files" (All / each company with counts / No company yet), remembered in the
  browser. The list does not refresh while a company box is open.
- Payroll file picker: a "Company" dropdown beside "Find a file…" for each employee (screen only, not saved). It starts on
  the company of the employee's ticked files (if they share one); a new employee starts on the previous employee's company.
  Ticked files always stay visible. `documents` in the payroll API now carry `company`. 253 tests; package rebuilt.

## Session 5c — 2026-10-07 — Leave table + Allowance & Deduction tab
249 tests pass (3 new). Package **not** rebuilt yet. Page not checked in a browser (Chrome extension not connected);
API checked with a throwaway data folder.
- Basic Pay & Overtime tab: Leave table (Leave | Type | Taken | Balance) bottom-left; "Please check" and day-by-day moved
  below the two tables. Balance is greyed out (kept in Million Payroll). Taken is typed by the user (never read from cards).
- New Allowance & Deduction tab: Allowance, Deduction, Benefit In Kind (BIK) tables (Rate typed per employee), User Defined
  Entry (Zakat / Levy paid by individual), Message.
- The lines are company lists in the month plan (`plan.lists`, defaults = the lines on the user's screenshots; the
  Deduction list there was cut off by a scrollbar). "+ Add a … line" / "×" change the list for every employee; a new month
  copies the lists of the latest saved month. Per employee: `entries`, `zakat`, `levy`, `message`.
- CSV: one column per line (`Leave: Annual Leave (Day)`, `Allowance: …`, `Deduction: …`, `Benefit In Kind (BIK): …`),
  then Zakat, Levy, Message, Notes.
- Still not reproduced: Arrears tab, Overtime Pay Period dates.

## Session 5b — 2026-10-07 — two fixes from the first real use
246 tests pass; package rebuilt.
- **Claude console windows popping up** (packaged app only): the windowed .exe has no console, so every `claude` start
  (status check + each page) opened one. Fixed with `creationflags=CREATE_NO_WINDOW` (`ocr.NO_WINDOW`) on the status check
  and the page runner (tests added). Checked with the rebuilt .exe during a real read: `claude.exe` ran, no visible window.
- **Payroll results now look like Million Payroll's Edit Payroll screen** (`static/payroll.js`, `app.css`): title bar,
  Employee No./Name boxes, "Month End Pay - September, 2026", the Basic Pay & Overtime tab with the three grey panels
  (Basic Rate/Director Fee/Back Pay greyed out — not on time cards; Working Days/Public Holiday/Days Worked/Hours of Worked;
  Lateness/Early Departure/No Pay Hour/Encashing Leave with Hour(s)/Day(s)), the Overtime table (Overtime | Unit | Hrs/Days),
  First/Previous/Next/Last between employees. Bottom-left slot (Leave table on the real screen) shows "Please check" and
  the day-by-day working. Not reproduced: Leave table, Allowance & Deduction and Arrears tabs, Overtime Pay Period dates
  (nothing to fill them from).

## Session 5 — 2026-10-07 — Payroll step (Million Payroll month-end figures)
244 tests pass (`tests/test_payroll.py` + payroll API tests).
- Flow kept: read → user corrects → generic CSV. New **Payroll** screen (header link, `#/payroll/yyyy-mm`) turns the
  *confirmed* cells into one row per employee in the Edit Payroll screen's terms and downloads `Payroll yyyy-mm.csv`.
- The "template" was taken from the 3 screenshots in `screenshots\` (Edit Payroll: Basic Pay & Overtime, Allowance &
  Deduction, Arrears). **No real Million Payroll import file was available**, so the column headings follow the screen
  labels (Employee No., Name, Month End Pay, Working Days, Public Holiday, Days Worked, Hours of Worked, Lateness,
  Early Departure, No Pay Hour, Encashing Leave, six overtime rates, Notes). If its importer needs other headings/order,
  change `payroll.FIELDS` / `build_csv`. Allowances, deductions, arrears, rates, leave balances are not on time cards: not output.
- `payroll.py` rules (worked out from a real sample employee: 2 half-month cards ↔ Days Worked 25, Working Days 25, OT 1.5 = 25 h,
  2 Times Work on Holiday = 1 day): per employee, daily hours come from the cards' Total column (or a chosen column);
  Working Days = days marked work; Days Worked = work days with hours > 0; OT 1.5 Times = hours above the normal hours
  (default 8, editable) on those days; rest-day work and public-holiday work are counted in days (not hours); Public
  Holiday = holidays not worked. Sundays start as rest days; the user marks public holidays on a calendar (Malaysia Day
  16 Sept in the example). Any figure can be typed over (`overrides`, shown with a blue edge and "use worked-out value").
- Never-guess in the calculation: a day whose hours cell is still yellow/unclear, a date for another month, text that is
  not hours, a day written twice with different hours, days with no entry, no hours column, or no Employee No. is listed
  under "Please check" and the row is marked **INCOMPLETE** in the CSV Notes column; unclear days are left out, not assumed.
  Corrections made in the document view flow through automatically.
- Employees are typed in the screen (Employee No. exactly as in Million Payroll); several documents (cards) can belong to
  one employee, each document to one employee only. Plans are saved per month in `Documents\Table Reader\payroll\`.
- Checked: example reproduces 25/25/25 h/1 day in tests; visual check in headless Edge (an unclear day 28 gives 24 and
  "Needs checking"). Live check with real Claude readings of the sample employee's two cards: totals read as 9/dash, but several
  Totals were flagged this run → user presses "Use this" first (then 25/25/25/1 expected; not yet confirmed end to end).
- Open: real import file format; other form types (tick grids, salary lists, logbooks) need their own mapping; leave /
  lateness / early departure are not derived (type over); employee list is typed by hand (could import Million Payroll's list).

## Session 4 — 2026-10-07 — Phase 5 (packaging) built; clean-PC test still to do
**Status: package built and tested on this laptop only.** 209 tests pass.
- Build: `.\packaging\build.ps1` → `dist\Table Reader\` (PyInstaller onedir, no console window, ~49 MB) and
  `dist\Table Reader.zip` (25 MB). Contains `Table Reader.exe`, `Install Table Reader.bat` + `install.ps1`, and the guide.
- Install (staff): unzip, double-click **Install Table Reader.bat** → copies to `%LOCALAPPDATA%\Table Reader`, desktop
  shortcut “Table Reader”, no admin rights; stops a running copy first; warns if Claude Code is not found.
- App changes for packaging: **Quit Table Reader** button (`POST /api/quit`; running reads are cancelled so they can be
  continued; confirm if files are being read), `GET /api/activity`, `Jobs.shutdown`; `start.py` has no console, logs
  warnings to `Documents\Table Reader\table-reader.log` (`TABLE_READER_DEBUG=1` for detail), second launch just
  re-opens the page; `ocr.cli_path()` also looks in `~\.local\bin` (desktop shortcuts may lack it on PATH).
- Found and fixed: start-up took 45 s because probing 20 closed ports takes ~2 s each on Windows → bind test; now ~6 s
  (first ever launch may be slower while Windows scans the files).
- Tested with the built .exe: page served, Claude status, real PDF upload read by real Claude (done, CSV + page image),
  Quit, relaunch, double launch, installer into a test folder + shortcut launches the installed copy.
- Guide: `packaging\Table Reader guide.pdf` (one A4 page, screenshots made from invented data; source
  `packaging\guide\guide.html`, regenerate with Edge `--print-to-pdf`). Icon: `packaging\make_icon.py`.
- NOT done / risks: **test on a clean Windows PC with only Claude Code** (plan's “done when”); the .exe is unsigned, so
  Windows SmartScreen / antivirus may warn (a code-signing certificate or IT allow-listing fixes it); no auto-update;
  `build\` and `dist\` are generated folders. Phase 6 (pilot) next.

## Session 3d — 2026-10-07 — Speed: timing, compact answer format (idea 1), inline image (idea 2) tested
207 tests pass.
- **Timing**: every page record now has `timing` (seconds, looks, Claude seconds and output tokens per look, model,
  effort, format). `bench.py run|compare` (counts and times only, no cell text printed) for before/after checks.
- **Where the time goes**: writing the answer. ~190 output tokens/s, so a page with ~5–7k tokens takes 30–40 s.
- **Compact answer format is now the default** (`ocr.COMPACT_SCHEMA/COMPACT_PROMPT`, `expand_compact`): rows are plain
  strings in column order; only doubted cells are listed in `doubts` (row, column, marks, reason). Same never-guess
  handling afterwards (short rows flagged, extra cells keep a column, a doubt that points at no cell goes to notes).
  `TABLE_READER_FORMAT=full` switches back (old format still supported by the validator and normaliser).
- **Benchmark, 6 files (4 JPEG, 2 PDF page 1), Sonnet 5.5 medium, one at a time**: full 155 s / 27,210 output tokens →
  compact 71 s / 7,595 tokens (2.2× faster; 20 s→10 s on clean PDFs, 35–40 s→14 s on photos). Same rows on every file.
- **Accuracy NOT proven equal**: cell-by-cell the two formats mostly agree (293 agree, 19 differ — 18 of them a
  descriptive word in a signature column that differs between runs; a few flags move both ways). But the same photo
  read repeatedly gives very different amounts of flagging even in one format (hard logbook photo: full 17/20/5 flagged,
  compact 7/2/21). So run-to-run noise on hard photos is bigger than any format effect; judge compact in the pilot with
  a human check of unflagged cells.
- **Idea 2 (inline image instead of the Read tool)**: works with `--input-format stream-json --tools ""` (2 turns
  instead of 3) but gave no speed-up (31.5 s vs 28.3 s on one page) and needs a more fragile stream parser. Not adopted.
- Still possible: parallel reading (2–3 pages at once), lower effort on clean pages, quicker orientation check.
- Finding for the pilot: a hard handwritten photo is flagged inconsistently (2–21 cells) from run to run.

## Session 3c — 2026-10-07 — fixes and Cancel
- **Use this** now saves the cell at once (it only filled the box before, so the cell stayed flagged).
- Model fixed in `ocr.py`: `MODEL = "claude-sonnet-5-5"`, `EFFORT = "medium"` (`--model/--effort` on every call).
  Earlier accuracy notes in this file were made with Claude Code's default model.
- **Cancel reading**: `Jobs.cancel(id)`, `POST /api/jobs/{id}/cancel`, “Cancel reading” button on the document and
  “Cancel” on active files in Recent. `ocr._run_cli` (Popen, checks twice a second, kills the CLI process tree on cancel or
  timeout; per-thread event via `ocr.set_cancel_event`). A cancelled file is `failed` with code `CANCELLED` (shown as
  “Cancelled”, not an error); finished pages kept; **Continue** carries on. A waiting file can be cancelled and continued
  without an “already reading” error. 198 tests pass. Live check with real Claude: cancel 2 s into a read stopped it in
  2.7 s and left no extra `claude` processes.

## Session 3b — 2026-10-07 — Phase 4 (plain-language errors) done
189 tests pass. Changes:
- `ocr.parse_cli_output`: plan-limit wording is checked before sign-in wording (a limit message can mention "login");
  messages now say to press **Sign in** / **Continue**.
- `app.py`: per page `problem` (blurry/dark → “take the photo again…”, otherwise “no table found…”); `can_continue`
  (false for damaged/oversize/wrong-type files, where Continue would just fail again); unexpected server errors return
  a plain JSON message (no stack trace); disk-full on upload is reported (`SAVE_FAILED`).
- `static/app.js`: problem banner per page; “no table could be read” status; Download disabled when nothing was read;
  sign-in/CLI-missing failures refresh the top-right Claude box at once; non-retryable failures point to “All files”;
  failure to load the recent list is shown instead of ignored.
- Not covered: real expired-sign-in and real plan-limit wording from the CLI (only simulated text); `auth status` may
  still say signed in while the token has expired, in which case the page fails with the sign-in message at read time.

## Session 3 — 2026-10-07 — Phase 3 (the screen) built
**Status: Phase 3 built and smoke-tested; not yet tried by a person.** 184 tests pass (7 new in `tests/test_app.py`,
fake reader, no Claude; needs `httpx2`, added to requirements).
- `app.py` (`create_app(jobs=None)`): endpoints from PLAN §5 plus `POST /api/jobs/{id}/resume` and `GET /api/ping`.
  `GET /api/jobs/{id}` returns the job + merged pages (Claude's reading + corrections). Errors → `{code,message}` JSON.
  Safety: rejects any Host that is not localhost, and POST/PUT with a foreign Origin; uploads ≤150 MB per file; bad files
  are reported while the others still go ahead.
- `start.py`: picks a free port from 8765, opens the browser, re-opens the existing window if already running.
- `static/index.html|app.css|app.js` (plain JS, text inserted via textContent): Claude status/Sign in box, drop zone
  (disabled until signed in), recent files (live while reading), document view with page picture beside the table,
  yellow flagged cells (reason + “Claude saw: …” + **Use this** / **It's empty**), inline edit (Enter saves, Esc cancels),
  **Undo my change**, “Go to next cell to check”, Continue (resume), Download CSV (asks if cells are still yellow).
- Checked in headless Edge against the real server: page loads, Claude status shows connected, document view renders
  header fields, notes, flagged cell and tools. NOT checked: clicking/typing, drag-and-drop, a real upload through the
  browser, PDFs with many pages, small-screen layout. Someone should click through it once (`python start.py`).
- Known gaps: no delete-job; the Recent list shows no “cells to check” count; progress text is generic (about a minute
  per page); `class="secondary"` button has no special style. Phase 4 = review error wording; Phase 5 = PyInstaller.

## Session 2 — 2026-10-06 — Rotation detection + Phase 2 (Jobs + CSV) built and tested

**Status: Phase 2 done. Stopped; waiting for the user's go-ahead for Phase 3 (the screen).** 177 tests pass
(`.\.venv\Scripts\python.exe -m pytest -q`; none need Claude).

### Rotation detection (`ocr.py`) — decided with the user at the start of the session
- Schema has a new required field `rotate_clockwise_degrees` (0/90/180/270). On a non-zero answer Claude is told not
  to transcribe; the page is turned and shown again. Up to `MAX_LOOKS = 3` looks: Claude sometimes picks the wrong
  direction (said 90 for a page needing 270), the next look then sees it upside down and adds 180. The last look must
  transcribe whatever it sees; if it still says "turn", a note “Claude was not sure which way up this page is” is added.
- `read_image` returns the usual page record plus `rotated_clockwise` (total turn applied). The job stores the page
  image turned upright so the viewer shows it the right way.
- Live check on the 3 originally-problem photos: sideways logbook 0 rows → 29 rows (turned 270); sideways tick grid →
  30 of 33 cells read, 1 flagged (turned 270); upright time card correctly left at 0. Costs 2–3 Claude calls (≈1–3 min)
  only for sideways pages.
- Prompt additions found by live testing: “Transcribe every row… never stop part-way” (it had stopped after 3 of 29 rows,
  honestly saying so) and “a blank box / unsigned signature space / dotted fill-in line is blank, not unclear”.
  `normalize_cell` also treats a raw_text that is only dots/underscores/`…`/`---` (with no value and no reason) as empty.

### Phase 2 files
- `pages.py` — `render_pages(path, out_dir)` PDF (pypdfium2, 200 dpi, ≤2400 px) or picture (EXIF-upright, multi-frame
  TIFF) → `page-N.png`; reuses existing page images (so resumed jobs keep turned pages); `turn_page` turns a stored page
  in place; plain-language errors (damaged/password PDF, >100 pages, wrong type).
- `jobs.py` — class `Jobs(root, reader=None)` (reader defaults to `ocr.read_image`; tests inject a fake):
  - Folder `<Documents>\Table Reader\jobs\<yyyy-mm-dd_hhmm>_<name>\` (real Documents folder via Windows, so OneDrive
    redirection works; override with env `TABLE_READER_HOME`) containing `original\`, `pages\`, `reading\page-N.json`
    (each page's reading, written once), `result.json` (all pages, written once at the end, never edited), `edits.json`,
    `job.json`, `<name>.csv`.
  - API for Phase 3: `create_job(filename, bytes)`, `list_jobs()`, `get_job(id)` (status, `pages_done/pages_total`,
    `error{code,message}`, `cells_to_check`), `resume(id)`, `load_result(id)` (partial while running), `load_edits(id)`,
    `save_edits(id, changes)`, `page_path(id, n)`, `write_csv(id)`, `wait_idle()`; module functions `merged_pages`
    (Claude's reading + corrections, each cell with `value`, `edited`, `needs_review`, `claude_value`, `raw_text`),
    `count_to_check`, `build_csv`.
  - Status: `queued → reading → done | failed`. One background worker reads **one document at a time** (also the "already
    reading" busy lock: `resume` on a running job raises `JOB_BUSY`). A failure keeps finished pages; `resume` carries on
    from the next page. A plan-limit / sign-in / CLI-missing failure also marks the waiting documents as stopped instead
    of repeating the failure. Jobs left "reading" when the app was closed are marked `INTERRUPTED` at start-up and can be
    continued. Unexpected crashes give a plain message (no stack trace) and the worker keeps going.
  - Corrections (`edits.json`): `{"page","row","column","value"}` or `{"page","header","value"}` (0-based row/header
    positions). `""` = "checked, really empty"; `None` takes a correction back. A batch is all-or-nothing and validated
    against the real cells. A flagged cell stays "to check" until corrected (or confirmed empty).
  - CSV: UTF-8 with BOM, CRLF; columns = form fields (union over pages) + `Page` + table columns (union) + `Notes`;
    duplicate names get ` (2)`. Uncertain, uncorrected cells are **blank** and described in `Notes` (reason + marks seen),
    so nothing uncertain looks certain; corrected cells are clean. Cells that would run as Excel formulas (`=`, `@`, `+`/`-`
    followed by a letter) get a leading `'`.
- Tests: `tests/test_pages.py`, `tests/test_jobs.py`, shared builders in `tests/helpers.py`. Mutation-checked: making the
  CSV print raw marks into uncertain cells fails a test.

### Live end-to-end (real Claude, scratch folder, not Documents): 3 files, 424 s total
2-page PDF (2 pages read, 56 CSV rows), small table (4 rows, 0 to check), sideways logbook (turned 270, 28 rows, 147
cells to check). `result.json` byte-identical after a correction; CSVs have the BOM. A two-minute stall on the first
document was caused by my own parallel test competing for the plan, not by the code.

### Known issues / decisions for later
- **CSV and Excel:** Excel will turn `07:26` into a time (fine) but will drop leading zeros of IC/phone numbers and may
  round 16+ digit numbers. Not handled yet; options: wrap such values as `="0123"` or a text-format xlsx. Decide with the
  user in Phase 3/4 once real HR use is known.
- A flagged form field puts its note on every row of that page in the CSV (verbose but keeps the doubt visible per row).
- Logbook-style photos at 960×1280 are still mostly flagged (147 of ~290 cells): resolution/legibility, not logic.
- Speed: 25–90 s per upright page; sideways pages 1–3 minutes. Phase 3 must show honest progress text.
- No delete-job, no CSV-per-batch (decision: per document), no model setting. `types.py` not needed.

### Next: Phase 3 — the screen (waiting for go-ahead)
`app.py` (FastAPI, endpoints in PLAN §5 over `Jobs`), `start.py`, `static/index.html|app.js|app.css`: Claude status/
sign-in box (`ocr.auth_status`, `ocr.start_login`), drop zone, progress per file, table beside the page image, yellow
flagged cells with the reason on hover and `raw_text` offered as a one-click suggestion, inline edit → `save_edits`,
Download CSV, Recent files. Then Phase 4 (error wording), 5 (PyInstaller), 6 (pilot).

---

## Session 1 — 2026-10-06 — Phase 1 (Engine) built and tested

### Decisions made (PLAN.md §8)
- App name: **Table Reader**.
- CSV: **one per document**.
- Form fields (Name, Month…): **leading columns on every row**.
- Sample forms: the user's folder `9. SEPTEMBER 2026-…\9. SEPTEMBER 2026` (≈200 time cards, logbooks, tick grids,
  salary lists; JPEG / PDF / PNG / Excel). **Read-only: never write into it, never add files to it.** Test on small
  selections (10 files at a time) before any bigger run.

### Done
- `.venv` (Python 3.14.8) + `requirements.txt` (fastapi, uvicorn, python-multipart, pypdfium2, pillow, pytest;
  pyinstaller commented out until Phase 5). Run things with `.\.venv\Scripts\python.exe`.
- `ocr.py`: generic prompt + schema, schema validator, CLI runner, sign-in status/launcher, "never guess" normaliser.
  `python ocr.py <jpg|png> [-o out.json] [--model M] [--timeout S]` prints validated JSON; failures print
  `[CODE] plain-language message` and exit 1.
- `tests/test_ocr.py`: 71 tests, all passing, none need Claude (schema validation, CLI-output parsing and error
  classification, never-guess rules, auth status, image preparation, `read_image` with a faked CLI, `main`).
  Checked that they fail when the never-guess line is deliberately broken.
- Live test on 10 real files (below): all 10 ran without errors, 8–85 s per page (typically ~40 s).

### How `ocr.py` works / differences from the PayTrace reference
- Per page: copy of the image → upright (EXIF), RGB, ≤2400 px, PNG in an empty temp folder → `claude -p
  --output-format json --json-schema … --tools Read --permission-mode dontAsk --no-session-persistence
  --strict-mcp-config --disable-slash-commands` with that folder as cwd. `ANTHROPIC_API_KEY`,
  `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_*` are removed from the CLI environment. API-key sign-ins are rejected
  (`authMethod` must be `claude.ai`). The app never sees credentials.
- Generic schema: `quality`, `header_fields[{label, cell}]`, `column_labels`, `rows[{cells[{column, cell}]}]`, `notes`.
  Removed from the PayTrace schema: `document_type*`, `totals` (a totals row is an ordinary row; totals written outside
  the table go to `header_fields`), `bbox` (not needed while the table is shown beside the image; add later only if
  Phase 3 wants to jump to a cell). Cell = `value, raw_text, confidence, unclear_reason`.
- **Never-guess normaliser** (`normalize_page`, applied before anything is saved): a cell keeps its `value` only if it
  has a value, no `unclear_reason`, no `?` in `raw_text`, and confidence ≥ 70 (`UNSURE_BELOW`). Otherwise
  `value=None`, `raw_text` (Claude's best marks) is kept, a reason is filled in if missing, and
  `needs_review=true`. A cell Claude omitted from a row is flagged (“Claude did not report this cell”), not treated
  as empty. Rows are made rectangular; duplicate column labels become `IN`, `IN (2)`; unlisted columns are added.
- Processed cell shape: `{value, raw_text, confidence, unclear_reason, needs_review}`; page record:
  `{quality, header_fields, column_labels, rows:[{cells:{<column>: cell}}], notes}`. This is what Phase 2 saves as
  `result.json` (then never edited).
- Not in Phase 1 (deferred on purpose): PDF input (`pages.py`, Phase 2), the per-document “already reading” lock
  (belongs with job folders, Phase 2), `types.py` (plain dicts are enough).

### Live test results (10 files)
| # | File type | Quality | Rows | Values | Blank | Flagged | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Time card photo, small stamped times (JPEG) | FADED | 16 | 31 | 69 | 28 | Stamped times left blank + flagged; `raw_text` has Claude's best reading |
| 2 | Bilingual time card photo (JPEG) | FADED | 16 | 30 | 74 | 24 | Same pattern; handwritten OFFDAY/PH noted |
| 3 | Handwritten + printed attendance log, 30 rows (JPEG) | MOSTLY_CLEAR | 30 | 117 | 30 | 3 | Unlabelled columns → `COL1`, `COL2` |
| 4 | Handwritten sign-in logbook (JPEG) | MOSTLY_CLEAR | 19 | 92 | 0 | 3 | **Checked all 19 rows by eye: every time matches;** the one ambiguous date was left blank + flagged |
| 5 | Dense handwritten logbook, rotated 90°, no EXIF (JPEG, 960×1280) | ILLEGIBLE | 0 | – | – | – | **Failed.** Rotated upright by hand: 29 rows, 57 values, 149 flagged |
| 6 | Tick-grid attendance form, rotated (PNG, 9.9 MB) | MOSTLY_CLEAR | 1 | 0 | 0 | 33 | **All flagged** (could not align marks). Rotated upright: 30 values, 1 flagged; marks consistent with real weekends |
| 7 | Small 3-column table (JPEG) | CLEAR | 4 | 9 | 3 | 0 | Exactly matches the image |
| 8 | Printed report, PDF page 1 | CLEAR | 21 | 147 | 0 | 0 | 4 header fields; not checked cell-by-cell |
| 9 | Scanned 31-day grid, rotated, PDF page 1 | MOSTLY_CLEAR | 9 | 252 | 36 | 0 | Claude warns row/total alignment needs checking; not checked cell-by-cell |
| 10 | Scanned salary table, rotated, PDF page 1 | CLEAR | 12 | 192 | 36 | 0 | 19 columns, duplicate labels disambiguated; not checked cell-by-cell |

Only #4 and #7 were verified cell-by-cell against the original; #1 and #6 partly. #8–#10 need a human check before
trusting the accuracy claim. Names of staff are personal data — don't paste result JSON into chat.

### Findings / issues to decide next
1. **Sideways or upside-down photos are the biggest accuracy risk.** Phone photos without an EXIF flag came out
   rotated; two of ten files failed or were all-flagged because of it (#5, #6), and both read well once upright.
   Suggested fix (small): add a `rotate_clockwise_degrees` (0/90/180/270) field to the schema; if non-zero, rotate the
   page with Pillow and read again (second Claude call only for rotated pages). Needs the user's OK because it doubles
   time/quota on those pages.
2. **Small stamped times on time cards** (#1, #2) are mostly blanked as low-confidence. Safe, but the user will have to
   confirm many cells. Phase 3 should show `raw_text` as a one-click suggestion in the highlighted cell. Possible
   accuracy lever: send the page at higher resolution / in two halves (images are downscaled by Claude to ~1.5k px).
3. Threshold `UNSURE_BELOW = 70` is a guess; measure in the pilot (Phase 6).
4. Speed ~40 s/page (8–85 s). Plan said 10–20 s; update expectations / progress text.
5. Claude's `notes` sometimes contain useful warnings (alignment, cropped edge). Show them above the table in Phase 3.

### Next: Phase 2 — Jobs + CSV (waiting for the user's go-ahead)
- `pages.py`: PDF → page PNGs (pypdfium2, `render_pages` from the reference) and images (EXIF-rotated).
- `jobs.py`: job folders `Documents\Table Reader\jobs\<yyyy-mm-dd_hhmm>_<name>\` with original, pages, `result.json`
  (Claude's reading, never edited), `edits.json`, CSV; background reading with page progress; per-document busy lock;
  resume after plan-limit errors without re-reading finished pages.
- CSV builder: UTF-8 with BOM, form fields as leading columns, `Page` and `Notes` columns, edits applied over
  `result.json`; uncertain-and-uncorrected cells stay blank.
- Decide finding 1 (rotation) before or during Phase 2.
