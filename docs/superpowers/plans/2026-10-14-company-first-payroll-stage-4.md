# Company-first payroll, stage 4: New in Million, the month-file summary, the employee view, no old page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the company-first payroll. Each company gets a "New in Million" list. The month's Million file is
shown as a summary before it is made. Everything only the old payroll page could do moves to the new screens, and the
old page is removed. Added on 2026-10-14 at the user's request: **Part C**, so that what Claude reads correctly also
reaches Million's fields (the conversion from a card's columns to days and Million figures).

**Architecture:** Stage 4 is split in three parts. Each part is merged and can be shipped by itself, and there is a stop
for the user's OK after each. They run in this order (the user chose conversion before Part B):
- **Part A** (`million-summary`, Tasks 1-3) changes only the overview and the company screen. **Done, merged into
  `pdf-text` and the app rebuilt on 2026-10-14.**
- **Part C** (`conversion`, Tasks 11-17) fixes how a card's columns become days and Million figures. The hours column
  is never a money or minutes column. Written formats the user has ruled on are read. **Layout maps**: for a card
  layout Table Reader does not know, Claude suggests what each column means, the user confirms it once, and the
  calculation uses it. The arithmetic stays in code.
- **Part B** (`employee-view`, Tasks 4-10) adds the employee view, the pay preview tab and "Add employee", then removes
  the old page.

From now on, every change to a plan goes to the server as one small action, under the existing lock and through
`validate_plan`. No page keeps its own copy of the whole plan any more. That copy is why a stale old-page tab could save
over newer work (review findings of stages 1 and 3).

**Tech Stack:** Python 3.14, FastAPI, pytest; plain HTML/JS/CSS, no build step; PowerShell 5.1 on Windows.

**Spec:** `docs/superpowers/specs/2026-10-12-company-first-payroll-design.md`: sections 3.3 (employee detail view, pay
preview, Add employee), 3.4 (what is removed or moved), 7 (New in Million), 8 (the month file), 9.3 stage 4 and 11.
The plans for stages 1-3 are in the same folder. Part C has no spec section. Its requirements are the user's
decisions of 2026-10-14 (below) and the findings on the real September data (PROGRESS.md session 21b).

**Decided here (not in the spec):**
- **Two parts, two merges** (see Architecture). The user approves the merge of Part A before Part B starts.
- **The employee view saves one change at a time:** `PUT /api/payroll/{month}/employee/{id}` with `{"changes": {key:
  value}}`. Only the keys sent are changed. A view opened before another tab changed something else on the employee
  does not undo that change.
- The employee view opens at `#/payroll/<month>/e/<employee id>`, in a new tab as "Open employee" does today. "Back to
  the company" goes to the employee's company screen.
- **"Move to another employee"** = `POST /place` with `"move": true`: the card is taken off its employee first. The
  choices are the other employees of the same company plus "A new employee". **"Take off"** = `POST /take-off`. A card
  taken off becomes a "whose card is this?" item again.
- The allowance, deduction, benefit and leave lines are the same for every employee. They are saved with `PUT
  /api/payroll/{month}/lists`, the whole `lists` at once. `validate_plan` already drops the figures of a removed line.
- **Summary before the file:** `GET /api/payroll/{month}/run` works the file out without writing it. `POST` (unchanged)
  makes it and works everything out again. It never relies on the summary.
- **Copy all** in "New in Million" copies one line per employee, `Employee No.<TAB>Name`, so it pastes into Excel as
  two columns.
- **These endpoints are removed with the old page:** `GET` and `PUT /api/payroll/{month}` (the whole plan),
  `POST /api/payroll/{month}/auto`, and `GET /api/payroll/{month}/xls` (the per-company file with its "anyway"
  questions). The tests that use them are ported or deleted in Task 9. `build_xls` and its `allow_*` options stay:
  `month_run` uses them and `tests/test_payroll.py` tests them. These stay: `/csv` and `/basic-pay` (with `company`),
  and `/run`.
- An old address that is bookmarked or still open goes to a real screen: `#/payroll/<m>/old` opens the month overview,
  and `#/payroll/<m>/old/e/<id>` opens the employee view.

**Part C: decided by the user (2026-10-14):**
- Order: conversion first, then Part B.
- **OUT earlier than IN, with no am/pm**, on an IN/OUT card (IN 8, OUT 5.00): OUT is read as afternoon (+12 h). This
  holds only when IN is before 12:00 and OUT is 11:59 or earlier. The day says how it was read.
- **SA / SU** in a month-grid cell: SA is Saturday and SU is Sunday. A cell holding only the day's name, on that same
  weekday, means nothing was worked that day (read as "off"). The user said Sunday is every worker's rest day and hours
  worked on it are overtime. The calendar already gives that: Sundays start as rest days, and hours on a rest day go to
  "Work on Rest Day". Anywhere else, SA and SU stay unclear.
- **Layouts Table Reader does not know:** Claude suggests what each column means, the user confirms it once per layout,
  and it is remembered (the old "Phase C"). Claude never calculates.

**Part C: decided here:**
- A **layout** is a page's column headings, lower case with spaces collapsed, joined by " | " (its signature). A
  confirmed **layout map** applies to every company and month that has the same headings. It is kept in
  `Documents\Table Reader\payroll\layouts.json`: `{signature: {"columns": {heading: {"role", "unit"}}, "confirmed":
  "yyyy-mm-dd"}}`.
