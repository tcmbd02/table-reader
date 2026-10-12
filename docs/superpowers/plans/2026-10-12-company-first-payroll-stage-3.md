# Company-first payroll, stage 3: month and company settings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The month keeps one default (calendar, normal hours, break); a company can have its own complete set, used
for its employees' figures, and can carry it into the next month.

**Architecture:** Pure helpers in `payroll.py` resolve an employee's settings (the company's own set, else the month
default) and `compute_all` uses them per employee; the arithmetic does not change. The plan file gains `companies`
(spec 6.2). `app.py` passes each employee's company to the calculation and gets two save actions. A new
`static/settings.js` draws one settings editor used by "Month settings" (overview) and "Company settings" (company
screen).

**Tech Stack:** Python 3.14, FastAPI, pytest; plain HTML/JS/CSS, no build step; PowerShell 5.1 on Windows.

**Spec:** `docs/superpowers/specs/2026-10-12-company-first-payroll-design.md` sections 3.2 (Month settings, "own
settings"), 3.3 (Company settings), 6.1-6.4, 9.3 stage 3, 11.

**Decided here (not in the spec):**
- **A company whose own settings are older than a change to the month's default gets a "Needs you" item** ("The
  month's default changed after this company got its own settings: check its calendar"), with **Open settings** and
  **It is right** (saves the same settings again). The spec only puts the sentence on the settings screen; a public
  holiday marked in the default after a company was given its own calendar would otherwise go unnoticed. Nothing is
  changed by itself.
- Settings are saved with a **Save** button (the editor works on a copy), not on every click as the old page does.
- Carry-over uses the latest saved month before the new one (as the table lines already do), only for companies with
  `keep`.
- The old page's "1. Month and days" stays; it edits the month default.

## Global Constraints

- **The calculation does not change.** A plan with no `companies` gives exactly today's figures (Task 6 proves it on
  the real September data). Each employee is worked out with `payroll.with_settings(plan, company)`.
- **Never guess.** Nothing is copied into a company's own set except at the moment the user chooses "This company is
  different" (a copy of the default) or when a kept set starts the next month (rules in Task 2). Public holidays are
  never carried over.
- Existing month files open unchanged; nothing is converted. `companies` holds only companies with their own set.
- **Personal data.** Made-up names only (MAJU JAYA, BINA, ALI, SITI). Real-data checks print counts only.
- **Before every commit:** full pytest passes; `check_i18n.py` 0 missing; `check_patterns.py` 0 not translated;
  real-name scan of the diff clean. Every new text has a Malay entry.
- Commits local on branch `company-settings` (from `pdf-text`). Merge, push, rebuild only on the user's OK.

## Review Focus

1. The old payroll page saves the whole plan: it must not drop `companies`. Pinned in Task 1 (validate keeps it) and
   Task 3 (PUT /api/payroll/{month} round trip).
2. A company name with signs (`A & B (M) SDN. BHD.`) in the save action. Pinned in Task 3 (name in the JSON body).
3. An employee with no company, or whose cards are of two companies: uses the default. Pinned in Task 1.
4. A month with 31 days carried into one with 30 / 28: the weekday rule, not a day-by-day copy. Pinned in Task 2.
5. Hours or break out of range, a calendar with a missing day: refused with the existing plain messages. Task 1.

---

## File Structure

| File | Responsibility |
|---|---|
| `payroll.py` | `SETTING_KEYS`; `settings_for`, `with_settings`, `default_changed`, `own_settings`, `carry_companies`; `validate_plan` keeps `companies`; `compute_all(..., companies=None)`; `PayrollStore.load` carries kept sets into a new month. |
| `companies.py` | `company_view(..., settings=None)`: the "settings" item and the view's `settings`; `overview` rows get `own`. |
| `app.py` | Each employee's company passed to `compute_all`; PUT `/api/payroll/{month}/settings` (month default); PUT `/api/payroll/{month}/company-settings`; views carry settings. |
| `static/settings.js` (new) | `settingsEditor`, Month settings panel, Company settings panel. |
| `static/index.html`, `companies.js`, `app.css`, `i18n.js`, `tools/check_i18n.py` | Buttons, panels, "own settings" mark, the settings item, styles, Malay. |
| `tests/test_payroll.py`, `tests/test_companies.py`, `tests/test_app.py` | Tests. |

---

### Task 1: Settings per company in the calculation

**Interfaces — produces (payroll.py):**
- `SETTING_KEYS = ("normal_hours", "break_hours", "day_types")`
- `settings_for(plan: dict, company: str) -> dict` — the three keys, from `plan["companies"][company]` when present,
  else from the plan.
- `with_settings(plan: dict, company: str) -> dict` — `{**plan, **settings_for(plan, company)}`.
- `default_changed(plan: dict, company: str) -> bool` — the company has its own set and its `based_on` (the default
  when the set was last saved) differs from the plan's current default.
- `own_settings(plan: dict, values: dict | None) -> dict` — a company entry from the user's values (None = a copy of
  the default): `{normal_hours, break_hours, day_types, keep: bool, based_on: {the default's three keys}}`.
- `validate_plan` keeps `companies` (`{name: entry}`; names normalised like an employee's company, at most 80 chars and
  500 entries; each entry checked with the same rules and messages as the default; `keep` bool; `based_on` checked
  the same way). Missing -> `{}`.
- `compute_all(plan, load_pages, million=None, companies: list[str] | None = None)` — employee *i* is calculated with
  `with_settings(plan, companies[i])` when given.

