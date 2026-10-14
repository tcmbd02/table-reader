# Progress log

## Session 24 - 2026-10-14 - Three steps: Upload, Check reading, Payroll
The user asked for one workflow of three pages with buttons between them. Spec
`docs/superpowers/specs/2026-10-14-three-step-workflow-design.md`, plan `docs/superpowers/plans/2026-10-14-three-step-workflow.md`
(8 tasks, built in this session). Branch `three-steps` (from `pdf-text`), **merged into `pdf-text` and the app
rebuilt on the user's OK (local, not pushed; `download` branch and PDF guide not updated).**
555 tests pass; Malay checks pass (0 missing, 0 not translated).
- **The page:** three step buttons at the top (**1 Upload**, **2 Check reading** with the number of yellow cells left,
  **3 Payroll** with the number of things that need the user) replace the Payroll link. Everything opens in the same
  tab; each step remembers in this tab where the user was (sessionStorage, safe when refused).
- **1 Upload:** the drop box, the Inbox / Tables folders, and **Just added** (files added in this tab and every file
  being read), then **Check them →**.
- **2 Check reading:** files on the left (Company and Month filters; "All months" shows yellow cells only), the file on
  the right with **This file needs you** above its table (whose card, which month, unknown card layout, no company, set
  aside / another month), the column choice opened in place (`#/check/<file>/columns/<page>`), and **Next file with
  yellow cells →**, **See … in payroll →**, **Go to payroll for … →**.
- **3 Payroll:** the month bar as before; the month's companies and employees in one list (search, ! / ✓); an employee
  on the right with their Needs you, cards (**Check this card →**), the Edit Payroll window, **‹ Previous** /
  **Next needing you ›**, and Look in place (`.../e/<id>/look`); a company heading shows its settings, pay preview, Add
  employee and New in Million.
- **Server:** `GET /api/payroll/{month}/people` (step 3) and `GET /api/payroll/{month}/files` (step 2), built from the
  same month workings; the job list carries each file's cells to check (cached on the files' size and time: 0.01 s for
  63 real files). `GET .../companies` and `.../company` are gone; old addresses (`#/doc/…`, `.../look/…`,
  `.../layout/…`, `.../old`) open the matching new place.
- **Removed:** the start page's Recent files, the month overview, the company screen, the separate Look and Layout
  pages, new tabs (`static/companies.js` → `people.js`, `layout.js` → `columns.js`, new `upload.js`, `check.js`,
  `steps.js`).
