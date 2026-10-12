# Company-first payroll, stage 2: the one-look panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One panel per employee that shows, card by card, only the lines of the time cards the calculation could not
use, beside the card's picture, with one button that accepts them; it replaces "Open card n" on the company screen.

**Architecture:** The calculation already raises an "unclear" (or "date") problem for each line it cannot use. Those
problems now also say *where* (document, page, row, day, the columns read on that line), so the panel's list comes
from the calculation itself. A pure function in `companies.py` turns an employee's located problems plus the cards'
current cells into the panel's cards. One read endpoint serves it; accepting goes through the existing corrections
endpoint, marked `via: "look"`. A new page script `static/look.js` draws the panel.

**Tech Stack:** Python 3.14, FastAPI, pytest; plain HTML/JS/CSS with no build step; PowerShell 5.1 on Windows.

**Spec:** `docs/superpowers/specs/2026-10-12-company-first-payroll-design.md` (sections 4 "Times to look at" /
"Cells to type", 5, 6.2 `via`, 9.3 stage 2). Stage 1 plan: `2026-10-12-company-first-payroll-stage-1.md`.

**Decided here (not in the spec):**
- **No highlight of the row on the picture.** Readings have no positions (`ocr.py` returns cells only), so the picture
  cannot be scrolled to a row; drawing a box anywhere would be a guess. The panel shows the page that holds the
  selected line, a click on the picture toggles a closer view, and each line says its row number ("row 9").
- A blank yellow box that is really empty gets a small **"Nothing written"** button: clearing an already empty box is
  impossible, and the user must say it is empty rather than the app assuming it.
- A located problem on a cell that is *not* yellow (an IN with no OUT, "abc" as hours, day 32) is shown in the panel
  too, with the calculation's sentence, because the panel is where the line is fixed. Only changed boxes of such a
  line are saved; accepting cannot clear it unless something is typed.
- "Days that do not add up" problems that are about one line (kind `date`) get the Look button too; the others
  (missing days, a day on two cards, PH on a working day, printed totals) keep "Open employee" until a later stage.
- Panel address: `#/payroll/<month>/look/<employee id>`, in the same tab; it returns to the employee's company screen.

## Global Constraints

- **Never guess.** Nothing is prefilled except what Claude saw, with a leading / trailing `?` dropped (as the document
  page does). A box with a `?` inside or nothing in it "must be typed". `result.json` is never written.
- **The calculation does not change.** No figure, problem kind or problem text changes; issues only gain an `at` key.
  Task 6 proves every September figure and problem text is unchanged.
- **Personal data.** The repo is public. Tests, comments, commit messages and chat use made-up names only (MAJU JAYA,
  BINA, ALI, SITI, ZUL). Real-data checks print counts only.
- **Before every commit:** `.venv\Scripts\python -m pytest -q` passes; `.venv\Scripts\python tools\check_i18n.py`
  shows `missing Malay: 0`; `.venv\Scripts\python tools\check_patterns.py` shows `0 not translated`; the diff's
  real-name scan is clean.
- **Every new text shown to the user** goes through `t()` / `tn()` / `tm()` and has a Malay entry in `static/i18n.js`.
- **Commits are local**, on branch `look-panel` made from `pdf-text`. Pushing, rebuilding the app and the `download`
  branch need the user's OK.
- Follow the surrounding style: 120-column lines, docstrings that say what and why, comment density as around.

## Review Focus

1. A grid row chosen as one worker (`<id>#p1r3`): the panel must save to the document's row 3 (index 2), not row 1 of
   the one-row slice the calculation sees. Pinned in Task 1 (`first_row`) and Task 4 (save lands on index 2).
2. The same document on two refs of one employee (two pages of one report): one card in the panel, lines of both
   pages, no line twice. Pinned in Task 3.
3. Accepting while the document page in another tab changed a cell: the panel reloads from the server after saving
   and shows only what is still wrong. Pinned in Task 4 (second GET after a save has no rows) and Task 5 (reload).