- **Roles** a column can have:
  - `date`;
  - `hours` (the day's hours);
  - `in` and `out`, and `stamps` (several clock times in one cell);
  - the Million figures `lateness`, `early_departure`, `ot_1`, `ot_1_5`, `ot_2` and `ot_3`;
  - `ignore`.

  Units: `hours` (8.5 or 8:30), `minutes` (divided by 60) or `none`. A mapped figure column works like the clock
  report's printed figures: added up as written, and on those days the normal-hours overtime rule is not applied.
- **`stamps`**: the clock times in the cell are taken in order as IN, OUT, IN, OUT. An odd number of times is reported,
  never completed.
- **Claude sees text only:** the headings, plus up to 5 rows where each value is reduced to its shape (digits as 9,
  letters as A, except words of 4 letters or fewer, such as PH or OFF). It runs once per layout, through the user's
  own Claude Code with the same model as the reading. Its answer is a suggestion and is used only after the user has
  confirmed it.
- **When the user is asked:** a "Needs you" item, "A card layout Table Reader does not know: check what its columns
  mean", appears once per unconfirmed layout. It appears only when a column the calculation does not read holds
  numbers or clock times in at least 3 rows, and that column is not a row number ("No.", "Bil", "#"). One click, **It
  is right as it is**, confirms the layout with every unread column set to `ignore`.
- **Built-in readings keep priority**, except for a confirmed map: a month grid, a Total / Jumlah column, IN/OUT pairs
  and the Shift Details report are read as today unless the user has confirmed a map for that layout.

## Global Constraints

- **The calculation does not change** in Parts A and B. No figure, problem kind or problem text changes. Task 3 and
  Task 10 prove this on the real September data (all 84 employees identical). **Part C does change figures on
  purpose.** Task 17 lists, by count, every employee whose figures change and why, and every other employee must stay
  identical.
- **Never guess.** Nothing is filled in by itself that is not filled in today. Claude's reading (`result.json`) is
  never written.
- **Personal data.** The repo is public. Tests, comments, commit messages and chat use made-up names only (MAJU JAYA,
  BINA, ALI, SITI, ZUL). Real-data checks print counts only.
- **Every new text shown to the user** goes through `t()` / `tn()` / `tm()` and has a Malay entry in `static/i18n.js`.
  Every new server sentence has its Malay entry too (`MS`, or `MS_PATTERNS` when it holds names or numbers). The
  Edit Payroll window's own labels stay English in both languages (CLAUDE.md, NEXT-SESSION §6).
- **Before every commit:**
  - `.venv\Scripts\python -m pytest -q` passes.
  - `.venv\Scripts\python tools\check_i18n.py` shows `missing Malay: 0`, and its file lists include every new script.
  - `.venv\Scripts\python tools\check_patterns.py` shows `0 not translated`.
  - The real-name scan of the diff is clean.
- **Commits are local**, on `million-summary` (Part A), `conversion` (Part C) and `employee-view` (Part B), each made
  from `pdf-text`. Merging, pushing, rebuilding the app and updating the `download` branch all need the user's OK.
- **Click-throughs** run on made-up data, in headless Edge or in the app's browser pane: a scratchpad server with
  `TABLE_READER_HOME`, scripted clicks.
- Follow the surrounding style: 120-column lines, docstrings that say what and why, and comment density as in the
  code around.

## Review Focus

1. **Two tabs.** The employee view is open while the company screen's "Use {no}" sets the Employee No. If the view
   then saves the name, the number stays. Pinned in Task 5 (`test_saving_one_field_keeps_what_another_tab_changed`).
2. **An employee removed in another tab.** Saving, moving a card or opening the view says "This employee is no longer
   in the payroll of this month…", never "Something went wrong". Pinned in Task 5.
3. **The summary goes stale.** Something is fixed between the summary and "Make the file", and the file holds the
   fixed state. Pinned in Task 1 (`test_the_file_is_worked_out_again_when_it_is_made`).
4. **Moving an employee's only card.** The card is on exactly one employee afterwards. The old employee stays, with a
   "no time card yet" item. Nothing is refused as "on two employees". Pinned in Task 5.
5. **An old-page address.** A tab or bookmark at `#/payroll/<m>/old…` opens the overview or the employee view, never a
   blank screen. Pinned in Task 8 (route and click-through).

**Part C:**

6. **The afternoon rule touches nothing else.** An OUT with an explicit "am", an IN after noon (night shift), an OUT
   of 12 or later, and an OUT equal to IN all stay unclear, as today. Pinned in Task 12.
7. **A map is confirmed for one layout only.** A card whose headings differ by one column is not read with another
   layout's map; it gets its own item. Pinned in Task 14 (`test_a_map_is_used_only_for_its_own_headings`).
8. **Claude's answer is never trusted as it comes.** A heading that is not on the page, a role or unit not on the list,
   a second `date`, or a bad answer leaves nothing saved: the panel shows the plain headings with nothing chosen.
   Pinned in Task 15.
9. **A minutes column with an h:mm value** ("1:30" under a `minutes` role) is read as 90 minutes, not as 1.30
   minutes. A value that is not a number of minutes is reported. Pinned in Task 14.
10. **Fixing the hours column changes only the layouts it should.** On the real September data, exactly the employees
    on the "E/Out(Min)" report and on the "TOTAL (RM)" list change; everyone else stays identical. Pinned in Task 17.

---

## File Structure

| File | Responsibility |
|---|---|
| `payroll.py` (modify) | Pure plan actions: `EMPLOYEE_KEYS`, `change_employee`, `take_off_card`, `remove_employee`, `add_employee` (Task 4). |
| `app.py` (modify) | `month_file` + `GET /run` (Task 1); employee, take-off, lists and pay endpoints (Task 5); removing the old endpoints (Task 9). |
| `static/paycommon.js` (new, Task 6) | Helpers that `payroll.js` holds today and the new screens share (month names, days, `fmt`, `runReason`, `showMonthRun`, ...). |
| `static/employee.js` (new, Task 6) | The employee view: the Edit Payroll window, the employee's cards, the hours column, Remove. |
| `static/paytable.js` (new, Task 7) | The company screen's Pay preview tab. |
| `static/companies.js` (modify) | Summary before the file, "New in Million", CSV buttons (Task 2); Open employee, tabs, Add employee (Tasks 6-7). |
| `static/payroll.js` (delete, Task 8) | The old page. |
| `static/index.html`, `static/app.js`, `static/app.css`, `static/i18n.js`, `tools/check_i18n.py` (modify) | Screens, routes, styles, Malay, script lists. |
| `tests/test_payroll.py`, `tests/test_app.py` (modify) | Tests. |
| `GUIDE - Table Reader to Million.html`, `PANDUAN - Table Reader ke Million.html`, `PROGRESS.md`, `NEXT-SESSION.md` (modify, Tasks 3 and 10) | Guides and notes. |
| `payroll.py` (modify, Part C) | `pick_columns` never takes money / minutes columns (Task 11); the afternoon rule and "530 pm" (Task 12); SA / SU (Task 13); layout signatures, roles and maps in `read_days`, `PayrollStore.load_layouts` / `save_layouts` (Task 14). |
| `layouts.py` (new, Task 15) | What Claude is shown about a layout (shapes only), the prompt and schema, checking its answer. Pure, apart from the one CLI call through `ocr`. |
| `ocr.py` (modify, Task 15) | `ask_text(prompt, schema, timeout)`: a text-only CLI call (no image, no tools), same environment, errors and model as the reading. |
| `app.py`, `companies.py`, `static/companies.js`, `static/layout.js` (new), `static/index.html`, `static/i18n.js`, `tools/check_i18n.py` (modify, Task 16) | The "card layout" item, its endpoints, and the panel to confirm a layout map. |

---

## Part A: branch `million-summary` (from `pdf-text`): done, merged and rebuilt 2026-10-14

### Task 1: The month file worked out without being made

**Files:** Modify `app.py` (`payroll_month_run`). Test: `tests/test_app.py`.

**Interfaces:**
- Produces: `month_file(month: str, make: bool) -> dict` inside `create_app`, shared by both routes. It returns what
  `POST /run` returns today, plus:
  - `"made": bool`
  - each company entry gains `"ready_people": [{"emp_no": str, "name": str}]` (the employees going in, in plan order).
  - With `make=False`, nothing is written and `"file"` is `None`.
- Produces: `GET /api/payroll/{month}/run` = `month_file(month, False)`. `POST` = `month_file(month, True)`.

- [x] **Step 1: Write the failing tests** (through `company_client`, `import_million`, `month_card`):
  - `test_the_summary_lists_who_goes_in_and_writes_no_file`:
    - Set up MAJU JAYA (ALI known to Million) and BINA (SITI known, ZUL not).
    - `GET /run`: `made is False`, `file is None`, `ready == 2`, `held == 1`.
    - BINA's entry: `ready_people == [{"emp_no": <SITI's>, "name": "SITI"}]`, and its held reason contains
      `"is not in the Million employee list"` (spec 7: only ZUL is held back; SITI goes in).
    - No `.xls` file is in the payroll folder.
  - `test_the_file_is_worked_out_again_when_it_is_made`: `GET /run` holds ZUL back. Then `import_million` again with
    ZUL added. `POST /run` gives `made is True` and `ready == 3`, and the `.xls` exists.
- [x] **Step 2: Run them and see them fail.** Run `.venv\Scripts\python -m pytest tests/test_app.py -q -k "summary_lists or worked_out_again"`.
  Expected: FAIL (405 on GET, then a KeyError on `made`).
- [x] **Step 3: Write `month_file`.** Move the body of `payroll_month_run` into it, collect `ready_people` beside the
  `ready` count, and write the file only when `make` is true.
- [x] **Step 4: Check the whole suite.** `.venv\Scripts\python -m pytest -q` passes (the existing
  `test_the_month_run_makes_one_file_and_lists_who_is_held_back` still passes).
- [x] **Step 5: Commit** "Payroll: the month's Million file can be worked out without being made".

### Task 2: Summary, New in Million and the payroll CSV on screen

**Files:**
- Modify `static/index.html`:
  - On the overview: `mo-csv` ("Download payroll CSV").
  - On the company screen: `co-csv`, `co-million-open` and `<section id="co-million" class="card" hidden>`.
- Modify `static/companies.js`, `static/app.css`, `static/i18n.js`.
- Test: `tests/test_app.py` (`test_the_page_has_the_company_first_screens` also expects `id="co-million"` and `id="mo-csv"`).

What each control does:
- **`mo-run`** now calls `GET /run` and draws the summary in `mo-run-result`:
  - head: "The month's Million file would hold {n} employee(s) from {c} companies."
  - one line per company: its name, then the names going in;
  - the people held back, grouped by company, each with its reasons through `runReason`;
  - "The Employee Nos. are not being checked against Million…" when the list was never imported;
  - two buttons: **Make the file** (primary; disabled when `ready == 0`), which calls `POST /run` and shows the result
    with `showMonthRun`, and **Not now**, which hides the summary.
- **`co-million-open`**:
  - its label is "New in Million: {n} employee(s)" (`tn`);
  - it is hidden when `coView.million_new` is empty, and replaces the legend line about Million drawn today;
  - it opens the `co-million` panel. The panel has:
    - the title "{company}: {n} employee(s) Million does not have yet";
    - a table of Employee No. and Name with a **Copy** button on each row (copies the number);
    - **Copy all**: `navigator.clipboard.writeText`, lines `NO\tNAME`;
    - the text from spec 7: "Create them in Million with exactly these numbers, then export Million's employee list
      and import it on the month page.", followed by the old page's export how-to ("In Million Payroll: Employee >
      Print > Employment Listing > …").
  - If the clipboard refuses, the error banner says "Copying did not work. Select the numbers and copy them yourself."
- **`mo-csv` and `co-csv`** set `location.href` to `/api/payroll/{month}/csv`, with `?company=` on the company screen.

Steps:
- [x] **Step 1: Extend the page test and see it fail.**
- [x] **Step 2: Build the screens.**
- [x] **Step 3: Check.** The suite, `check_i18n` and `check_patterns` pass.
- [x] **Step 4: Click it through** in headless Edge on made-up data (scratchpad server with `TABLE_READER_HOME`,
  script injected, as in stages 2-3). Check that:
  - the summary shows a held ZUL and the ready SITI, and Not now hides it;
  - Make the file reports the file;
  - "New in Million: 1 employee" opens the list and Copy all puts `"<no>\tZUL"` on the clipboard (read it back in the
    script);
  - both CSV buttons download.
- [x] **Step 5: Commit** "Payroll: summary before the month's Million file; New in Million list; payroll CSV on the
  new screens".

### Task 3: Part A proof, notes, stop

- [x] **Step 1: Check the real September data.** On a copy, in memory, counts only: `GET /run`'s ready and held
  counts equal `POST /run`'s, and every employee's figures are identical to `pdf-text`'s.
- [x] **Step 2: Write the notes.** PROGRESS.md gets session 21 (Part A) and NEXT-SESSION.md section 0 is updated.
  Commit "Notes: stage 4 part A".
- [x] **Step 3: Review and stop.** One fresh reviewer reviews the branch, and the important findings are fixed.
  **Stop:** ask the user before merging into `pdf-text` and before rebuilding.

---

## Part C: branch `conversion` (from `pdf-text` after Part A is merged), done before Part B

Why (real September data, a copy, counts only; PROGRESS.md session 21b): with every Employee No. known to Million, 37
of 84 employees would go into the file and 42 would be held back as INCOMPLETE. These conversion failures come from
cards Claude read correctly:
- two layouts where the wrong column is taken as the daily hours:
  - a second clock-report layout (`… | WDays | WHrs | E/Ot | OT | LIn(Min) | … | E/Out(Min) | …`) where the early-out
    minutes are taken instead of WHrs;
  - a salary-deduction list where `TOTAL (RM)` is taken as hours.
- formats refused although they are readable: OUT earlier than IN with no am/pm (20 days), SA / SU on weekend grid
  cells (16), "530 pm" (1);
- layouts no rule fits: the clock report's OT and minute columns never reach Million, and a door-system export has
  several stamps in one cell (4 pages).

### Task 11: The hours column is never a money or minutes column

**Files:** Modify `payroll.py` (`pick_columns`). Test: `tests/test_payroll.py`.

**Interfaces (Produces):** `pick_columns(labels, hours_column)` as today, with these rules:
- A label whose last part (after the last " / ") holds a money mark (`rm`, `(rm)`, `amount`, `$`) or a minutes mark
  (`min`, `(min)`, `mins`, `minutes`) is never an automatic hours column. A column the user chose by hand still wins.
- Among the rest, the first preference is a label whose last part is exactly an hours word: `hours`, `hrs`, `whrs`,
  `total`, `jumlah`, `jam`, `total hours`, `jumlah jam`. After that comes today's rule (the last matching label).

- [ ] **Step 1: Write the failing tests.**
  - `test_minutes_columns_are_never_the_daily_hours`: the second report's labels (`"DAYS/HOURS/MINUTES WORK / WHrs"`,
    `"… / OT"`, `"… / LIn(Min)"`, `"… / E/Out(Min)"`, plus `"DATE"`) pick `"DAYS/HOURS/MINUTES WORK / WHrs"`.
  - `test_a_money_column_is_never_the_daily_hours`: `("NO.", "NAME", "DAY UNPAID", "TOTAL (RM)")` gives `None`, so the
    calculation's "no column with the daily hours" problem appears.
  - `test_the_users_hours_column_still_wins`: `hours_column="TOTAL (RM)"` returns it.
  - `test_total_normal_is_still_the_hours`: `("Date", "TOTAL (NORMAL)")` picks `"TOTAL (NORMAL)"` (a September layout;
    "NORMAL" is not "RM").
- [ ] **Step 2: Run them and see them fail.** `.venv\Scripts\python -m pytest tests/test_payroll.py -q -k "never_the_daily or users_hours or total_normal"`.
  Expected: the first two FAIL.
- [ ] **Step 3: Change `pick_columns`.** Mark matching works on whole words of the last part, so "NORMAL" never
  matches "rm".
- [ ] **Step 4: Check that the whole suite passes.**
- [ ] **Step 5: Commit** "Payroll: the daily hours are never taken from a money or minutes column".

### Task 12: An afternoon OUT written without pm; "530 pm"

**Files:** Modify `payroll.py` (`_clock_day`, `parse_clock` / `_STAMP`). Test: `tests/test_payroll.py`.

**Interfaces (Produces):** In `_clock_day`, when `end <= start`, OUT has no am/pm, IN is before 12:00 (`start < 720`)
and OUT is before 12:00 (`end < 720`), OUT is read as `end + 720`, and the day's `clock` gains `"afternoon"`: the
OUTs read so (`["5.00"]`). The page's Day by day shows "OUT {out} read as afternoon" from it (with a Malay entry).
`parse_clock` also reads 3-4 digits followed by am/pm ("530 pm" -> 17:30, "1130 am" -> 11:30). Without am/pm, digits
alone stay not a clock time.

- [ ] **Step 1: Write the failing tests.**
  - `test_an_out_earlier_than_in_without_pm_is_afternoon`: IN "8", OUT "5.00", break 1 gives 8.0 hours, status
    "ok", `clock["afternoon"] == ["5.00"]`.
  - `test_the_afternoon_rule_leaves_other_cases_unclear`: these all stay "unclear" with today's sentence:
    - OUT "5.00 am" with IN "8";
    - IN "9:00 pm", OUT "5.00" (a night shift);
    - IN "13:00", OUT "12.30";
    - IN "8", OUT "8".
  - `test_digits_with_pm_are_a_clock_time`: `parse_clock("530 pm") == 1050` and `parse_clock("1130 am") == 690`.
    `parse_clock("530") is None`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write the rule.** It covers both a single pair and the "one IN, one later OUT" span.
- [ ] **Step 4: Check.** The suite passes. Add the day note to the old page's Day by day (`clockText`, `payroll.js`)
  with its Malay entry; Part B's employee view ports it. `check_i18n` passes.
- [ ] **Step 5: Commit** "Payroll: an OUT written without pm and earlier than IN is read as afternoon (user's rule)".

### Task 13: SA and SU in month grids

**Files:** Modify `payroll.py` (`_read_grid`). Test: `tests/test_payroll.py`.

**Interfaces (Produces):** In `_read_grid`, a cell whose text is `SA` / `SAT` on a Saturday of the month, or `SU` /
`SUN` on a Sunday, is mark `"off"` (hours 0, `code` = the text). On any other day it stays "not a mark Table Reader
knows". This is not added to `GRID_MARKS`, because it depends on the weekday.

- [ ] **Step 1: Write the failing tests** (September 2026: the 5th is a Saturday, the 6th a Sunday, the 7th a
  Monday).
  - `test_sa_on_a_saturday_and_su_on_a_sunday_are_not_worked`: a grid row with day 5 = "SA", day 6 = "SU" and the
    other days ticked gives both days `mark == "off"`, no unclear problem, and they are not counted as worked.
  - `test_sa_on_a_weekday_stays_unclear`: day 7 = "SA" gives the "not a mark Table Reader knows" problem.
  - `test_hours_on_a_sunday_still_count_as_rest_day_work`: day 6 = "8" gives the rest-day figure exactly as today.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write the rule.**
- [ ] **Step 4: Check that the whole suite passes.**
- [ ] **Step 5: Commit** "Payroll: SA / SU on their own weekday in a month grid mean not worked (user's rule)".

### Task 14: Layout maps in the calculation

**Files:** Modify `payroll.py`. Test: `tests/test_payroll.py`.

**Interfaces (Produces):**
- `LAYOUT_ROLES = ("date", "hours", "in", "out", "stamps", "lateness", "early_departure", "ot_1", "ot_1_5", "ot_2",
  "ot_3", "ignore")` and `LAYOUT_UNITS = ("hours", "minutes", "none")`.
- `layout_signature(labels: list[str]) -> str`: `" | ".join(_key(label) for label in labels)`.
- `valid_layout_map(labels: list[str], columns: dict) -> dict`: a clean `{label: {"role", "unit"}}`, or
  `OcrError("BAD_LAYOUT", "What the columns mean could not be understood. Open the card layout again.")`. Its rules:
  - every label of the page is present, and no label from another page;
  - roles and units come from the lists;
  - at most one `date`;
  - `in` and `out` columns alternate in page order;
  - a figure role has unit `hours` or `minutes`;
  - `date`, `in`, `out`, `stamps` and `ignore` have unit `none`.
- `read_days(..., layouts: dict[str, dict] | None = None)`: when the page's signature is in `layouts`, the map decides
  everything about that page, before the grid check:
  - `date` gives the date column; `hours` the hours column (`minutes` divided by 60; a minutes value written h:mm, such
    as "1:30", is 90 minutes);
  - `in` / `out` columns pair up in page order;
  - `stamps`: the clock times in the cell are pairs in order. An odd count is an "unclear" problem with `at`:
    "'…' holds an odd number of clock times, so IN and OUT cannot be paired. Correct it in the document.";
  - the figure roles are read like the clock report's `report` columns (printed figures, added up, unit converted;
    the normal-hours overtime rule is not applied on those days);
  - `ignore` is not read.
  `calculate(..., layouts=None)` and `compute_all(..., layouts=None)` pass it through.
- `PayrollStore.load_layouts() -> dict` and `save_layouts(layouts: dict) -> None` use `layouts.json` in the payroll
  folder. A missing or damaged file gives `{}`.
- `columns_read(labels: list[str], hours_column: str | None, layouts: dict | None) -> set[str]`: the columns
  `read_days` reads on a page with these headings: the map's non-`ignore` columns; or the grid's day and name columns;
  or date, hours, the IN/OUT pairs and the report columns. It shares the same helpers, so the two cannot drift. Task 16
  uses it. Test: `test_columns_read_matches_what_read_days_reads`, for a Total card, an IN/OUT card, a grid, the Shift
  Details report and a mapped page.

- [ ] **Step 1: Write the failing tests.**
  - `test_a_mapped_report_gives_hours_and_million_figures`: labels `("DATE", "WHrs", "OT", "LIn(Min)",
    "E/Out(Min)")`. The map gives `hours`, `ot_1_5` (hours), `lateness` (minutes) and `early_departure` (minutes). Rows
    for days 1-2 give:
    - hours 8 and 8;
    - `printed == {"ot_1_5": 2.0, "lateness": 0.25, "early_departure": 0.0}` on day 1 (OT "2", LIn "15", E/Out "0");
    - `ot_1_5` from the normal-hours rule not added on top.
  - `test_a_map_is_used_only_for_its_own_headings`: the same map and a page with one extra column gives today's
    reading (built-in rules), not the map's.
  - `test_stamps_in_one_cell_are_paired_in_order`: `"07:58 12:01 13:02 17:05"` gives 8.1 hours with no break (two
    pairs). `"07:58 12:01 13:02"` gives an unclear problem.
  - `test_a_minutes_figure_written_as_hmm_is_minutes`: LIn(Min) "1:30" gives lateness 1.5.
  - `test_valid_layout_map_refuses_bad_answers` (parametrized): a missing label, a label not on the page, role
    "salary", unit "days", two `date`, `hours` with unit `none`, and `out` before `in` all give code `BAD_LAYOUT`.
  - `test_layouts_are_stored_and_a_damaged_file_is_empty`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write the maps into `read_days`.** Reuse the `report` path. A mapped page sets `report`, `hours_col`,
  `date_col` and `pairs` from the map, then runs the existing row loop.
- [ ] **Step 4: Check.** The suite passes, and every existing test is unchanged (no map = today's reading).
- [ ] **Step 5: Commit** "Payroll: a confirmed layout map says what each column of a card means".

### Task 15: Claude's suggestion for a layout

**Files:** Create `layouts.py`. Modify `ocr.py`. Tests: `tests/test_layouts.py` (new), `tests/test_ocr.py`.

**Interfaces (Produces):**
- `ocr.ask_text(prompt: str, schema: dict, *, timeout: int = 120) -> dict`: runs the signed-in CLI with the prompt on
  stdin, `--output-format json --json-schema <schema>`, no image and no tools, with the reading's `MODEL` and `EFFORT`,
  the billing variables removed and the same plain-language `OcrError`s. Returns the structured answer.
- `layouts.shapes(page: dict, rows: int = 5) -> list[dict]`: up to `rows` rows `{label: shape}`. In a shape, digits
  become 9 and letters become A, except whole words of 4 letters or fewer, kept as written ("PH", "OFF"). An empty
  cell is "". Yellow cells are shaped from what Claude saw.
- `layouts.SUGGEST_SCHEMA`: `{"columns": [{"label", "role" (enum LAYOUT_ROLES), "unit" (enum LAYOUT_UNITS)}]}`.
  `layouts.suggest(page: dict, ask=ocr.ask_text) -> dict`: builds the prompt (the role list with one line each, "choose
  ignore when unsure; never guess"), asks, and returns `payroll.valid_layout_map(...)` of the answer. A bad answer
  raises `BAD_LAYOUT` (Review Focus 8).

- [ ] **Step 1: Write the failing tests.** No real CLI: `ask` is a fake that records the prompt.
  - `test_shapes_hide_names_and_numbers`: a row `{"NAME": "ALI BIN ABU", "IN": "07:58", "MARK": "PH"}` gives
    `{"NAME": "AAA AAA AAA", "IN": "99:99", "MARK": "PH"}`. Check that the made-up name does not appear anywhere in
    the prompt.
  - `test_suggest_returns_a_checked_map`, and `test_suggest_refuses_an_answer_with_an_unknown_role`.
  - `test_ask_text_runs_without_tools_or_image` (in `test_ocr.py`, fake `subprocess.run` as the existing tests do):
    the command has `--json-schema` and no `--tools Read`, and the billing variables are removed.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write `layouts.py` and `ocr.ask_text`.**
- [ ] **Step 4: Check that the whole suite passes.**
- [ ] **Step 5: Commit** "Layouts: Claude suggests what a card layout's columns mean (text only)".

### Task 16: The card layout item and its panel

**Files:**
- Modify `app.py` (load the layouts and pass them to `compute_all` everywhere the plan is worked out).
- Modify `companies.py` (the `layout` item).
- Create `static/layout.js`.
- Modify `static/companies.js`, `static/index.html` (`<main id="layout" hidden>`, script tag), `static/app.js`
  (route `#/payroll/<m>/layout/<doc>/<page>`), `static/app.css`, `static/i18n.js` and `tools/check_i18n.py`.