- **A company's status in step 3 no longer counts its files' problems** (they are in step 2; the company says "N files
  need you in step 2").
- **Click-throughs** now live in `tools/clickthrough/` (made-up data; `sh tools/clickthrough/run.sh <scenario>`; needs
  dev-only `websockets`): `upload_page`, `check_page`, `check_reading` (with `SLOW_FILE=1`), `people_page`,
  `employee_page`, `cross_steps` — all "No problems". The harness never counted failed checks before (it was imported twice); fixed.
- **Real September data (copies, counts only, deleted):** 87 employees' figures identical before and after, the month
  file 9 ready / 78 held both times, and the same file problems (29 cards on nobody, 3 unknown layouts).
- **Guides:** both long guides (sections A-C) and the quick guide's text rewritten for the three steps. The PDF and its
  pictures were not regenerated (needs the user's OK).
- **Review** (one fresh reviewer, whole branch): "with fixes", 0 critical, 4 important, 9 minor. Fixed, each with a
  click-through that failed first: a step entered from another step asks the server again (a file left while being
  read showed its progress for ever; "See … in payroll" after placing a card on a new employee opened someone else);
  "… need you in step 2 →" puts step 2 back on the month (not "All months") and opens the first file with something
  to settle (the company's button: that company, Company chooser set to it); what joined by itself and new Employee
  Nos. are kept from step 2's opening of the month and said in step 3; step 3 says when step 2's Company chooser
  filters its list ("Show all companies"); the Month list is no longer rebuilt every 4 s. New scenario `cross_steps`.
  Seven minor findings left (listed in the session's final message).
- Rulings taken during the build are listed in the session's final message.

## Session 23 - 2026-10-14 - Stage 4 Part B: the employee view, the pay preview tab, Add employee; the old page removed
Built on branch `employee-view` (from `pdf-text` after Part C), Tasks 4-10 of
`docs/superpowers/plans/2026-10-14-company-first-payroll-stage-4.md`. **Merged into `pdf-text` and the app rebuilt on the
user's OK (local, not pushed; `download` branch and PDF guide not updated).** 549 tests pass (530 on `pdf-text`); Malay checks pass.
- **How it started:** an earlier session had begun Part B in the main folder (`Documents\table-reader`): Task 4
  committed, Task 5 half-done and not saved. On the user's word ("do it here") the unsaved work was moved into this
  worktree (identical apart from one joined line, fixed), and the main folder was put back on `pdf-text`, clean.
- **Server (Tasks 4-5):** `GET / PUT / DELETE /api/payroll/{month}/employee/{id}` (one change at a time:
  `{"changes": {key: value}}`, only the keys sent are changed), `POST /employee` (Add employee; in a company it gets a
  new number), `POST /take-off`, `PUT /lists`, `GET /pay?company=`, and `"move": true` on `/place`. An employee removed
  in another tab: every call says "This employee is no longer in the payroll of this month…" (also `/place`, which said
  `BAD_PAYROLL` before). A card read with a confirmed layout map is marked `mapped`.
- **The employee view (Task 6)**, `#/payroll/<month>/e/<id>`, opened in a new tab by "Open employee":
  - the Edit Payroll window ported from the old page (labels English), without First/Previous/Next/Last;
  - the employee's cards: Open the card, **Move to** another employee of the company or a new one, **Take off**; the
    Hours column; Remove employee;
  - a card with a confirmed layout says "the Hours column list does not apply to this card"; a day's note shows both
    the mapped / report figures and how its IN/OUT times were read (also "OUT … read as afternoon");
  - saving: text boxes after 500 ms without typing, number boxes and selects when changed, one request after the
    other; a box being typed in keeps its text when another save redraws the window; Back sends what is waiting.
  - shared helpers moved from `payroll.js` to `static/paycommon.js`.
- **Company screen (Task 7):** tabs **Employees / Pay preview** (always opens on Employees; no Pay preview for files with
  no company, where it would list every company), the pay table with total row and its CSV, and **Add employee**
  (opens the new employee's view in a new tab).
- **The old page is gone (Tasks 8-9):** `static/payroll.js`, its screen, the "Old payroll page" link, its styles, and
  the endpoints only it used (`GET` / `PUT /api/payroll/{month}`, `/auto`, `/xls`). An old address still open or
  bookmarked opens a real screen (`.../old` = the month overview, `.../old/e/<id>` = the employee view). The tests that
  used those endpoints were ported to the new ones (25), 3 were deleted with their reason in the commit message.
- **Found and fixed on the way:** a card layout address opened in a fresh tab (or reloaded) showed the start page: the
  first route ran in `look.js`, before `layout.js` was loaded. It now runs in the last script.
- **Lost with the old page (minor, for the user to know):** the note "N time-card files chosen before are no longer in
  Recent files, so they were taken off this employee" (the card is still taken off; the note is not shown anywhere);
  the per-company Million file with its "make it anyway" questions (the month file holds back such employees and says
  why; there is no "anyway" for an INCOMPLETE employee any more); "Give … employees a new number" and "Use all …
  suggested" in one click (numbers are given when the month is opened, offers are one click each on the company screen).
- **Real September data (copy, counts only, deleted afterwards):** all 84 employees' figures, problems and pay are
  identical between `pdf-text` and `employee-view`; the employee view equals the company screen's figures for all 84;
  the month file still has 8 ready and 76 held.
- **Clicked through** in headless Edge on made-up data (MAJU JAYA: ALI, SITI, ZUL on a confirmed layout, AMIN's August
  card): the view, the pay tab and Add employee, the old addresses and every screen, and after the review the other
  files list, a stale tab's Take off and adding one line; no script error.
- **Guides:** `GUIDE - Table Reader to Million.html` and `PANDUAN - Table Reader ke Million.html`, sections B and C, now
  describe the month, a company and its Needs you, the employee view, New in Million and the month's file with its
  summary first. The PDF guide was not regenerated.
- **Whole-branch review (fresh reviewer): "ready with fixes", no critical, 3 important, 7 minor.** Fixed, each important
  one with a test that failed first; 549 tests pass; the real September check repeated after the fixes (identical):
  1. a stale tab's Take off / Move could take a card off whoever had it by then (another tab had moved it): the view
     now says which employee the card was on, and the server refuses "That card is no longer on this employee";
  2. the line lists were saved whole, so a tab opened before another tab added "Transport" took the line (and every
     employee's figures on it) away when it added "Meal": now one line is added or removed at a time;
  3. a file set aside by mistake as "Not a time card", or a card whose month was read wrongly, could no longer be put
     right (only the old page's tick list could): the company screen now lists such files of the company, folded under
     Needs you, with "It is for <month>". They are not items, so no status or count changes (real month: 1 file);
  - smaller: the view's reloads now wait for its saves; a failed save keeps newer typing; a name box keeps a trailing
    space while typing; overrides that are not figures gave a crash (now refused); remembered Employee Nos. are updated
    under the lock; the Pay preview's Monthly/Daily follows where the rate comes from; "Untick it from the other
    employee first" now says "Take it off"; the PDF guide's source paragraph (`packaging/guide/guide.html`) describes the
    new screens (the PDF itself is not regenerated).
  - Left: no automated test for the routes (`#/payroll/<m>/old`, `/old/e/<id>`, `/e/<id>`); the click-throughs check
    them. Malay entries of removed texts are left in `i18n.js` (harmless).
- **Open for the user:** merge `employee-view` into `pdf-text`, rebuild the app, push, update the `download` branch and
  regenerate the PDF guide (each needs your OK); the questions still open from session 22 (rest-day work with an OT
  column mapped, overtime on rest days / holidays as days, should the CSV buttons ask about "Needs checking").

## Session 22 - 2026-10-14 - Stage 4 Part C: conversion (what Claude reads correctly now reaches Million's fields)
Built on branch `conversion` (from `pdf-text`), then **merged into `pdf-text` (fast-forward, local, not pushed) and the app rebuilt** on the user's OK; the rebuilt app shows 5 card-layout items on the real month (the 4 counted + the door export). 530 tests pass; Malay checks
pass. Plan: `docs/superpowers/plans/2026-10-14-company-first-payroll-stage-4.md`, Tasks 11-17.
- **The hours column is never a money or minutes column** (`pick_columns`): "TOTAL (RM)" and "E/Out(Min)" were taken as
  the daily hours. A column named exactly for hours (WHrs, Total, Jumlah) is preferred. A column the user chose still
  wins.
- **The user's rules:**
  - an OUT with no am/pm that is earlier than a morning IN is afternoon (8.00 / 5.00 -> 17:00, said in Day by day);
    an OUT with am, a night shift, or OUT = IN stay unclear;
  - "530 pm" is a clock time;
  - SA on a Saturday and SU on a Sunday in a month grid mean not worked; elsewhere they stay unclear.
- **Month grids whose day columns carry the weekday** ("1 / TUE", "1 Tuesday", Malay "1 Sel") are grids. Found by the
  real-data proof: such a sheet was read as a time card, with the "No." column taken as dates.
- **Layout maps** (`payroll.py`: `layout_signature`, `valid_layout_map`, `_layout_columns`, `columns_read`,
  `map_as_read`; `layouts.py`; `PayrollStore.load_layouts` / `save_layouts`, `payroll\layouts.json`):
  - For a card layout Table Reader does not know, the user says once what each column means: date, hours, IN, OUT,
    several clock times in one cell, lateness, early departure, overtime 1.0 / 1.5 / 2.0 / 3.0, not used. Figures can
    be in hours or minutes.
  - The map is kept for every company and month with the same headings.
  - Mapped figures go to Million's fields like the clock report's (added up as written, no normal-hours overtime rule
    on those days).
  - Several clock times in one cell are paired in order; an odd number is reported.
- **Claude's suggestion** (`layouts.suggest`, `ocr.ask_text`): text only.
  - Claude sees the headings and up to 5 rows with every value reduced to its shape: digits as 9, letters as A, apart
    from marks and time words (PH, OFF, am, OT...). Never names or figures.
  - The answer is checked like the user's map and used only after Save.
  - Claude is asked only when the user presses "Ask Claude".
- **Company screen:** a "Needs you" item, "a card layout Table Reader does not know", appears once per unconfirmed
  layout. It needs a column the calculation does not read that holds figures in 3 rows or more (row numbers and codes
  such as "No." and "Emp. No." do not count). Grids and the Shift Details report are never asked about. Its buttons:
  **Check the columns** (the panel: per column how it is written, what it means and its unit, Ask Claude, Save) and
  **It is right as it is** (today's reading kept, the rest not used).
- **Real September data** (copy, counts only, no layout confirmed yet):
  - 6 employees changed and 78 are identical. Causes: hours column 2, SA/SU 2, afternoon OUT 1, "530 pm" 1.
  - Unclear or unreadable problem lines 309 -> 262. Complete employees 40 -> 42.
  - With every Employee No. known, 39 would go into the file (was 37).
  - 4 layouts would be asked about: the second clock report (two heading variants) and two other clock-system
    exports; one of them splits overtime into norm / rest / holiday / off, which the roles cannot express yet.
  - The clock report now reads its WHrs; where its pages repeat days with different hours, that is reported instead
    of reading 0.
- **Clicked through** in the app's browser pane on made-up data, with Claude's answer replaced by a fixed one: the
  item, the panel on today's reading, Ask Claude preselecting, one role changed, Save (OT 1.5 0 -> 60, item gone),
  "It is right as it is" on another layout. Not looked at by eye.
- **Open for the user:**
  - ~~one real Claude call~~ **done on the user's OK (after they signed in to Claude again: three earlier tries failed
    with "Failed to refresh OAuth token", a half-finished sign-in renewal):** Claude answered in 8 s, the answer passed
    `valid_layout_map`, and WHrs = hours (hours), OT = overtime 1.5 (hours), LIn(Min) = lateness (minutes) and
    E/Out(Min) = early departure (minutes) all matched; In / Out as IN / OUT, DATE as date, every other column "ignore".
    Nothing saved. So the CLI accepts `--tools ""` with `--json-schema`;
  - with an OT column mapped, Sunday work no longer counts as "Rest day" days (the report's own OT is trusted, as
    with the Shift Details report): is that right for these reports?
  - roles for overtime on rest days and holidays as days;
  - should the payroll CSV buttons ask about "Needs checking" employees.
- Two tests (`test_company_can_be_set_and_is_listed`, `test_the_month_run_makes_one_file_and_lists_who_is_held_back`)
  each failed once in a full run and passed in every run after: timing flakes, not caused here.
- **Whole-branch review (fresh reviewer): "with fixes", 2 critical, 5 important, 8 minor. All 7 fixed, each with a
  test that failed first; 530 tests pass:**
  - a saved map whose headings differ only in capitals or spacing crashed every month view;
  - "It is right as it is" turned days flagged today (empty Total, times in other columns) into silent 0-hour days;
  - mapped figure columns were dropped on IN/OUT and stamp days;
  - a map with lateness only wiped out overtime and rest-day work;
  - "It is right as it is" ignored the employee's chosen hours column;
  - a confirmed layout could never be reopened. A layout whose map cannot work out the days now comes back as an
    item, and its sentence says "Open the card layout";
  - door exports (several times in one cell) never got an item.

  Also found while clicking through the fixes: after a save, the panel's Save stayed disabled in that tab (fixed).
- **Left for later (minor):**
  - two "hours" columns are accepted;
  - a wrong value in a minutes column says "not a number of hours";
  - Malay "minit" / "gaji" are not in the never-hours words;
  - the panel offers "It is right as it is" also over a saved map;
  - a hand-made request could map the clock report;
  - **a question for the user:** a 24-hour OUT "00:30" after a morning IN is read as 12:30 pm by the afternoon rule.

## Session 21b - 2026-10-14 - Why read cards do not reach Million; Part C (conversion) added to the plan
The user: Claude reads the tables well, but some data is not converted into the file Million imports. Measured on a copy
of the real September data (counts only, scripts in the session scratchpad, copies deleted afterwards):
- **Only 8 of 84 employees reach the month's Million file.** 67 are stopped first by "Employee No. not in Million's
  list": the list imported on this laptop is the test Million (7 employees), and most numbers were made by Table Reader.
  Also 4 numbers that Million has under another name, 4 shared numbers and 1 empty number. The month file names only
  the first reason, so this hides the next one.
- **If every Employee No. were known, 37 would go in and 42 would stay INCOMPLETE.** Among the incomplete employees:
  - 312 lines with yellow cells (179 IN/OUT times, 60 grid marks): to be accepted, with the one-look panel;
  - 20 employees with days missing (mostly a half-month card not there);
  - 22 days on two cards with different hours;
  - 8 employees with no card.
- **Conversion failures on cards read correctly:**
  - **wrong hours column, which can give wrong figures without warning**: on a second clock-report layout (`WDays |
    WHrs | E/Ot | OT | LIn(Min) | … | E/Out(Min)`) the early-out minutes column was taken as the daily hours (that
    worker: 0 days worked), and on a salary-deduction list `TOTAL (RM)` was taken as hours;
  - OUT written without pm and earlier than IN (IN 8, OUT 5.00): 20 days;
  - "SA" / "SU" in month-grid cells, always on Saturdays and Sundays: 16;
  - "530 pm" and other formats: about 15 cells;
  - the clock report's OT and minute columns never reach Million;
  - 5 files no rule fits (a door-system export with several stamps in one cell; a grid headed "1 Tuesday…"; one whose
    headings were not read). The rest of those 5 are not time cards (a leave form, a lorry log, a cleaning list).
- No figure was lost to the office's File Format Setting (no "no column for it" refusal).
- **The user's decisions:**
  - conversion before Part B;
  - an OUT with no am/pm that is earlier than IN is afternoon;
  - SA is Saturday and SU is Sunday: on their own weekday they mean not worked, and Sunday work is overtime (rest-day
    work, already so);
  - unknown layouts: Claude suggests what the columns mean, the user confirms once (Phase C).
- **The plan gained Part C** (`docs/superpowers/plans/2026-10-14-company-first-payroll-stage-4.md`, Tasks 11-17,
  branch `conversion`), to run before Part B. Not built yet.

## Session 21 - 2026-10-14 - Company-first payroll, stage 4 planned; Part A: summary before the file, New in Million
Plan: `docs/superpowers/plans/2026-10-14-company-first-payroll-stage-4.md`. Stage 4 is split in two parts, each merged
and shippable by itself: **Part A** (this session) and **Part B** (employee view, pay preview tab, Add employee, then
the old page and the endpoints only it used are removed). Part A built on branch `million-summary` (from `pdf-text`),
then **merged into `pdf-text` (fast-forward, local, not pushed) and the app rebuilt** on the user's OK; the rebuilt app
answers the summary on the real month (8 in, 76 held back, no file written). 465 tests pass; Malay checks pass.
- **What the user sees:** "Make the month's Million file" first shows what the file would hold: per company the
  employees going in, then who is held back with the reason. **Make the file** makes it (worked out again then, so
  something fixed in between is in it); **Not now** closes the summary. A company with employees Million does not have
  yet shows **New in Million: n employees**: a list of Employee No. and name with **Copy** per row and **Copy all**
  (one line per employee, number and name separated by a tab, so it pastes into Excel as two columns), with how to
  create them in Million and export its list again. **Download payroll CSV** is on the month overview (every company)
  and on a company screen (that company).
- **How:** `GET /api/payroll/{month}/run` works the file out without writing it (`month_file(month, make)` shared with
  POST); each company in the answer lists `ready_people`. The held-back list is drawn by one function for both the
  summary and the result (`heldNodes`, payroll.js; moves in Part B). Copy falls back to the older copy command when
  the browser refuses the clipboard (the app's own browser pane refused it).
- **Real September data (copy, counts only):** all 84 employees identical before and after (same fingerprint);
  the summary's counts equal the made file's (8 in, 76 held back, 26 companies); the summary wrote no file.
- **Clicked through** in the app's browser pane on made-up data: offers accepted, "Ready, 1 waiting for Million", the
  New in Million panel, Copy all's text, summary / Not now / Make the file, both CSV addresses. Not looked at by eye
  (screenshots time out while the app window is minimized); the real Windows clipboard was not written.
- **Whole-branch review (fresh reviewer): "with fixes", 0 critical, 1 important, 7 minor.** Fixed (each reproduced in
  the browser first, then gone): the CSV buttons replaced the screen with a raw English error when the file could not
  be saved (open in Excel); they now download in the page and show the reason in the banner, in Malay too. Also fixed
  (raised from minor): a summary that arrives after the user moved to another month was shown there, and its Make the
  file made that other month's file; the previous company's "New in Million" button stayed while another company
  loaded or failed to load. Left for later (minor): the old page asked "n employees are marked Needs checking ...
  download anyway?" before the CSV, the new buttons do not (decide before Part B removes the old page); a second Copy
  click within 1.5 s can leave the button reading "Copied"; the month-file button is not disabled on a month with no
  employees (the server's message is about downloading); an open summary is not redrawn on coming back to the tab
  (Make the file works everything out again, so the file is right); the layout not yet looked at by eye.

## Session 20 - 2026-10-12 - Company-first payroll, stage 3: month and company settings
Built on branch `company-settings` (from `pdf-text`), then **merged into `pdf-text` (fast-forward, local, not
pushed) and the app rebuilt** on the user's OK; the rebuilt app has Month settings and Company settings. 463 tests
pass; Malay checks pass. Plan: `docs/superpowers/plans/2026-10-12-company-first-payroll-stage-3.md`.
- **What the user sees:** **Month settings** on the month overview: the month's default (normal hours, break,
  calendar: click a day for working -> rest -> public holiday), saved with Save. **Company settings** on a company
  screen: "Same as the month's default" or "This company is different:" with its own hours, break and calendar (it
  starts as a copy of the default) and "Use the same settings for this company next month". The overview marks such a
  company "own settings". Its employees' figures (OT, rest days, Working Days, so also the Million file) follow its
  own settings; everyone else follows the default.
- **Next month:** a company with "next month" ticked starts the next month with the same hours and break, and a
  calendar where a weekday is a rest day if all its days were rest days this month (public holidays left out of that
  count, ruling); public holidays come from the new month's default only, never carried.
- **Decided while planning:** when the month's default is changed after a company got its own settings, that company
  gets a "Needs you" item ("the month's default changed after this company got its own settings") with **Open
  settings** and **It is right** (saves its settings again); nothing is copied by itself. Settings are saved with a
  Save button. The old page's "1. Month and days" still edits the default.
- **Storage:** the month file gains `companies` (only companies with their own set, with `keep` and `based_on` = the
  default when last saved). Old month files open unchanged.
- **Real September data (read-only, counts only):** all 84 employees identical before and after (no company has its
  own settings yet).
- **Checked in headless Edge on a made-up card:** 19/19 scripted clicks (own settings change the figures, overview
  mark, a public holiday in the default gives the item, It is right clears it, back to the default, bad hours refused);
  screenshots of the overview and the settings panel look right.
- **Whole-branch review (fresh reviewer): "with fixes", 0 critical, 1 important, 7 minor.** Fixed: an old payroll page
  open in another tab (Open employee opens one) wiped a company's own settings when it saved; the old page now never
  saves over them. Left for later (minor): a settings panel opened before the default changed elsewhere can clear the
  item on Save; a company with no files yet this month is not marked "own settings"; own settings under an old company
  name after a rename are not pointed out; "keep" sent as a non-true/false value by a hand-made request counts as
  true; the old page's "1. Month and days" does not say a company has its own settings; the item says "check its
  calendar" also when only hours or break changed; a stale old-page tab can still undo a Month settings change (goes
  away with the old page in stage 4).
- Next: stage 4 ("New in Million" list, the summary before the month file, removing the old page).

## Session 19 - 2026-10-12 - Company-first payroll, stage 2: the one-look panel
Built on branch `look-panel` (from `pdf-text`, which already held stage 1), then **merged into `pdf-text`
(fast-forward, local, not pushed) and the app rebuilt** on the user's OK; the rebuilt app serves the panel. 447 tests pass; Malay checks pass. Plan:
`docs/superpowers/plans/2026-10-12-company-first-payroll-stage-2.md`.
- **What the user sees:** on a company screen, an employee's "cells to check" item now says "n lines of the time cards
  to check" and has a **Look** button. It opens the panel (`#/payroll/<month>/look/<employee id>`, same tab): one card
  at a time ("Card 1 of 2", < >), the card's page on the left (click = closer view), on the right only the lines the
  calculation could not use, each labelled "Day 9 (row 9)" with a box per cell it reads there. A yellow box shows what
  Claude saw without a leading / trailing "?" (as the document page); a box that is empty or has a "?" inside says
  "Must be typed"; an empty one has a **Nothing written** button (the user says it is empty, never assumed).
  **Accept all n cells** stays disabled until every must-type box is typed, saves the card in one go, then shows the
  next card; after the last it goes back to the company screen, where the item has gone.
- **How:** the calculation itself says where each line problem is (`"at"` on unclear / date problems: document, page,
  row, day, the columns read), so the panel cannot drift from it. `companies.look_cards` builds the panel;
  GET `/api/payroll/{month}/look?employee=`; accepting goes through the existing cells endpoint, each correction marked
  `"via": "look"`. Claude's reading is untouched.
- **Decided with the user:** no highlight of the row on the picture (readings carry no positions, a box drawn anywhere
  would be a guess); built here, reviewed at the end by a fresh reviewer.
- **Decided while building (rulings):** a line labelled by its day does not repeat the date as a box (the date is a box
  only when it is the problem); a line with a problem that is not yellow (IN without OUT, "abc") is shown with the
  calculation's sentence, and only changed boxes of it are saved; "days that do not add up" items about one line get
  the Look button too, the others keep "Open employee"; "Nothing written" must be pressed again after paging away.
- **Real September data (read-only, counts only):** all 84 employees' figures and problem texts identical before and
  after; 26 employees have 313 lines for the panel; every unclear/date problem has its place (the last one, a sheet's
  mark in a day-31 column of a 30-day month, was found this way and added).
- **Checked in headless Edge on made-up cards:** 26/26 scripted clicks, then 13/13 after the review fix; the saved
  corrections carry `via: "look"`, the blank one saved as empty.
- **Whole-branch review (fresh reviewer): ready "with fixes", 0 critical, 1 important, 7 minor.** Fixed: Accept could
  write the panel's old prefill over a correction typed in another window since. Now each box tells the server how the
  cell looked when shown; if it was corrected since, nothing is saved ("This card was changed in another window...")
  and the panel shows what is saved. Left for later (minor): a problem sentence is hidden on a line that also has a
  yellow cell; "Nothing written" is lost when the panel redraws on coming back to the tab; if the save works but the
  reload fails Accept stays disabled until reload; the Accept label counts yellow boxes only; Escape does not clear
  "Nothing written"; the endpoint reads each card twice (a re-read in between could give an error); no test that a
  grid row's save lands on the document's row (the row number itself is tested).
- Not in stage 2: company settings (stage 3), "New in Million" and removing the old page (stage 4). Still open from
  before: do yellow cells count before they are accepted (asked, no answer; the panel makes accepting quick); does
  Million accept a 10-character Employee No.

## Session 18 - 2026-10-12 - Company-first payroll, stage 1: month overview and company screen
Branch `company-first` (from `pdf-text`), merged into `pdf-text` locally. **Not pushed.** 426 tests pass; Malay checks
pass. Design: `docs/superpowers/specs/2026-10-12-company-first-payroll-design.md`; plan:
`docs/superpowers/plans/2026-10-12-company-first-payroll-stage-1.md`.
- The user called the Payroll page terrible (matching ~100 files to ~84 employees by scrolling). Decisions taken with
  them: one company at a time; only the problems; one look per employee for yellow cells (stage 2); one Million file at
  month end; a "New in Million" list now, a Million import test later; a month default with per-company exceptions.
- **Built (stage 1 of 4):** `companies.py` (pure: the calculation's problems -> "Needs you" items, Employee No. items,
  company status, month overview; no arithmetic). `app.py`: `open_month` (shared by the old page and the new
  screens), GET `/api/payroll/{month}/companies` and `/company?name=`, POST `/place` (a card on an employee or a new
  one), POST `/api/payroll/file-month` (the month of a file that prints none, or "not a time card"; kept in
  `payroll\file-months.json`), PUT `/employees/{id}` (accept the number Million offers). `static/companies.js`: the two
  screens. Payroll now opens on the overview; the old page is at `#/payroll/<month>/old` ("Old payroll page") and opens
  on the right company and employee when an employee is clicked.
- An employee the month file would hold back for a reason no item names gets a "held" item with the reasons, so a
  company is never "Ready" while the file would leave someone out (`payroll.month_run` now returns the employee id).
- A damaged reading no longer breaks the page: it is that employee's problem ("could not be opened").
- **Real September data, on a copy (counts only): every calculated figure and problem is identical before and after**
  (84 employees, 36 complete, same fingerprint). The new screens show 30 rows (25 need the user, 2 ready, 3 ready and
  waiting for Million) and these items: 28 cards to check, 29 "days that do not add up", 20 cards on no employee,
  8 employees with no card, 8 Employee Nos. to fix, 1 offered number, 1 file with no company.
- **Checked in a real browser engine (headless Edge, made-up data, scripted clicks): 18 of 18** (an earlier note said
  19; it was a miscount). The Chrome extension was not connected, so nobody has looked at the layout with their eyes yet.
- **Merged into `pdf-text` (fast-forward, local) and the app rebuilt on the user's OK, before the review came back.**
- **Independent whole-branch review: no critical findings, 6 important.** Fixed after the rebuild (426 tests; **the
  running app does not have these fixes until it is rebuilt again**):
  1. An old plan that cannot be saved as it is (one card on two employees) blocked the overview as soon as a new file
     of the month was read, and a number was remembered for an employee never saved. Now such a plan is left alone
     completely until it is put right on the old page (`open_month`).
  2. Placing a card failed with "Something went wrong" when another document's reading was damaged. Now only the
     card's own document is opened.
  3. A file of the month that is nobody's card could not be set aside: "Not a time card" is now on that item too.
  4. The month file's reasons on a "held" item were not translated to Malay (now through `runReason`). No automated
     test: there is no JS test runner.
  5. A company could read "Ready, n waiting for Million" while the month file held that employee for a second reason;
     the reason is now shown.
  6. Speed (each screen reads every document several times): measured on the real September data, 0.7 s for the
     overview and for the largest company, the same as the old page. Left as it is.
- **Company chooser moved (user: it only works for the file list, so put it there):** it now sits beside "Recent
  files" on the start page and filters only that list. The old payroll page has its own chooser (`prFilter` in
  payroll.js, not remembered): a company screen opens the page on its company, the "Old payroll page" link on all
  companies. This also settles the review's point that opening an employee changed the start page's filter.
  Click-through repeated: 22 of 22. 427 tests.
- **Opening from a company screen is in a new tab (user's request):** "Open the card", "Open employee" and a click on
  an employee row open a new browser tab, so the "Needs you" list stays where it is; the old page takes the employee
  from its address (`#/payroll/<month>/old/e/<employee id>`) and shows their company. Coming back to the list's tab
  draws it again. Click-through 24 of 24, with the browser's "open a tab" call stood in for; a real second tab and the
  redraw on coming back were not exercised.
- Review findings left for later (minor): a refused action leaves the old list on screen until reload; "Not a time
  card" cannot be undone from the new screens; a hand-typed address with a bad `%` or month 13 shows a blank screen;
  a slow answer can draw under the wrong title after fast clicks; "Open employee" changes the Company chooser in the
  top bar; the old page open in a second tab can save over what the new screens did; a broken office-mapping file now
  blocks the overview (and tests read this PC's mapping file); one test's name promises "being read" but only tests a
  damaged reading; a damaged reading is listed under "days that do not add up"; upper/lower case differs between the
  overview's shared-number check and the month file's.
- Not in stage 1 (old page until then): the one-look panel (stage 2), company settings (3), the "New in Million"
  screen and removing the old page (4). Open from before: do yellow cells count before they are accepted (user asked,
  no answer); does Million accept a 10-character Employee No.

## Session 17 - 2026-10-12 - A new worker's Employee No. filled in from Million's list (whole name only)
402 tests pass; Malay checks pass. **Committed and pushed on `pdf-text` (390d7b0); app rebuilt and restarted; `download`
branch updated (700dd47: new zip, both Million guides); PR #2 description updated.**
- The user asked for the Employee No. to be put on an employee by itself after reading. Already there: a number typed
  once is remembered per worker; a partly fitting name gets the "Use ..." button. The user chose: fill in by itself
  only on a whole-name match.
- **Built (`payroll.fill_employee_nos`, called from `auto_employees`):** when an employee is made from the files
  ("Add employees from files" and files that join by themselves), the number comes from Million's imported list when
  the name **read on the card** (confirmed cell, not the file name) is the whole name of exactly one employee there
  (case and spacing aside), no other employee in the plan has that name, and nobody in the plan has that number. The
  number typed in an earlier month still wins. Marked `emp_no_million` on the employee: the page writes "From Million's
  list (same name). Change it if this is another person." beside the box until the number is changed (validate_plan
  drops the mark then). The message after adding says how many were filled in. Everything else stays a button.
- Only at the moment the employee is made: an employee already in the payroll, or a list imported later, gets the
  button as before.
- Real data, dry run in memory (counts only, single-worker files): 34 employees, 24 named on the card, 2 would get a
  number from Million's list (15 employees), 0 left to the button.
- **New Employee Nos. (user's request, same session; this replaces the earlier decision that a number is only ever
  typed):** an employee with no number gets one made from the company: first 7 letters and digits of its name in
  capitals + the next number, 3 digits (`payroll.company_prefix`, `new_employee_nos`; MAJU JAYA -> MAJUJAY001). Order
  when an employee is made from the files: number remembered from an earlier month -> Million's number on a whole-name
  match -> new number. Not when Million's list has a number to offer (the "Use ..." button), nor without a name or a
  company. The next number is one above the highest with that start in every saved month, the remembered workers and
  Million's list (`PayrollStore.used_employee_nos`), and a new number is remembered at once (`number_new_employees` in
  app.py), so another month cannot hand it to someone else. Marked `emp_no_new`; the page says "New number made by
  Table Reader. Create this employee in Million ..." until it is changed. Employees already in a payroll are not
  touched by themselves: a button "Give N employees without an Employee No. a new one" (confirm list) does it.
  402 tests pass; Malay checks pass.
- Real September payroll, dry run in memory (counts only): 84 employees, 17 have a number, 1 has a Million suggestion,
  62 would get a new number by the button, 4 stay empty (no company / no name). 26 companies, 26 different starts, 8
  shorter than 7 characters; longest number 10 characters.
- **Not checked: whether Million accepts a 10-character Employee No.** (numbers used so far are short). Try one
  employee in Million before relying on it. Companies whose names start with the same 7 letters share one number run.
  Million's imported list is one file: a worker of a company whose list was not imported looks "not recorded".
- **Yellow cells show what Claude saw, nothing else (user's request, same session):** the reason text, "Claude saw:",
  "Use this" and "It's empty" are gone from the document page (`paintCell` in app.js). The yellow box holds the marks
  Claude saw (a "?" at the start or end dropped, as the old button did); the reason is the tooltip. Enter in the box
  accepts what it shows (an empty box = the cell is empty); typing over it corrects it; just passing through does
  nothing. **Unchanged on purpose: a yellow cell is still unconfirmed** - blank in the CSV (with its note) and
  "unclear" in the payroll - because of the never-guess rule. **Asked the user** whether yellow readings should count
  without being accepted; not changed until they say so. `packaging/guide/guide.html` updated, its PDF not regenerated.
- Not clicked through in the browser (tests + syntax check only). Guides (EN, BM) say it; the PDF guide does not.
- **Follow-up, same day (user: "generate the Employee No. if it does not have one"), committed (0d96aa4), app rebuilt;
  September opened once through the new app: 66 employees numbered, 1 left to the "Use ..." button; payroll files backed
  up first in `Documents\Table Reader\payroll-backup-2026-10-12 before new numbers`. `download` branch still has the
  build before this one:**
  the month run listed 67 employees as "Employee No. is empty" because employees already in a payroll only got a
  number through the button. Now everyone without a number gets one when the month's Payroll page is opened (GET,
  under the lock, saved; `view["numbered"]`, message on the page), also an employee with no name (was skipped). Still
  not: no company, or Million's list has a number to offer (button). **These employees then show "Employee No. … is
  not in the Million employee list" in the month run until they are created in Million and its list is imported
  again** - Million only updates employees it has. 402 tests pass.
- The rebuilt app serves the new page script and offers the same 62 new numbers on September (counts only). The
  `download` worktree is `.claude\worktrees\download`.

## Session 16b - 2026-10-12 - Phase B: newly read files go into their month's payroll by themselves
397 tests pass; Malay checks pass (130 messages). **Committed and pushed on `pdf-text` (0045a5d, PR #2); app rebuilt
and restarted 2026-10-12** (nothing was being read). First start of the new app wrote the index: all 62 documents
"before", September payroll file untouched.
- **The month of a file** (`payroll.document_month`): the card's Month / Bulan / Period field (+ its Year / Tahun field,
  or a full date "01/09/2026") and the file name. A file name counts only with a year beside the month ("SEPT 2026",
  "SEPT26", "Sep-26"), so a worker named Mei / Jun is not a month; a 2-digit year is taken only within a year of today
  ("SEPT 15" is the 15th). Month words are whole words (MARKET is not March), English and Malay. No year anywhere: the latest
  such month up to next month. Two different months: none (reported). Real data (62 files): 60 September, 1 August
  (the cleaners' AUGUST file), 1 no month, none wrong.
- **When:** files are added when that month's Payroll page is opened (GET `/api/payroll/{month}`), never during a save
  or a download: the page keeps its own copy of the plan and would save over employees added behind it. Index
  `payroll\added-by-themselves.json` ({document id: month, or "before"}): written at app start with every document
  already there ("before": existing payrolls are not touched), then each file once; a file taken off an employee is
  not added again; a file ticked by hand is marked done. A lock covers the add and the PUT save.
- **How:** `auto_employees` (same grouping as "Add employees from files") with `addable` = the new files only; cards
  already chosen take part by file name, so a later card with no name printed joins its worker (`joined`). The page
  shows what was added / joined / left out (no days readable, unclear row names, no month found) once.
- Hours column option now says "Automatic (the Total column; the IN/OUT times on days it is empty)"; the IN/OUT legend
  explains the clocked-twice rule and that a written Total counts.
- Checked in the browser on invented cards (made-up worker, laid out like the user's two cards: bilingual labels, empty Total, morning IN +
  overtime OUT, OFF, PH, one smudged time): one employee with both cards, 24 days worked and 41 h OT (checked by hand),
  the smudged day and the PH on a working day reported; message shown once.
- Not built: Phase C (Claude names columns Table Reader does not know). A file still being read when the page is opened
  is added on a later visit.

## Session 16 - 2026-10-12 - Sessions 12b-15b committed; "Use this" drops a leading / trailing "?"
- Sessions 12b-15b committed and pushed on `pdf-text` (7bc162e, second commit of PR #2; description updated).
- The user's request: cells like "Claude saw: 18:50?" are usually right; stop the yellow, or drop the "?" on "Use this".
  **Kept yellow** (never-guess rule: a "?" is a character Claude could not read, `ocr.normalize_cell`). Changed: when
  the "?" is only at the start or end, the button saves the value without it and names it (`Use "18:50"`), so a
  reading like "18:5?" shows `Use "18:5"` and the missing digit is visible. A "?" inside ("1?:50") stays; "??" alone
  gets no Use button. Malay entry added; guide text updated. Checked in the browser on an invented card (throwaway data
  folder via `TABLE_READER_HOME`). 369 tests pass (front-end only, no new test: there is no JS test runner).
- **Found while looking at two cards of one worker that the user uploaded: a silent wrong result.** Cards with IN/OUT columns
  AND a Total column nobody fills in: the payroll took the empty Total as 0 hours every day, ignored the times and the
  yellow time cells, and called the employee COMPLETE with Days Worked 0. 18 cards, 11 of 83 September employees (7 of
  them "complete"); none had an Employee No., so none reached a Million file. Card (2) also had bilingual labels
  ("Sebelum T/Hari Before Noon / Masuk In") that were not taken as IN/OUT. Grouping the two cards into one employee
  already worked (file name).
- **Phase A built (user's choice: a written Total counts; build A then stop):** IN/OUT times count on days the Total
  is empty; bilingual IN/OUT labels paired (`clock_pairs`); a row with an empty Total and times / yellow cells in
  columns not known as IN/OUT is reported, not "not worked". Real data: exactly those 11 employees change, none is
  complete now (their days are unclear). 373 tests pass, Malay checks pass (128 messages).
- **Why so many days stay unclear (counts on all multi-pair cards):** 119 yellow times; and the commonest written
  pattern is morning IN + OVERTIME OUT (73 rows) or morning IN + afternoon OUT (22): one IN and one OUT across pairs,
  which today reads as "IN but no OUT". Words in time cells: OFF, OFF DAY(S), AHAD, PH, CUTI, MC (20 "not a clock time").
  User's decisions, built: **one IN and one OUT in a later pair = one span minus the month's break** (the existing
  break box next to Normal hours; "customable" was taken to mean that box - ask if per-employee was meant); **day
  words = day marks** as on month grids (`DAY_WORD_MARKS`: holiday / off / leave only, never "worked"; words split
  over cells are joined; added to GRID_MARKS: OFF DAY(S), REST DAY, AHAD = off; CUTI = leave; CUTI AM / CUTI UMUM =
  holiday). Real data after both: "IN but no OUT" 77 -> 3, "not a clock time" 20 -> 7; the 11 employees now have
  days worked 0-13 and the rest of their days wait on 139 yellow time cells. Other 72 employees unchanged.
  375 tests pass; Malay checks pass. **Not committed, app not rebuilt** (worktree branch
  `claude/use-this-question-mark`, to fast-forward into `pdf-text`). Phases B (finished files join the month's payroll
  by themselves) and C (Claude names unknown columns) wait for the user's go-ahead.

## Session 15b - 2026-10-09 - Process Pay on the three test employees (user's OK): what Million really calculates
Process Pay run on 100, 101, 102 in the October test month (~17:28), payslips read on screen (View Payslip).
Inputs for all three: Working Days 25, Public Holiday 1, overtime 2 / 10 / 4 / 1 hours (1.0 / 1.5 / 2.0 / 3.0),
Rest Day 2, Holiday Day 1.

| | 100: Daily 80, daily OT table | 101: Monthly 2080, monthly OT table | 102: Daily 80, MONTHLY OT table (the mistake) |
|---|---|---|---|
| Days Worked typed | 25 | 23 | 25 |
| Days Worked after processing | **24** | **24** | **24** |
| Basic Pay | 2,000.00 | 2,050.00 (2080 - 20 lateness - 10 no-pay hour) | 2,000.00 |
| OT rate per hour (1.0 / 1.5 / 2.0 / 3.0) | 10.42 / 15.62 / 20.83 / 31.25 | 10.00 / 15.00 / 20.00 / 30.00 | 0.40 / 0.60 / 0.80 / 1.20 |
| Rest Day / Holiday Day per day | 166.66 / 249.99 | 160.00 / 240.00 | 6.41 / 9.62 |
| Overtime total | 874.92 | 840.00 | **33.64** |
| Allowance | 50.00 (fixed Transport from the employee file) | 0 | 0 |
| Gross = Net | 2,924.92 | 2,890.00 | 2,033.64 |

- **Million works out Days Worked itself when pay is processed**: all three became 24 = Working Days 25 - Public
  Holiday 1, whatever was typed (25, 23, 25). So the Days Worked figure in the import file did not decide the pay in
  this test. Absence has to reach Million another way (the Absence / Non-Pay Leave lines, No Pay Hour) - not yet
  confirmed by a processed example.
- **Daily basic pay was 25 x 80** with Working Days 25, PH 1 (so the public holiday was paid, or Working Days is what
  is paid). **Open, important:** Table Reader sends Working Days WITHOUT the public holiday (25 work days + PH 1). If
  Million's Working Days is meant to include it (its own default is 26 a month), a Daily worker who worked all 25 days
  is paid 25 days instead of 26. To be settled with HR / the office before any real daily-rated payroll.
- **Daily overtime is not rate / 8 when the month has a public holiday**: the day's pay Million used was 83.33
  (= 2,000 / 24, basic pay / days worked), giving 10.42 an hour. Table Reader's pay preview uses 80 -> 840.00, Million
  874.92. Monthly matches the preview exactly (840.00). The preview is NOT changed yet (one sample).
- **Monthly: lateness and no-pay hours are taken off** at rate / 26 / 8 per hour (2 h + 1 h = 30.00).
- **The wrong overtime table costs the worker almost all overtime** (33.64 instead of 874.92): Million divided the
  day's pay by 26 and by 8 again. Nothing warns about it.
- **A fixed allowance in the employee file is paid** (Transport 50.00 on the payslip).
- EPF employee 0.0 %, employer 4.0 % on these test employees (the calculation text says so; their records have no
  I/C, age or nationality - not looked into).
- **A processed row can be reopened**: Edit on the row opens Edit Payroll with Save (the month still has unprocessed
  rows and no later month - September, fully processed with October after it, has no Edit). The payslip's own Edit
  lets EPF / SOCSO / EIS / PCB and the overtime lines be overridden by hand.
- **View Calculation** after processing is the EPF / SOCSO / PCB working (text, "Send to File"), not the pay inputs.
- **Second round started, not finished:** Absence 2 days was typed and saved for 100 and 101 (rows reopened after
  processing, NOT processed again); 102 was to get Public Holiday 0. Stopped because the user was working in the
  browser and the screen kept switching. An Edit Payroll window may still be open in Million (Close it).
  To finish: set 102's Public Holiday to 0, tick the three, Process Pay again, read the payslips.

## Session 15 - 2026-10-09 - Experiments inside Million (values entered in the October test month)
The user asked to try Million's functions with real entries. Backups first: previous one kept as
`mycompany_2026-10-09_1228_before-experiments.bak`, then a new Backup Database (~17:14). Only the October test payroll
and the test employees 100, 101, 102 were touched. **Process Pay was NOT run** (the app's safety check refused it; the
user decides). Nothing was deleted.
- **What was changed in Million (still there):**
  - Employee 100: Pay Basis Daily (was already), Pay Period Monthly (was Fortnightly), Basic Rate 80, Overtimes Table
    "for Daily Pay" (was "for Monthly Pay"), fixed Transport Allowance 50 in the employee file.
  - Employee 101: Basic Rate 2080 (Monthly). Employee 102: Pay Basis Daily, Basic Rate 80, Overtimes Table left on
    "for Monthly Pay" on purpose (to show what that mistake does once pay is processed).
  - October rows of 100 / 101 / 102: Quick Update "Update Basic Rate from Employee file"; overtime 2 / 10 / 4 / 1
    hours at 1.0 / 1.5 / 2.0 / 3.0, Rest Day 2, Holiday Day 1; for 101 also Days Worked 23 (of 25), Lateness 2,
    No Pay Hour 1. Status of the three rows: Saved. They were left ticked for Process Pay when the window closed.
- **Found out:**
  - **Changing Pay Basis does not change the Overtimes Table.** Both must be set by hand (employee 100 was Daily with
    the monthly table; Million gave no warning).
  - **A month's row keeps the Basic Rate and pay basis it was created with.** After the employee file changed, the
    October row still said 0.00 Monthly. Quick Update > General Update > "Update Basic Rate from Employee file" (for
    an employee range) brought it to 80.00 Daily. The row's Basic Rate box can also be typed over for one month.
  - **A fixed allowance typed in the employee file** (Allowance & Deduction tab, Rate) showed in the October row's
    Allowance & Deduction tab (seen after the Quick Update; not checked which of the two brought it there). The import
    file writes 0 into every allowance column, so **an import after that would set it back to 0** (earlier finding:
    mapped columns are overwritten) - not re-tested today.
  - Row status goes New -> Saved when the row is saved by hand (an import leaves it New) -> Processed.
  - **View Payslip** (Alt+V) shows every input of an employee on one screen, but all amounts are 0 until Process Pay.
    **View Calculation** is empty before processing and has a "Send to File" button (a possible source for an
    automatic check after processing - not seen with content yet).
  - Pay Basis choices: Monthly, Daily, Hourly. Pay Period: Monthly, Fortnightly. A Daily employee has optional
    "1st Half Rate / 2nd Half Rate" boxes.
  - **APS Generator** makes the bank and statutory files (Payroll, Bonus & Commission, EPF, SOCSO, EIS, PCB, ASN,
    Tabung Haji, Zakat) per bank and payroll; nothing was generated.
  - Typing by remote control: a grid cell needs two separate clicks before it takes keys; a key sent right after a
    click is lost; Tab order runs through the top boxes then into the Leave grid; **Escape closes the window**.
- **Still unknown (needs Process Pay):** whether Million's pay for a Daily employee equals rate x Days Worked plus
  the overtime table lines (the pay preview's formulas); what Public Holiday not worked pays a Daily employee; how
  Days Worked below Working Days, Lateness and No Pay Hour reduce a Monthly employee's pay; what the monthly overtime
  table does to a Daily employee; what View Calculation > Send to File contains.
- **Not tried:** creating a new month (does everyone get added?), Holiday > Generate, the import onto a fixed allowance.

## Session 14 - 2026-10-09 - Pay basis and rate from Million's report; pay preview with Million's formulas
369 tests pass; Malay checks pass. **Package rebuilt and restarted. Not committed (branch `pdf-text`, on top of PR #2).**
- **Million's "Payroll Information" report now also gives Branch, Pay Basis and Basic Rate**
  (`parse_million_employees`; stored in `payroll\million-employees.json` on this PC - so salaries are now kept there,
  the user agreed by asking for this). The Employment Listing report gives the Basic Rate only.
- **Pay terms in force** (`payroll.pay_terms`): what is typed for the employee counts; while no rate is typed, Million's
  Pay Basis and Basic Rate for that Employee No. are used (`rate_source` "typed" / "million" / none). Results show
  "From Million: ...", or a warning when what is typed differs from Million. A Pay Basis other than Monthly / Daily
  (e.g. Hourly) gives no preview. Branch is read and kept but not used for the company yet.
- **Pay preview** (`payroll.pay_preview`, `OT_LINES`, 26 days x 8 hours as in Million's Work Table / overtime tables on
  this PC): basic pay (Daily: rate x Days Worked; Monthly: the rate), each overtime line (hour = a day's pay / 8 x 1,
  1.5, 2, 3; Rest Day worked = a day's pay x 2; Holiday Day worked = x 3), allowances and deductions as typed, and
  "Estimated pay before EPF, SOCSO and tax". Not taken off: absence, lateness, unpaid leave. No EPF / SOCSO / tax.
  Shown under the Basic Rate box in Results and in section "4. Pay preview"; CSV `Basic pay <month>.csv` has every line.
- **Caution:** Table Reader's own labels for the last two lines say "1 Time - Work on Rest Day" and "2 Times - Work on
  Holiday" (copied from the Edit Payroll screen), while this PC's Million tables pay x 2 and x 3. The preview follows
  the tables. If the office Million's tables differ, `OT_LINES` must follow them.
- **Real data:** the report on disk (15 employees) says Monthly for all, one with a rate; that employee has no number
  in Table Reader's plan, so no preview comes from Million yet. Checked in the browser with a typed test rate (Daily,
  then Monthly), then put back. Million itself was not asked to process a pay to compare the preview against.

## Session 13 - 2026-10-09 - Survey of Million Payroll's functions (read-only, nothing built)
Looked at through desktop control; nothing saved. Opened: every top menu and the Employee submenus, Payroll list
(Add, Organize, Quick Update), Work Table, Overtime tables, Holiday, General Setup. NOT opened: Leave, Loan, Piecework,
Salary Increment, Historical Data, B/F Payroll, Payment Advice, APS Generator, Bank, Statutory Setting, the government
and 12-month / year-to-date reports, Reminder Reports, HR Letters.
- **Menus.** Employee: Maintenance, Allowance, Deduction, Overtime, Leave (Leave, Leave Table, B/F, Leave Update,
  records), Salary Increment, Loan, Piecework Pay, Historical Data, Miscellaneous (Nationality, Race, Relationship,
  Religion, Branch, Department, Category, Holiday). Transaction: Payroll, B/F Payroll, Print Pay Slip, Print Payment
  Advice, APS Generator. Reports: EPF, SOCSO, Income Tax, HRDF, Other Government, Personnel, Management, 12 Months,
  Year-To-Date (+ Statistic), Allowance, Deduction, Account Department, Reminder, Human Resource Letters. Setting: Work
  Table, Payment Table, Bank, APS Format Setting, Statutory Setting. System: General Setup, Upgrade / Backup / Restore
  Database, Change Password, Administrative Tools.
- **Add New Payroll:** types 1st Half, 2nd Half, Month End Pay, Bonus, Commission; From/To Date; a Public Holiday
  count; tick box "I will add the employee to the payroll later" (unticked = every employee is put in the new month).
- **Organize** only re-orders payroll sequences. **Quick Update** (General / Allowance / Deduction): sets Working Days,
  Public Holiday, Days Worked, a leave, allowances or deductions for many employees at once, filtered by employee
  range, Branch, Department, Category; also "Update Basic Rate from Employee file".
- **Work Table #1:** 26 work days per month, 8 daily work hours (why a new payroll row starts at 26 / 26).
- **Overtime tables** (Round Method + Smallest Unit per table; each line has EPF/SOCSO/Taxable/HRDF ticks):
  Monthly pay: hour = ((BASIC_RATE/26)/8) x 1, 1.5, 2, 3; Rest Day = (BASIC_RATE/26) x 2 per day; Holiday Day =
  (BASIC_RATE/26) x 3 per day. Daily pay: hour = (BASIC_RATE_MY/8) x 1, 1.5, 2, 3; Rest Day = BASIC_RATE_MY x 2;
  Holiday Day = BASIC_RATE_MY x 3. There is also a table for Hourly pay.
- **An employee's record chooses its tables** (Accounts & Setting: Work Table, Leave Table, Overtimes Table) and its
  Pay Basis / Pay Period (Employment tab). Seen: one test employee with Pay Basis Daily while its Overtimes Table was
  still "for Monthly Pay" (looked at earlier today; may have been changed since).
- **Holiday** list is empty, with a Generate button. **General Setup > Transaction:** lateness and no-pay-hour deduction
  ratios (1.00), rounding of basic and net pay, a few tick boxes. **Other:** payslip e-mail subject / content.
- Million's "Payroll Information" report (already imported for the employee list) also carries Branch, Pay Basis and
  Basic Rate per employee.

## Session 12b - 2026-10-09 - Basic Rate with Monthly / Daily in the Results window
366 tests pass. **Package rebuilt and restarted. Not committed (branch `pdf-text`, after PR #2's first commit).**
- The user's correction: "daily rate" meant that the **Results window lets you choose Monthly or Daily** beside the
  Basic Rate, as in Million's employee file. Session 12's separate "daily rate" field is replaced by two fields per
  employee: `pay_basis` ("monthly" default / "daily") and `basic_rate`.
- Results window: the Basic Rate box can be typed in, with a Monthly / Daily list beside it; a line under it shows the
  basic pay (Daily: rate x Days Worked; Monthly: the rate itself, absence and unpaid leave not taken off).
- Section 4 is now "Basic pay (monthly or daily rate)": the same two fields per employee, counts, basic pay, total.
  CSV: `GET /api/payroll/{month}/basic-pay` -> `Basic pay <month> [company].csv` (`payroll.build_basic_pay_csv`).
- Neither field goes into the Million file (it has no column for them); Million keeps its own Pay Basis and rate.
- Checked in the browser on the real plan: typed a test rate as Daily, then Monthly, both lines right, then put the
  employee back to Monthly with no rate.

## Session 12 — 2026-10-09 — Daily-rated pay table; Inbox folder (no clicks) and Tables folder
365 tests pass; Malay checks pass (125 server messages). **Package rebuilt and restarted. Not committed (branch
`pdf-text`, with sessions 10 and 11).**
- **HR's request: employees paid by a daily basic rate.** Seen in Million (read-only): Employee > Employment tab has
  Pay Basis (Monthly / Daily…), Basic Rate, Pay Period; one test employee is already set to Daily + Fortnightly, rate 0.
  Not tested: whether Million multiplies the daily rate by the imported Days Worked.
- **Section "4. Daily-rated pay"** on the Payroll screen: one row per employee with the counts from the time cards
  (Days Worked, public holiday not worked, rest day / public holiday worked, OT 1.5 and 2.0 hours), a **Daily rate**
  box, and **Basic pay = rate x Days Worked** with a total. `employee.daily_rate` in the plan (remembered for next
  month with the Employee No.), `daily_rate` / `daily_basic_pay` on each result, `payroll.build_daily_csv`,
  `GET /api/payroll/{month}/daily` -> `Daily pay <month> [company].csv` (all counts incl. OT 1.0 / 3.0 and Notes).
  **Only basic pay is turned into money.** Overtime, public holidays and rest days stay counts: the rules (PH paid
  when not worked? rest day 1x / 1.5x / 2x? OT from rate / normal hours?) were asked of HR and are not answered.
  The Million file is unchanged by this.
- **Inbox folder (`inbox.py`, started in `start.py`, every 5 s):** a file saved into
  `Documents\Table Reader\Inbox\<company>\` is taken in like a dropped file, its company = the folder's name, then
  moved to `Inbox\_Read\…` (never deleted; unusable files go to `Inbox\_Not read\…`). Files still being copied (changed
  in the last 5 s), temporary files and other kinds are left alone. **It uses the Claude plan as soon as a file lands.**
- **Tables folder:** every finished document's table (reading + corrections) is kept as
  `Documents\Table Reader\Tables\<company>\<document id>.csv`, written again after a correction or a company change.
  First run on this PC wrote 62 tables in 30 company folders.
- Home page: one line explaining it, buttons "Open the Inbox folder" / "Open the Tables folder"
  (`/api/folders`, `/api/folders/{name}/open`).
- **Not tried with a real file through Claude** (it would spend plan tokens; the tests use a stand-in reader). The
  daily rate box was not typed into on the real plan (unit and API tests cover it).

## Session 11 — 2026-10-09 — "Automate more": one Million file per month, Employee No. suggestions
356 tests pass; Malay checks pass (123 server messages). **Package rebuilt and restarted. Not committed (branch
`pdf-text`, together with session 10).** Supervisor's aim: fewer clicks for staff; about 40 companies, 1-20 workers each.
- **Month run** (`payroll.month_run`, `POST /api/payroll/{month}/run`, button "Make the month's Million file (all
  companies)"): ONE file `Payroll <month> (Million).xls` for every company, so the office imports once instead of 40
  times. Everyone who would pass a company's file without a question goes in; everyone else is held back and listed by
  company with the reason (Employee No. empty / not in Million / another name in Million / used twice / INCOMPLETE /
  a figure with no column). Nobody is put in "anyway" there: that stays the per-company Download button.
- **Employee No. suggestions** (`payroll.suggest_employee_nos`, `suggest` on each result): for an employee with no
  number, when exactly one name in Million's imported list fits (one name has all the words of the other) and nobody
  in the plan has that number: a button "Use MJ(1) (… in Million)" beside the box; with 2 or more, also "Use all n …"
  (asks first, listing them). Never filled in by itself.
- **Real September plan in the packaged app:** 83 employees, 26 companies. Month run: file with 7 employees, 76 held (68
  have no Employee No. yet; others: not in Million, placeholder names in Million, INCOMPLETE). Only 1 suggestion,
  because this laptop's Million has 15 employees. At the office, where Million already holds everyone, the
  suggestions should fill most numbers. Page checked in the browser: result panel and suggestion button are drawn.
- **Item 2 (check the import automatically) is NOT built: Million cannot supply the figures.** Looked at in Million:
  - a month that is not processed prints nothing ("No record to print!") in Management Reports;
  - after processing, the reports show money (Basic Pay, Overtime RM, …), not the days and hours that were imported;
    Working Days / Days Worked are in none of them; the Overtime Report prints nothing while the Basic Rate is 0;
  - Excel output of these reports opens an unsaved workbook in Excel (no file); PDF output writes
    `C:\million\Payroll\mycompany\PDF\Management Reports.pdf` (a text PDF, one click).
  The check that remains is opening an employee in Million (guide, step E). The month run and the list checks remove
  the known causes of a silent skip before the file is made.
- Guides (EN + BM): the month run and the suggestion button.

## Session 10 — 2026-10-09 — Text-only PDF pages read without Claude (branch `pdf-text`)
352 tests pass; Malay checks pass. **Package rebuilt and restarted. Not committed (branch `pdf-text`, from `main`).**
- **Why not a plain "PDF text -> table" reader:** the PDF gives words and positions, not columns, and the payroll needs
  Claude's names for the columns and fields (e.g. "Shift Details / Actual", "Emp Code"). Claude itself names them
  differently from page to page. So `pdftext.py` **learns the layout from one page Claude reads** and fills later pages
  of the same PDF from their own text:
  - Claude reads the first text page as usual. Its whole reading must be found in the page's own characters, row by
    row (rows are matched character by character: two columns printed 0.7 pt apart come out of the PDF as one word).
    That gives each column's extent, the shapes seen in each column ("9.9", "A-A"), the lines above/below the table
    and where each field's value sits. Applying the layout to the same page must give Claude's reading back.
  - A later page is taken from its text only if every character sits in one known column, every always-filled column
    is filled, every value has a shape seen in its column, and the lines around the table have the same printed words.
    Anything else: Claude reads that page, and its reading becomes one more layout for the document.
  - Never for scans, photos, turned pages or scans with a hidden text layer (`is_text_page`). Pages read this way carry
    `source: "pdf-text"` and the note "Read from the PDF's own text (no Claude)…"; cells are certain (not yellow).
  - Wired into `jobs._read_pages` (also after Continue: pages already read teach the layout).
- **Measured on the read September PDFs (27 text pages in 7 files), replaying Claude's stored readings, no tokens:**
  **16 pages need no Claude** (the 17-page clock report: Claude 3, PDF 14; a 4-page report: 2 and 2). On those 16
  pages all **7,508 cells equal Claude's reading**; the only differences are 3 fields Claude had doubted (the text is
  clear) and Claude's own changing names for columns/fields between pages (the text reader keeps one set of names).
  Payroll days are identical on all 27 pages. Single-page PDFs save nothing; 4 files give no layout because Claude's
  reading is not word-for-word what is printed (a field reworded, a printed remark left out, ticks drawn as shapes,
  two columns Claude ordered differently).
- **Not done / ideas:** layouts are per document, in memory only. Keeping them between documents (next month's report
  from the same clock system would then need no Claude at all) is the bigger saving, not built. Not tried with a real
  read through Claude in the app (the replay used stored readings). The `download` branch still has the older zip.

## Session 9b — 2026-10-09 — Employee list imported from Million (name check, Employee Nos. offered)
339 tests pass; Malay checks pass (111 server messages, 0 missing). **Package rebuilt and restarted (xlrd is inside
now). Not committed.**
- **Million can export its employee list** (looked at through desktop control, read-only): Employee > Print >
  "Employment Listing" > Print > Excel > File > OK. No save dialog: it writes `rptempepmlist.xls` into Million's company
  folder (`C:\million\Payroll\mycompany` here), replacing the previous one. Printed-report layout: heading row
  ("Emp no.", "Name", Gender, D.O.B., …, Basic Rate) again on every page, one employee every four rows, last line
  "Total Employees : n".
- **"Import employee list from Million"** (Payroll screen, section 2): `payroll.parse_million_employees` (xlrd) keeps
  **only Employee No. and name** in `payroll\million-employees.json`; refused when it is not that report or when the
  count differs from the report's own total. `POST /api/million/employees`; the payroll view carries `million`.
- **Used for:** (1) every Employee No. box offers Million's list (datalist, name shown beside the number; nothing is
  filled in by itself); (2) before the Million file: unknown numbers are checked against this list (employees.txt is
  only used when no list was imported); (3) **name check** `MILLION_NAME` / `allow_names`: asked when the name is
  someone else's in Million. Same person = one name has all the words of the other, case ignored; an empty name is
  not compared. Order of questions: unknown number, name, INCOMPLETE.
- Real export on this laptop: 9 of 9 employees read (2 more than at the tests; the user added them). In the packaged
  app: the two tested companies download with no question, a company whose number is not in Million is asked about.
- **Not done:** the button's file chooser was not clicked in a browser (the upload was sent to the same endpoint
  directly; the page shows the list and the 9 choices). Allowance/deduction lists and the File Format Setting are not
  imported. `learn-million\million-import-tools\employees.txt` (office checker) still lists 7 codes.
- PR #1 title and description brought up to date (session 9 work); guide: new step B0 and the name question.
- **User's first try failed** ("Total Employees : 14, but 17 could be read"): they had exported the first report in
  Million's list, **Payroll Information** (`rptemppsnlist.xls`), whose title, company name and total line sit in the
  Emp No. column. Fix: a row is an employee only when it also has something under another heading. Both reports are
  read now (real files: 14 of 14 and 9 of 9); test added. Rebuilt; the 14-employee list is imported.

## Session 9 — 2026-10-09 — Import cause found, Employee No. warning, IN/OUT time cards
335 tests pass; Malay checks pass (106 server messages, 0 missing). **Package rebuilt and restarted. Not committed.**
- **"No record updated" — cause confirmed in Million itself** (looked at through desktop control, nothing changed):
  Employee tab > Employee lists 3 employees, the two codes of the import file among them. But the **September payroll
  is Processed and lists only the first employee** (it was created before the two were added), so Million had no
  payroll row to update. October (status New) also lists only that one employee, and has an **Add** button in
  Transaction > Payroll > October > Edit; the processed September window has no Add/Edit. Not tried: how to get the
  two workers into September (un-process / Organize / delete and re-create) — that changes payroll data, the user decides.
- **End-to-end test passed (user's OK, ~12:30):** Payroll screen, one company chosen -> "Download Million file (.xls)"
  (2 employees, no warnings) -> Million backed up (previous backup kept as
  `mycompany_2026-10-09_1014_before-table-reader-test.bak`) -> the two workers added to the **October** payroll
  (Transaction > Payroll > October > Edit > Add; tick = select the box cell, then Space; Alt+S, Yes) -> System >
  Administrative Tools > 9. Import > October > Import, **Files of type "Excel 97-2003 (*.xls)"** (the dialog opens on
  "Text (*.txt)") -> "Update complete". Both employees went from Working Days 26 / PH 0 / Days Worked 26 to
  **25 / 1 / 21**, exactly the file; the third employee (not in the file) kept its figures. October now holds these
  September figures as test data (not processed).
- **Second company, same test, passed (~12:38, user's OK):** its 4 Employee Nos. were not in Million -> Table Reader
  asked "4 Employee Nos. are not in the Million employee list" (answered No) -> 4 employees created in Million
  (Employee > Add: Employee No. + Name only, Million saves with just these; **everything else is Million's default,
  e.g. Gender Male, Basic Rate 0 — to be completed by the user**) -> codes added to employees.txt -> download with no
  question -> added to October -> import -> "Update complete": all 4 went 26/0/26 -> 25/1/25 = the file; the first
  company's two and the third employee unchanged. The Open dialog resets to "Text (*.txt)" on every import.
- **Guide for staff:** `GUIDE - Table Reader to Million.html` (project folder; no real names; prints well).
- `learn-million\million-import-tools\employees.txt`: now all 7 codes of this laptop's Million.- **Warning before download** (`payroll.load_million_employees`, `build_xls(known=, allow_unknown=)`, endpoint
  `allow_unknown`): an Employee No. that is not in `employees.txt` -> 400 `MILLION_UNKNOWN`, the page asks "Make the
  Million file anyway?" (asked before the INCOMPLETE question). No employees.txt (or no codes in it) = no check. Path:
  `TABLE_READER_MILLION_EMPLOYEES`, else the learn-million tools folder. Tests never read this PC's list
  (`tests/conftest.py`). The "Million file made" message now also says Million only updates employees who are already
  in that month's payroll. Checked in the packaged app: whole-month file -> MILLION_UNKNOWN (5 codes), page draws.
- **IN/OUT time cards** (`clock_pairs`, `parse_clock`, `_clock_day`; used only when the page has no hours column):
  pairs "IN|OUT", "Time In|…|Time Out", "MORNING / IN|MORNING / OUT|AFTERNOON / …", Masuk/Keluar. Clock formats seen
  on the real cards and accepted: 07:55, 7.55, 17:02:10, 5.30 PM / 5:30pm / 5,30 p.m. One pair on a day: OUT − IN −
  break (`plan.break_hours`, default 1, 0–5, box next to Normal hours; a day shorter than the break keeps its hours).
  Several pairs: added up, no break. Reported and left out, never guessed: yellow cell, only one time of a pair, not a
  clock time (e.g. "530 PM", a time with a tick after it), OUT not later than IN (night shift, or afternoon written
  without PM). "Day by day" shows the times and how the hours were worked out. `readable()` now includes these cards,
  so "Add employees from files" picks them up. Dates written year-first (2026-09-16, door systems) are read now.
- **Real cards (counts only):** 11 documents now readable; typical worked day 8.3–8.8 h after the break. Left out:
  40 days with a yellow cell, 20 "OUT not later than IN" (one card writes afternoon times without PM), 5 not a clock
  time, 6 unclear dates, 2 conflicts.
- **Still not readable:** one cell holding several stamps ("Times | Time", 4 pages), day-per-column job sheets, tables
  whose headers were read as COL1…, a leave form.
- **To confirm with the user:** (1) morning/afternoon pairs: no break taken off; (2) a half day with one IN/OUT pair
  still has the break taken off (only matters for overtime); (3) a few minutes early/late each day become overtime
  fractions (e.g. 0.17 h) — no rounding rule yet; (4) cards that print their own "Work"/"Work Hour" figure: Table
  Reader works from IN/OUT unless the user picks that column in the Hours column list.

## Session 8 — 2026-10-09 — Million import said "no record updated" (diagnosis only, no code changed)
The user imported a real September Million file for one company (2 employees) on this laptop: nothing was updated.
- **The file is built correctly** (compared by shape with `learn-million\import-test\Million import test 2026-10.xls`,
  which imported correctly today: same sheet name, same 51 headers, text in A, numbers in C–AY).
- **Likely cause: the Employee Nos. are not in Million on this laptop.** Both rows have a short 3-character code;
  `employees.txt` holds only the one code confirmed in Million. Million skips unknown codes silently. The office
  checker had already said "Fix 2 errors" (both codes not in employees.txt) before the import.
- Not confirmed directly: Million's own employee list could not be read from here (no database access, no desktop
  control in this session).
- Second possible cause, same message: this laptop's September payroll is already processed and holds one employee;
  workers who are not in that month's payroll cannot be updated. How Million adds a new employee to an existing
  month is not known yet.
- **Next (user):** in Million check Employee tab > Employee for the two workers; add them or correct the codes in
  Table Reader; check they are listed in the month's payroll; add the codes to `employees.txt`; checker READY; import.
- **Offered, not built:** Table Reader warns before download when an Employee No. is not in `employees.txt`.
- IN/OUT time cards still not started.

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