4. An employee id that is not in the month (stale tab, removed employee): a plain message, not a crash. Task 4.
5. A card whose reading cannot be opened (damaged, still being read): the panel opens with the other cards and does
   not list that one. Task 4.

---

## File Structure

| File | Responsibility |
|---|---|
| `payroll.py` (modify) | `read_days`, `_clock_day`, `_read_grid` add `at` to line problems; `compute_all` turns the document position into its id. |
| `jobs.py` (modify) | `_validate_edit` keeps `via: "look"` on a correction. |
| `companies.py` (modify) | `look_cards` (the panel's cards); `issue_items` counts located lines (`places`) and keeps only unlocated texts. |
| `app.py` (modify) | `page_loader` (shared by `payroll_view` and the panel; part pages carry `first_row`); GET `/api/payroll/{month}/look`. |
| `static/look.js` (new) | The panel. |
| `static/companies.js`, `static/app.js`, `static/index.html`, `static/app.css`, `static/i18n.js`, `tools/check_i18n.py` (modify) | Look button, route, the `<main id="look">`, styles, Malay, the check scans `look.js`. |
| `tests/test_payroll.py`, `tests/test_jobs.py`, `tests/test_companies.py`, `tests/test_app.py` (modify) | Tests. |

---

### Task 1: Where each line problem is

**Files:** Modify `payroll.py` (`read_days`, `_clock_day`, `_read_grid`, `compute_all`). Test: `tests/test_payroll.py`.

**Interfaces:**
- Produces: an issue of kind `unclear` or `date` raised about one line carries
  `"at": {"doc": str, "page": int, "row": int, "day": int | None, "columns": list[str]}` after `compute_all`
  (`doc` = the document id, the ref without `#p..`; `row` = 0-based row in the *whole* document page; `columns` = the
  columns the calculation read on that line, in the page's column order). Straight from `read_days` / `calculate`,
  `doc` is the position in `docs` (int). Problems about a whole page (no hours column, a sheet with many workers,
  printed totals, a day on two cards, missing days) have no `at`.
- A page may carry `first_row: int` (0-based row of its first row in the document; absent = 0).

Columns read, per line: hours card -> date, hours column, and the report columns on a clock report; IN/OUT card ->
date and every IN/OUT column; "Total empty but other columns have times" -> date, hours column and those other
columns; "date unclear" -> the date column and every timed column; a month grid -> the one day column (`day` set).

- [ ] **Step 1: Failing tests**
  - `test_an_unclear_hours_cell_says_where_it_is`: card rows days 1-3, day 2's Total yellow; `calculate` -> the unclear
    issue's `at == {"doc": 0, "page": 1, "row": 1, "day": 2, "columns": ["Date", "Total"]}`.
  - `test_an_unclear_in_out_time_says_its_columns`: labels `("Date", "In", "Out")`, day 4 Out yellow -> `at["columns"]
    == ["Date", "In", "Out"]`, `at["day"] == 4`.
  - `test_an_unclear_date_has_no_day`: day cell yellow with hours written -> `at["day"] is None`, columns include Date.
  - `test_a_grid_row_part_points_at_the_documents_row`: a one-row grid page with `first_row: 2`, day 5 yellow ->
    `at == {"doc": 0, "page": 1, "row": 2, "day": 5, "columns": ["5"]}`.
  - `test_compute_all_names_the_document_of_a_problem`: employee jobs `["d9#p1"]`, loader returns the card above ->
    `at["doc"] == "d9"`; a lost (unloadable) first job does not shift the position.
  - `test_whole_page_problems_have_no_place`: "no hours column" issue has no `at`.
- [ ] **Step 2:** Run `.venv\Scripts\python -m pytest tests/test_payroll.py -q -k "where or columns or no_day or part_points or names_the or no_place"` -> FAIL.
- [ ] **Step 3:** Implement: `read_days` enumerates `docs` and builds the `at` for each row; `_clock_day(..., at)` and
  `_read_grid(..., k)` attach it; `compute_all` keeps the refs it loaded alongside `docs` and replaces `at["doc"]`.
- [ ] **Step 4:** Whole suite passes (`.venv\Scripts\python -m pytest -q`).
- [ ] **Step 5:** Commit "Payroll: each line problem says where it is on the card".

### Task 2: A correction accepted through the panel is marked

**Files:** Modify `jobs.py` (`_validate_edit`). Test: `tests/test_jobs.py`.

- [ ] **Step 1: Failing tests** `test_a_correction_from_the_panel_is_marked`: `save_edits(id, [{page, row, column,
  value: "9", via: "look"}])` -> stored entry has `via == "look"`; then the same cell saved without `via` (Enter on the
  document page) -> no `via`. `test_an_unknown_via_is_refused`: `via: "x"` -> `OcrError` code `BAD_EDIT`.
- [ ] **Step 2:** Run them -> FAIL. **Step 3:** Implement (only `"look"` is accepted; header changes may carry it too).
- [ ] **Step 4:** Suite passes. **Step 5:** Commit "Corrections: mark the ones accepted through the one-look panel".

### Task 3: The panel's cards

**Files:** Modify `companies.py`. Test: `tests/test_companies.py`.

**Interfaces:**
- Consumes: Task 1's `at`; merged pages (`jobs.merged_pages`) of whole documents.
- Produces: `companies.look_cards(result: dict, employee: dict, pages: dict[str, list[dict]], names: dict[str, str])
  -> list[dict]`, each `{"doc": str, "name": str, "lines": [{"page": int, "row": int, "day": int | None,
  "texts": list[str], "cells": [{"column": str, "value": str | None, "raw_text": str, "needs_review": bool,
  "unclear_reason": str | None, "edited": bool}]}]}`. Cards in the employee's card order; lines by (page, row, day);
  one line per (page, row, day), its columns the union of its problems' columns in the page's column order; `texts`
  the calculation's sentences for that line. A document missing from `pages` is left out.
- Produces: `issue_items` items of kind `look` and `days` get `"places": int` (distinct located lines) and their
  `texts` hold only problems without `at`; an item with neither is not made.

- [ ] **Step 1: Failing tests**
  - `test_look_cards_one_card_per_document_in_card_order` (refs `d2`, `d1#p1`, `d1#p2`; problems on d1 pages 1 and 2
    and on d2 -> docs `["d2", "d1"]`, d1 has 2 lines, page order kept).
  - `test_a_line_with_two_problems_is_one_line_with_both_columns_and_texts` (grid: two days are two lines; a card
    row with an unclear Total and an unclear report column is one line).
  - `test_look_cards_show_the_cells_as_they_are_now` (an edited cell: `edited` True, `needs_review` False).
  - `test_a_look_item_counts_places_and_keeps_only_unplaced_texts` (update the existing exact-dict test too).
- [ ] **Step 2:** Run -> FAIL. **Step 3:** Implement. **Step 4:** Suite passes.
- [ ] **Step 5:** Commit "Companies: the one-look panel's cards from the calculation's own problems".

### Task 4: The panel's endpoint

**Files:** Modify `app.py`. Test: `tests/test_app.py`.

**Interfaces:**
- Produces: `GET /api/payroll/{month}/look?employee=<id>` -> `{"month", "employee", "name", "company", "cards"}`
  (`cards` = Task 3). Unknown employee -> `OcrError("EMPLOYEE_NOT_FOUND", "This employee is no longer in the
  payroll of this month. Go back to the company and open it again.")`. Does not change the plan (no `open_month`).
- `page_loader()` in `create_app`: the `load_pages(ref)` that `payroll_view` used, with its cache, shared; a part
  page carries `first_row`.

- [ ] **Step 1: Failing tests** (made-up cards through `company_client`):
  - `test_the_look_panel_lists_the_yellow_lines_and_accepting_clears_them`: a 30-day card with day 9's Total yellow
    (`cell(None, "9?", 30, "smudged")`), employee placed -> GET gives one card, one line, day 9, Total cell
    `needs_review`; PUT `/api/jobs/<id>/cells` `{changes: [{page, row: 8, column: "Total", value: "9", via: "look"}]}`
    -> GET gives `cards == []`; the company screen's items no longer have `look`.
  - `test_the_look_panel_saves_a_grid_row_to_the_documents_row`: a 3-worker grid, worker 3's day 2 yellow -> line
    `row == 2`.
  - `test_the_look_panel_for_an_unknown_employee_says_so`: code `EMPLOYEE_NOT_FOUND`.
  - `test_the_look_panel_leaves_out_a_card_that_cannot_be_opened`: one of two cards' `result.json` damaged -> 200, the
    other card listed.
- [ ] **Step 2:** Run -> FAIL. **Step 3:** Implement. **Step 4:** Suite passes.
- [ ] **Step 5:** Commit "Payroll: an endpoint for the one-look panel".

### Task 5: The panel on screen

**Files:** Create `static/look.js`. Modify `static/index.html` (`<main id="look" hidden>` with title, card counter,
`<` `>`, error banner, picture box, lines box, "n still need typing" line, Accept button; script tag after
`companies.js`), `static/app.js` (`hideScreens` includes `look`; `route` handles `#/payroll/<month>/look/<id>` before
the company pattern), `static/companies.js` (look / days items with `places > 0`: head "{name}: {n} lines to check on
the time cards" and a primary **Look** button that sets the hash; keep "Open employee" for the rest), `static/app.css`,
`static/i18n.js`, `tools/check_i18n.py` (scan `look.js`), `tests/test_app.py` (`test_the_page_has_the_company_first_screens`
also expects `id="look"` and `look.js`).

Behaviour (spec §5): one card at a time, `card n of m`, `<` `>`; left the page picture of the selected line (click =
closer view, scroll inside the box); right one row per line: "Day 9" (or "Row 4" when there is no day), one box per
cell, yellow ones marked, the reason (`unclear_reason`, else the calculation's text) under it, "must be typed" on a
box whose shown text is empty or has a `?` inside; clicking a line shows its page. **Accept all (n)** (n = yellow
boxes; "Save" when there are none) is disabled while a must-type box is unchanged and not marked "Nothing written";
it sends one PUT for the card: every yellow box's value plus every changed other box, each with `via: "look"`. Then
the panel reloads: the next card with lines, the same card with a note if lines are left, or back to the company
screen when there is nothing left.

- [ ] **Step 1:** Extend the page test; run -> FAIL. **Step 2:** Build the screen. **Step 3:** Suite, `check_i18n`,
  `check_patterns` pass.
- [ ] **Step 4:** Click-through in headless Edge on made-up data (scratchpad server, script injected): Look opens the
  panel; Accept disabled until the `?` box is typed; accept moves to card 2, then back to the company screen with the
  item gone; "Nothing written" enables Accept; the saved corrections carry `via: "look"`.
- [ ] **Step 5:** Commit "Payroll: the one-look panel".

### Task 6: Proof on the real month, notes

- [ ] **Step 1:** On a copy of the real data, in memory, counts only: every employee's figures, problem kinds and texts
  before (pdf-text) and after (look-panel) are identical; print how many employees have located lines, how many lines,
  and how many problems of kind unclear/date have no `at` (expected 0 except "date is unclear" rows already counted).
- [ ] **Step 2:** PROGRESS.md session 19, NEXT-SESSION.md section 0 (also correct session 18: merged and rebuilt).
- [ ] **Step 3:** Commit "Notes: one-look panel (stage 2)". Merge / rebuild only on the user's OK.