- Tests: `tests/test_companies.py`, `tests/test_app.py`.

**Interfaces (Produces):**
- `companies.unknown_layouts(pages_by_doc: dict[str, list[dict]], layouts: dict, used: dict[str, set[str]]) ->
  list[dict]`: one `{"kind": "layout", "signature", "doc", "page", "columns": [unread figure columns]}` per unconfirmed
  signature, under the rule in "Part C: decided here" (`used` = `payroll.columns_read` for each page). The company
  screen lists it among its items.
- `GET /api/payroll/layout?doc=&page=`: `{"labels", "shapes", "saved": map | null, "suggestion": map | null, "error":
  text | null}`. The suggestion is asked only when nothing is saved and `?ask=1` is given, so opening the panel never
  calls Claude by itself; the panel has an **Ask Claude** button.
- `PUT /api/payroll/layout`, body `{"doc", "page", "columns"}`: runs `valid_layout_map`, saves it under the page's
  signature with today's date, and returns `{"ok": true}`. `{"doc", "page", "as_is": true}` saves the layout with every
  column the calculation does not read set to `ignore` ("It is right as it is").

Behaviour of the panel:
- One row per column: heading, the shapes of its first rows, and a select of the roles (shown in plain words such as
  "Hours worked that day" and "Lateness") with a unit select.