- [ ] Tests: `test_a_company_with_its_own_settings_is_calculated_with_them` (normal hours 9 and day 7 a rest day for
  BINA: its employee's OT and Working Days follow; an employee of MAJU JAYA and one with no company use the default);
  `test_no_companies_gives_the_same_figures`; `test_validate_keeps_company_settings_and_refuses_bad_ones` (hours 25,
  break 6, a day missing -> the existing messages; a name with signs kept); `test_default_changed_after_own_settings`.
- [ ] Run -> FAIL; implement; suite passes; commit "Payroll: a company's own settings in the calculation".

### Task 2: Carry a company's settings into the next month

**Interfaces — produces:** `carry_companies(previous: dict, plan: dict) -> dict` — for each company of `previous` with
`keep`: normal hours and break as they were; in the new month every day is the new default's day, except that a day
whose weekday was a rest day on *every* such day of the previous month's company calendar is a rest day, and a
weekday that was not is a working day; a public holiday of the new default stays a public holiday; the previous
month's public holidays are not carried. `keep` stays true; `based_on` = the new default.
`PayrollStore.load(month)` for a month with no file adds `carry_companies(latest earlier plan, plan)`.

- [ ] Tests: `test_kept_settings_start_the_next_month_by_weekday` (BINA rests on Saturdays and Sundays in August
  (31 days) and works no PH; September: every Saturday and Sunday rest, the rest working, normal hours 9 kept;
  August's PH on day 31 not carried); `test_a_company_working_some_sundays_works_sundays_next_month`;
  `test_settings_not_kept_do_not_carry`; `test_a_new_month_file_starts_with_the_kept_settings` (PayrollStore).
- [ ] Run -> FAIL; implement; suite passes; commit "Payroll: a company's kept settings start the next month".

### Task 3: Settings in the server

**Interfaces — produces (app.py):**
- `payroll_view` and `look_panel` pass each employee's company to `compute_all` (the same `employee_company` the
  screens use).
- `PUT /api/payroll/{month}/settings` body `{normal_hours, break_hours, day_types}` -> `{"ok": true}`; refuses through
  `validate_plan`'s messages.
- `PUT /api/payroll/{month}/company-settings` body `{"company": str, "own": false}` (follow the default) or
  `{"company", "own": true, "normal_hours"?, "break_hours"?, "day_types"?, "keep": bool}` (no values = a copy of the
  default) -> `{"ok": true}`. `company` "" refused ("Choose the company first.", code `BAD_PAYROLL`).
- Both under `auto_lock`, through `validate_plan` and `plans.save`.
- The company view gets `settings: {own, normal_hours, break_hours, day_types, keep, default_changed, default}`; the
  overview gets `settings` (the month default) and each row `own`.

- [ ] Tests: `test_company_settings_change_its_employees_figures_and_back` (A & B (M): own normal hours 9 -> OT drops
  by the right amount; `own: false` -> back); `test_month_settings_apply_to_companies_that_follow_them`;
  `test_a_month_default_changed_after_own_settings_gives_an_item_until_saved_again`;
  `test_the_old_page_keeps_company_settings_when_it_saves`; `test_bad_settings_are_refused`.
- [ ] Run -> FAIL; implement (Task 4's `companies` additions are needed for the item test: do Task 4 first if they
  block); suite passes; commit "Payroll: save the month's and a company's settings".

### Task 4: The settings item and the "own settings" mark

**Interfaces — produces (companies.py):** `company_view(..., settings: dict | None = None)` — when
`settings["default_changed"]`, an item `{"kind": "settings", "company": name}` first in the list (it counts in
"Needs you"); the view returns `settings`. `overview(views, known)` rows carry `own` (`v["settings"]["own"]`, False
when absent).

- [ ] Tests (test_companies.py): `test_a_changed_default_is_an_item_of_a_company_with_own_settings`,
  `test_the_overview_marks_own_settings`.
- [ ] Run -> FAIL; implement; commit with Task 3 if done together.

### Task 5: The settings on screen

`static/settings.js` (loaded after companies.js, before look.js): `settingsEditor(month, values) -> {node, values()}`
— normal hours, break, the calendar (click: working -> rest -> public holiday, as the old page), the summary line.
**Month settings** button on the overview opens a card with the editor and **Save**. **Company settings** button on
the company screen (not for "(no company)") opens a card: "( ) Same as the month's default" / "( ) This company is
different:" + editor + "[ ] Use the same settings for this company next month" + **Save**; the line "The month's
default was changed after this; check the calendar." when `default_changed`. The "settings" item: head "{company}:
the month's default changed after this company got its own settings", detail "Check its calendar.", buttons **Open
settings** (opens the card) and **It is right** (saves the same settings). Overview: "own settings" after the status.
Page test expects `settings.js` between companies.js and look.js; check_i18n scans it.

- [ ] Build; suite, check_i18n, check_patterns pass.
- [ ] Click-through in headless Edge on made-up data: company settings 9 h + a rest day -> the employee row's figures
  change; back to the default -> as before; Month settings: a PH -> the own-settings company shows the item; It is
  right -> gone; "own settings" on the overview.
- [ ] Commit "Payroll: month and company settings on screen".

### Task 6: Proof on the real month, notes

- [ ] Real September (read-only, counts only): figures and problems identical before/after (no company has own
  settings), via `compute_all` with the employees' companies.
- [ ] PROGRESS.md session 20, NEXT-SESSION.md. Commit "Notes: company settings (stage 3)".