- Claude's suggestion is preselected and marked "Claude's suggestion: check it".
- **Save** confirms the map. **Back** returns to the company screen, where the item is gone and the figures are worked
  out again.

- [ ] **Step 1: Write the failing tests.**
  - `test_an_unknown_layout_with_figures_is_an_item_once`: two cards of the same unknown layout give one item. A
    layout whose unread columns are only "No." and a signature column gives none.
  - `test_confirming_a_layout_changes_the_figures`, through `company_client`: a made-up card with the second report's
    headings. Before confirming: the item, and OT 1.5 = 0. After `PUT` with the map: no item, and OT 1.5 equals the
    sum of the OT column.
  - `test_it_is_right_as_it_is_ignores_the_rest`, and `test_a_bad_map_is_refused_and_nothing_saved`.
  - `test_opening_the_panel_does_not_ask_claude`: the fake `ask` is not called without `ask=1`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Build the server side.**
- [ ] **Step 4: Build the page.** The suite, `check_i18n` and `check_patterns` pass.
- [ ] **Step 5: Click it through** on made-up data with the second report's headings, with Claude's answer replaced
  by a fixed one in the scratchpad server. Check that:
  - the item opens the panel, and Ask Claude preselects the roles;
  - changing one role and pressing Save updates the figures on the company screen;
  - "It is right as it is" clears the item of another layout.
- [ ] **Step 6: Commit** "Payroll: a new card layout is confirmed once, with Claude's suggestion".

### Task 17: Part C proof, notes, review, stop

- [ ] **Step 1: Check the real September data** (a copy, counts only, before = `pdf-text`, after = `conversion`, no
  layout confirmed):
  - the employees whose figures changed, by cause (hours column; afternoon rule; SA/SU);
  - every other employee identical;
  - the number of unclear lines before and after;
  - the number of "card layout" items, and which layouts they are (headings shown to Claude only, never in chat).
- [ ] **Step 2: Real Claude, once, with the user's OK** (it uses their plan): ask for the second clock report's
  layout and print only whether each column's suggestion matches the expected role (WHrs hours, OT ot_1_5,
  LIn(Min) lateness minutes, E/Out(Min) early_departure minutes). Save nothing.
- [ ] **Step 3: Write the notes.** PROGRESS.md gets session 22 (Part C) and NEXT-SESSION.md section 0 is updated.
  Commit "Notes: stage 4 part C".
- [ ] **Step 4: Review and stop.** One fresh reviewer reviews the branch, and the important findings are fixed.
  **Stop:** ask the user before merging and rebuilding. Before relying on the new rules, the user also confirms the
  September layouts in the app.

---

## Part B: branch `employee-view` (from `pdf-text` after Part C is merged)

### Task 4: Plan actions for one employee

**Files:** Modify `payroll.py`. Test: `tests/test_payroll.py`.

**Interfaces (Produces):**
- `EMPLOYEE_KEYS = ("emp_no", "name", "hours_column", "overrides", "entries", "zakat", "levy", "message",
  "pay_basis", "basic_rate")`: the keys the employee view may change. Values are checked afterwards by `validate_plan`.
- `change_employee(plan: dict, employee_id: str, changes: dict) -> dict`: sets those keys on the employee in place and
  returns the employee.
  - A key not in `EMPLOYEE_KEYS` raises `OcrError("BAD_PAYROLL", <the standard "could not be understood" sentence>)`.
  - An unknown id raises `OcrError("EMPLOYEE_NOT_FOUND", "This employee is no longer in the payroll of this month. Go
    back to the company and open it again.")`, the sentence `look_panel` already uses. Use one shared constant for
    both.
- `take_off_card(plan: dict, ref: str) -> str | None`: removes `ref` from whichever employee has it and returns that
  employee's id. Returns `None` when nobody has it.
- `remove_employee(plan: dict, employee_id: str) -> None`. An unknown id raises the `EMPLOYEE_NOT_FOUND` error.
- `add_employee(plan: dict, new_id: str, company: str) -> dict`: appends and returns the same empty employee that the
  old page's "Add employee" makes (`emp_no` "", `name` "", `jobs` [], `hours_column` None, `overrides` {}, `entries`
  {}, `zakat` 0, `levy` 0, `message` "", `pay_basis` "monthly", `basic_rate` 0, `company`).

- [ ] **Step 1: Write the failing tests.**
  - `test_change_employee_sets_only_the_keys_given`: name "ALI" -> "ALI B"; `emp_no` and `overrides` unchanged.
  - `test_change_employee_refuses_a_key_it_does_not_know`: `{"jobs": []}` gives code `BAD_PAYROLL`; `{"id": "x"}` too.
  - `test_an_unknown_employee_cannot_be_changed_or_removed`: code `EMPLOYEE_NOT_FOUND` for both.
  - `test_take_off_card_returns_whose_it_was`: returns `"e1"`, the ref is gone from e1, and a second call returns
    `None`.
  - `test_add_employee_is_empty_and_valid`: `validate_plan(plan, set())["employees"][-1]["company"] == "BINA"`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write the functions.**
- [ ] **Step 4: Check that the whole suite passes.**
- [ ] **Step 5: Commit** "Payroll: plan actions for one employee".

### Task 5: Endpoints for the employee view and the pay preview

**Files:** Modify `app.py`. Test: `tests/test_app.py`.

**Interfaces:**
- Consumes: Task 4's functions, and `change_plan`, `page_loader`, `candidates_of`, `number_new_employees` and
  `million_by_no` from `app.py`.
- Produces `GET /api/payroll/{month}/employee/{id}`. It reads the plan as saved; nothing is changed (no `open_month`).
  It returns:

  | Key | Content |
  |---|---|
  | `month` | the month |
  | `employee` | the saved plan entry |
  | `result` | `compute_all` for this one employee with their company, plus `"columns"` (labels of their cards, as in `payroll_view`) |
  | `company` | the employee's company |
  | `cards` | `[{"ref", "doc", "name"}]`, one per ref, named as `candidates_of` names it |
  | `others` | `[{"id", "emp_no", "name"}]`: the same company's other employees |
  | `lists` | the plan's lists |
  | `list_heads`, `fields` | as `payroll_view` gives them |
  | `million` | `[{"emp_no", "name"}]`, or `None` |

- `PUT /api/payroll/{month}/employee/{id}`, body `{"changes": {...}}`: runs `change_employee` under the lock and
  `validate_plan`, then saves. When `emp_no` or `name` changed, it also runs `remember_employees`. It returns the same
  response as GET.
- `DELETE /api/payroll/{month}/employee/{id}` returns `{"ok": true}`.
- `POST /api/payroll/{month}/employee`, body `{"company": str}`: runs `add_employee`. When the company is not "", the
  new employee is given a number with `number_new_employees`. Returns `{"employee": id}`.
- `POST /api/payroll/{month}/take-off`, body `{"ref": str}`. Returns `{"ok": true}`. A ref that nobody has gives
  `OcrError("BAD_PAYROLL", "That card is not on any employee any more. Reload the page.")`.
- `POST /place` gains an optional `"move": true`, which runs `take_off_card` before placing. Without it, the endpoint
  works as today.
- `PUT /api/payroll/{month}/lists`, body `{"lists": {...}}`: sets `plan["lists"]` and saves through `validate_plan`.
- `GET /api/payroll/{month}/pay?company=`, which returns `{"rows": [...]}` with one row per employee of the company.
  Each row:

  | Key | Content |
  |---|---|
  | `id`, `emp_no`, `name` | the employee |
  | `typed_basis`, `typed_rate` | the employee's own `pay_basis` and `basic_rate` |
  | `rate_source`, `pay_basis`, `basic_rate`, `pay` | from the result |
  | `days_worked` | the result's value |
  | `complete` | from the result |

- [ ] **Step 1: Write the failing tests** (a made-up MAJU JAYA with ALI and SITI, one card each, placed by opening the
  month):
  - `test_the_employee_view_shows_figures_cards_and_colleagues`:
    - `result.values.days_worked.value == 30`;
    - `cards[0]["doc"]` is ALI's document;
    - `others == [SITI]`;
    - `columns == ["Date", "Total"]`.
  - `test_an_override_is_saved_and_returned`: changes `{"overrides": {"ot_1_5": 4}}` give `result.values.ot_1_5 ==
    {value 4, edited True}`. Then `{"overrides": {}}` gives the computed value back.
  - `test_saving_one_field_keeps_what_another_tab_changed`: `PUT /employees/{id}` with `{"emp_no": "MJ9"}`, then
    employee changes `{"name": "ALI B"}`, gives `emp_no == "MJ9"`.
  - `test_an_employee_removed_elsewhere_says_so`: after DELETE, these all give `EMPLOYEE_NOT_FOUND`: the GET, the PUT,
    and a `/place` with `"employee"` = that id.
  - `test_moving_a_card_takes_it_off_its_employee`: ALI's only card is moved to SITI (`move: true`). Then:
    - SITI has both refs and ALI has `[]`;
    - the company screen has a `nocard` item for ALI;
    - the same move without `move` is refused with "A document can belong to one employee only…".
  - `test_a_card_taken_off_is_whose_card_again`: after take-off, the company screen has an `unplaced` item with that
    ref. Taking it off again gives `BAD_PAYROLL`.
  - `test_add_employee_by_hand_gets_a_number`: `POST /employee {"company": "MAJU JAYA"}` returns an id whose GET shows
    `emp_no` starting `"MAJUJAY"` and `company == "MAJU JAYA"`.
  - `test_a_removed_allowance_line_clears_its_figures`: `PUT /lists` with an allowance "Transport", then employee
    `entries` `{"allowance": {"Transport": 50}}`, then `PUT /lists` without it: the employee's `entries["allowance"]
    == {}`.
  - `test_the_pay_table_of_one_company`: two rows. After employee changes `{"pay_basis": "daily", "basic_rate":
    80}`, ALI's row has `pay.basic == 80 * 30` and `rate_source == "typed"`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write the endpoints.** Use `change_plan` for every write. `EMPLOYEE_NOT_FOUND` comes from the
  functions.
- [ ] **Step 4: Check.** The suite and `check_patterns` pass (Malay for the new sentence).
- [ ] **Step 5: Commit** "Payroll: endpoints for the employee view and the pay table".

### Task 6: The employee view on screen

**Files:**
- Create `static/paycommon.js`. Move into it from `payroll.js`: `MONTH_NAMES`, `WEEKDAYS`, `DAY_ORDER`, `DAY_WORDS`,
  `defaultPayrollMonth`, `addedByThemselves`, `newNumbersText`, `employeeNoHint`, `fmt`, `runReason`, `showMonthRun`,
  `PAY_BASES` and `payBasisWord`. Delete them from `payroll.js`: a top-level `const` declared in two scripts is an
  error.
- Create `static/employee.js`.
- Modify `static/index.html`:
  - add `<main id="employee" hidden>` with `em-back` ("← Back to the company"), `em-title`, `em-save`, `em-error`,
    `em-cards` and `em-window`;
  - add the script tags `paycommon.js` (after `app.js`) and `employee.js` (after `companies.js`).
- Modify `static/app.js`: `hideScreens` includes `employee`; `route` sends `#/payroll/<m>/e/<id>` to
  `showEmployee(month, id)`.
- Modify `static/companies.js`: `openEmployee(id)` opens `#/payroll/<m>/e/<id>` in a new tab.
- Modify `static/app.css`, `static/i18n.js` and `tools/check_i18n.py` (scan `paycommon.js` and `employee.js`).
- Test: the page test expects `id="employee"`, `paycommon.js` before `companies.js`, and `employee.js` after it.

Behaviour:
- **What the view shows.** It ports today's Results window from `payroll.js` for one employee:
  - the Employee No. and Name boxes. The No. box uses a datalist of `million`, and the old page's "From Million's
    list" / "New number made by Table Reader" notes stay;
  - Basic Rate and Monthly/Daily, with the basic-pay line;
  - every figure with its override and "Worked out: … – use it";
  - the Leave table, the overtime table, and the Allowance & Deduction tab with Message, Zakat and Levy;
  - "Please check:" and "Day by day".
  The labels stay English. First/Previous/Next/Last go.
- **The employee's cards.** Above the window, `em-cards` lists each card with:
  - **Open the card** (new tab);
  - **Move to…**, a select of `others` plus "A new employee", then a **Move** button;
  - **Take off**, after a confirm.
  The same block holds the **Hours column** select (as today) and **Remove employee** (confirm, then go back to the
  company screen).
- **Saving.**
  - Number and text boxes send their one key after 500 ms without typing. Selects and buttons send at once.
  - The response redraws the window through the ported `keepFocus`.
  - "Add a line" and "×" on a line send `PUT /lists`.
  - Errors go to `em-error`. `EMPLOYEE_NOT_FOUND` shows its sentence and hides the window.

Steps:
- [ ] **Step 1: Extend the page test and see it fail.**
- [ ] **Step 2: Move the helpers to `paycommon.js`.** Then check: the suite and `check_i18n` pass, and the old page
  still loads (headless Edge: `#/payroll/<m>/old` draws without a console error).
- [ ] **Step 3: Build the view.**
- [ ] **Step 4: Check.** The suite, `check_i18n` and `check_patterns` pass.
- [ ] **Step 5: Click it through** in headless Edge on made-up data. Check that:
  - Open employee from a company item opens the view;
  - typing the name saves it and survives a reload;
  - an override shows the blue edge, and "use it" clears it;
  - a Transport allowance line plus a figure, then ×, clears the figure;
  - Move to SITI moves the card, and ALI's view has no card;
  - Take off creates the company item;
  - Remove employee goes back to the company screen.
- [ ] **Step 6: Commit** "Payroll: the employee view".

### Task 7: Pay preview tab and Add employee on the company screen

**Files:** Create `static/paytable.js`. Modify `static/index.html` (company screen: `co-tab-employees` /
`co-tab-pay` buttons, `<div id="co-pay" hidden>`, `co-pay-download`, a small `co-add` "Add employee" link under the
employee table; script tag after `employee.js`), `static/companies.js`, `static/app.css`, `static/i18n.js`,
`tools/check_i18n.py`. Test: the page test expects `id="co-pay"` and `paytable.js`.

Behaviour:
- **The Pay preview tab** has today's pay table (`renderDaily` / `fillDaily` ported) for the company's rows from
  `GET /pay`. Basis and rate are editable and save through the employee PUT. The rows stay in place while a box has
  focus. There is a total row, the legend sentence from section 4 of the old page, and "Download the pay table (CSV)"
  (`/basic-pay?company=`).
- **"Add employee"** posts `/employee` with the company and opens the new employee's view in a new tab.
- The tab chosen is not remembered: the company screen always opens on Employees.

Steps:
- [ ] **Step 1: Extend the page test and see it fail.**
- [ ] **Step 2: Build it.**
- [ ] **Step 3: Check.** The suite, `check_i18n` and `check_patterns` pass.
- [ ] **Step 4: Click it through.** Check that:
  - Pay preview lists both employees;
  - typing a daily rate updates Basic pay and the total;
  - the CSV downloads;
  - Add employee opens a view whose number starts with the company's letters.
- [ ] **Step 5: Commit** "Payroll: pay preview tab and Add employee on the company screen".

### Task 8: Remove the old page

**Files:**
- Delete `static/payroll.js`.
- Modify `static/index.html`: remove `<main id="payroll">`, the `mo-old` link and the `payroll.js` tag.
- Modify `static/app.js`:
  - `hideScreens` drops `payroll`;
  - in `route`, `.../old` opens `showMonth`, and `.../old/e/<id>` opens `showEmployee`;
  - the `nav-payroll` click handler, which lived in `payroll.js`, moves to `companies.js`.
- Modify `static/companies.js`: remove the `mo-old` handler and `window.prOpenCompany`.
- Modify `tools/check_i18n.py`: drop `payroll.js`.
- Modify `static/i18n.js`: remove the Malay entries that only the deleted texts used, only if `check_i18n` lists them
  as unused. Otherwise leave them.
- Test: the page test expects no `id="payroll"`, no `payroll.js` and no "Old payroll page".

Steps:
- [ ] **Step 1: Extend the page test and see it fail.**
- [ ] **Step 2: Remove the old page.** Run `grep -n "pr-\|prFilter\|showPayroll" static/` and expect no hits.
- [ ] **Step 3: Check.** The suite, `check_i18n` and `check_patterns` pass.
- [ ] **Step 4: Click it through.** Check that:
  - `#/payroll/<m>/old` opens the overview;
  - `#/payroll/<m>/old/e/<id>` opens the employee view;
  - the top bar's Payroll link opens the overview;
  - the console has no error on any screen.
- [ ] **Step 5: Commit** "Payroll: the old payroll page is removed".

### Task 9: Remove the old page's endpoints, port the tests

**Files:** Modify `app.py`: remove `get_payroll`, `save_payroll`, `auto_add_employees` and `payroll_xls`. Keep
`payroll_view` (`month_state` uses it); its `assign` is no longer needed, so drop it. Test: `tests/test_app.py`.

Every test in `tests/test_app.py` that calls `GET` / `PUT /api/payroll/{month}`, `/auto` or `/xls` is handled by one
of three rules:
1. **It sets up employees:** upload after the app starts and open the month (`GET /companies`); the files join by
   themselves.
2. **It changes a plan and reads results:** use the employee PUT / GET, `PUT /settings`, `PUT /lists` or `/place`.
3. **It tests only the removed endpoint's own behaviour:** delete it. That covers `/auto`'s company filter, the
   per-company `/xls` "anyway" questions and the old page's save guard for company settings. Before deleting, name in
   the commit message the `test_payroll.py` test that still covers the same rule (for example
   `test_a_name_that_is_someone_else_in_million_needs_an_explicit_yes`), or port it to `/run`.

These are the tests today (from the list made while planning). Each must be ported, kept, or deleted with its reason
in the commit message:

- `test_a_card_that_is_nobodys_can_be_set_aside_as_not_a_time_card`
- `test_a_later_card_joins_its_worker_and_a_removed_card_is_not_added_again`
- `test_a_month_grid_with_several_workers_gives_one_employee_per_row`
- `test_a_new_worker_named_on_the_card_gets_millions_employee_no_and_the_mark_goes_when_it_is_changed`
- `test_add_employees_from_files_of_a_company`
- `test_an_old_bad_plan_is_left_alone_when_a_new_file_of_the_month_arrives`
- `test_an_old_page_tab_opened_before_company_settings_does_not_wipe_them`
- `test_basic_pay_table_download`
- `test_files_already_there_when_the_app_starts_are_left_as_they_are`
- `test_million_xls_download_asks_about_an_employee_no_that_is_not_in_employees_txt`
- `test_million_xls_download_refuses_then_allows_incomplete`
- `test_millions_employee_list_is_imported_offered_and_checked_before_download`
- `test_pay_basis_and_rate_come_from_millions_report_until_typed`
- `test_payroll_api_refuses_bad_input`
- `test_payroll_csv_for_one_company`
- `test_payroll_file_picker_gets_the_company_of_each_file`
- `test_payroll_saves_even_when_a_ticked_time_card_no_longer_exists`
- `test_payroll_screen_api_end_to_end`
- `test_payroll_uses_only_the_chosen_workers_page_of_a_report`
- `test_placing_a_card_and_refusing_one_that_is_taken`
- `test_placing_a_card_works_while_another_reading_is_damaged`
- `test_the_look_panel_leaves_out_a_card_that_cannot_be_opened`
- `test_the_month_run_makes_one_file_and_lists_who_is_held_back`
- `test_the_old_page_keeps_company_settings_when_it_saves`
- `test_two_cards_of_one_worker_become_one_employee_when_the_month_is_opened`

The rules a ported test still has to prove:
- the Origin check refuses a write from another site with 403 (move this to the employee PUT);
- a bad body gives 400;
- a gone document is taken off, not an error.

Steps:
- [ ] **Step 1: Remove the endpoints** and run the suite. The failures expected are exactly the tests above.
- [ ] **Step 2: Port or delete the tests** one by one, following the rules.
- [ ] **Step 3: Check.** The suite passes, and `grep -n "/auto\"\|/xls\"" tests/ static/` finds nothing.
- [ ] **Step 4: Commit** "Payroll: endpoints only the old page used are removed; tests moved to the new screens'
  endpoints".

### Task 10: Part B proof, guides, notes, review

- [ ] **Step 1: Check the real September data.** On a copy, in memory, counts only:
  - every employee's figures and problem texts with the new code equal `pdf-text`'s (84 employees);
  - the employee GET for each employee gives the same figures as the month view;
  - `/run`'s ready and held counts are unchanged.
- [ ] **Step 2: Update the guides.** In `GUIDE - Table Reader to Million.html` and `PANDUAN - Table Reader ke
  Million.html`, replace the old-page steps with: month overview, a company, Needs you, New in Million, Make the
  month's Million file (summary first). The PDF guide is not regenerated without the user's OK.
- [ ] **Step 3: Write the notes.** PROGRESS.md gets session 22 (Part B), including the review findings left for later
  that the old page's removal settles. NEXT-SESSION.md section 0 and section 1 lose the old page. Commit "Notes:
  stage 4 part B; guides without the old page".
- [ ] **Step 4: Review.** One fresh reviewer reviews the whole branch, and the important findings are fixed.
- [ ] **Step 5: Stop.** Ask the user before merging, rebuilding, pushing, and updating the `download` branch.
