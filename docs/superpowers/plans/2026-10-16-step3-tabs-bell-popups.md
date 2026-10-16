# Step 3: Tabs, Bell and Pop-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make step 3 (Payroll) show one thing at a time with few words: icon buttons on the month bar, messages in a
bell, Month settings / Company settings / Export as pop-ups, and the employee and the company in tabs.

**Architecture:** Front end only, plus one server line (the payroll folder can be opened). New shared helpers in
`static/app.js` (icons, pop-up), a new `static/bell.js` (messages), a new `static/hours.js` (the month calendar); the
existing `people.js`, `employee.js`, `settings.js` and `paycommon.js` draw into tabs and pop-ups instead of stacked
cards and banners. No calculation, stored data or address changes.

**Tech Stack:** Python 3.14, FastAPI, pytest; plain HTML/CSS/JS (no build, no Node); headless Edge click-throughs
(`tools/clickthrough/`, `sh tools/clickthrough/run.sh <scenario>`).

**Spec:** `docs/superpowers/specs/2026-10-16-step3-tabs-bell-popups-design.md` (read it first).

## Global Constraints

- Branch `step3-tabs` (made from `pdf-text` at bd1c781; holds the spec and this plan). Commit after every task.
  **Never push, merge, rebuild the app or touch the `download` branch** without the user's OK.
- The repo is PUBLIC: made-up names only (MAJU JAYA, A & B (M), ALI, SITI, ZUL, AMIN). Scan each diff before
  committing (`git diff --cached | grep -nE '[A-Z]{3,}'`).
- Never guess: nothing may fill a cell, a figure or an employee by itself.
- Every new text goes through `t()` / `tn()` with a Malay entry in `static/i18n.js`; Million's Edit Payroll labels
  stay English. End of every front-end task: `"$PY" tools/check_i18n.py` → `missing Malay: 0`,
  `"$PY" tools/check_patterns.py` → `0 not translated`.
- Text from the server goes in with `textContent` (`el()`), never `innerHTML`. Icons are `<svg><use href="icons.svg#ti-NAME">`.
- Storage only through `remember` / `recall` / `forget` (they swallow errors); the page must work when storage throws.
- **Icon-only buttons keep their words as a visually hidden `<span class="sr-only">`** (so screen readers and the
  click-throughs' `T.click('Month settings')` still find them) and the same words as `title`.
- Buttons and tab names 1-3 words; any explanation longer than one line goes in a fold (`<details>`) or a tooltip.
- `PY="C:/Users/TENGA CEKAP/Documents/table-reader/.venv/Scripts/python.exe"`; tests `"$PY" -m pytest -q` (558 pass at
  the start). Click-throughs need the main folder's venv (`websockets`), `check_reading` needs `SLOW_FILE=1`,
  `yellow_confirm` needs `YELLOW_FILE=1`. Windows, PowerShell 5.1, Git Bash; no bare `git stash`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Typing in the Pay tab, then at once another tab, another employee or a step button**: what was typed is saved
   (test in Task 8).
2. **A pop-up open when the address changes** (Back, a step button, "Next to fix"): the pop-up closes; no pop-up left
   over step 2 (test in Task 2).
3. **Storage refused** (`sessionStorage.setItem` throws): the bell still shows this visit's messages and the page
   works (test in Task 3).
4. **A company name with signs** (`A & B (M)`) in the Export chips, the company tab and its pop-ups: the right company
   is chosen and exported (test in Task 9).
5. **Many companies (about 30 on the real month)** in the Export pop-up: it scrolls inside itself and its buttons stay
   on the screen (test in Task 4).

---

### Task 1: Icons, and the payroll folder can be opened

**Files:**
- Create: `tools/make_icon_sprite.py`, `static/icons.svg`, `static/icons-LICENSE.txt`, `tests/test_icons.py`
- Modify: `static/app.js` (helpers), `static/app.css` (`.ico`, `.sr-only`, `.icon-btn`), `app.py` (`FOLDERS`),
  `tests/test_inbox.py:92-100`

**Interfaces:**
- Produces: `icon(name: string) -> SVGElement` (class `ico`, `aria-hidden`); `iconButton(name: string, label: string,
  props?: object) -> HTMLButtonElement` (icon + `<span class="sr-only">label</span>`, `title=label`, class
  `icon-btn` plus `props.class`, other props as `el()`); `POST /api/folders/payroll/open`.

- [ ] **Step 0: Ask the user** for the one-time download of the icons (spec §7.1). Source:
  `https://unpkg.com/@tabler/icons@3.19.0/icons/outline/<name>.svg` and its `LICENSE`, into a new empty folder in the
  scratchpad. Names: alert-triangle, arrows-exchange, bell, calendar, calendar-cog, cash, check, chevron-down,
  chevron-left, chevron-right, circle-check, clock, clock-minus, clock-pause, clock-plus, coin, copy, dots, download,
  eye, file-plus, file-spreadsheet, folder, id, info-circle, photo, plus, table, user-plus, users, x.
- [ ] **Step 1: Write the failing tests**

```python
# tests/test_icons.py
def test_every_icon_the_page_uses_is_in_the_sprite():
    sprite = (STATIC / "icons.svg").read_text(encoding="utf-8")
    have = set(re.findall(r'<symbol id="ti-([a-z0-9-]+)"', sprite))
    used = set()
    for f in [*STATIC.glob("*.js"), STATIC / "index.html"]:
        text = f.read_text(encoding="utf-8")
        used |= set(re.findall(r'icon(?:Button)?\("([a-z0-9-]+)"', text)) | set(re.findall(r'icons\.svg#ti-([a-z0-9-]+)', text))
    assert used and used <= have, sorted(used - have)

def test_the_sprite_carries_the_licence():
    assert "MIT" in (STATIC / "icons-LICENSE.txt").read_text(encoding="utf-8")
```

In `tests/test_inbox.py::test_the_page_can_open_the_two_folders`: `GET /api/folders` also returns
`"payroll": str(tmp_path / "payroll")`, and `POST /api/folders/payroll/open` opens it (`opened` gains that path).

- [ ] **Step 2: Run** `"$PY" -m pytest tests/test_icons.py tests/test_inbox.py -q` → FAIL (no sprite, no payroll folder).
- [ ] **Step 3: Implement.** `tools/make_icon_sprite.py <svg folder> <out>`: each `<name>.svg` becomes
  `<symbol id="ti-<name>" viewBox="0 0 24 24">` with its inner elements, `stroke="currentColor"` kept, in one
  `<svg xmlns=… style="display:none">`. Run it into `static/icons.svg`; copy the licence. `app.py`: `FOLDERS` gains
  `"payroll": plans.root`. Helpers in `app.js` next to `el()`. CSS: `.ico{width:1.15em;height:1.15em;vertical-align:-.2em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}`,
  the usual `.sr-only` clip rule, `.icon-btn{padding:6px 8px}`.
- [ ] **Step 4: Run** the two test files → PASS; the whole suite → 559+ pass.
- [ ] **Step 5: Commit** ("Icons (Tabler, MIT) as one sprite; the payroll folder can be opened from the page").

### Task 2: The pop-up, with Month settings and Company settings in it

**Files:**
- Modify: `static/index.html` (add `<dialog id="popup"><div class="pop-head"><h2 id="popup-title"></h2></div><div id="popup-body"></div><div id="popup-foot" class="need-buttons"></div></dialog>`; remove `#mo-settings`, `#co-settings`), `static/app.js`, `static/app.css`, `static/settings.js`, `static/people.js` (`showCompany` no longer hides `co-settings`), `static/steps.js` (`route()` calls `closePopup()` first)
- Create: `tools/clickthrough/popups.py`; Modify: `tools/clickthrough/rest_days.py` (`#mo-settings` → `#popup`)

**Interfaces:**
- Consumes: `icon`, `iconButton` (Task 1).
- Produces: `openPopup({ title: string, icon: string, body: Node[], buttons: HTMLButtonElement[], onClose?: () => void }) -> void`
  (closes any open one first; `showModal()`; × button and Esc close it; `max-height: 85vh`, body scrolls inside);
  `closePopup() -> void`; `popupOpen() -> boolean`.

- [ ] **Step 1: Write the failing click-through** `popups.py`:

```python
await page.goto(f"{BASE}/#/payroll/{M}")
await page.ev("T.until(() => location.hash.includes('/e/'), 'step 3')")
await page.ev("T.click('Month settings'); T.until(() => document.getElementById('popup').open, 'open')")
expect("settings in the pop-up", await page.ev("!!document.querySelector('#popup input[data-weekday]')"), True)
await page.ev("document.getElementById('popup').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'})); T.sleep(200)")
expect("Esc closes", await page.ev("document.getElementById('popup').open"), False)
# Save: Saturday ticked as a weekly rest day is saved
await page.ev("T.click('Month settings'); document.querySelector('#popup input[data-weekday=\"6\"]').click(); T.click('Save', document.getElementById('popup'))")
await page.ev("T.until(() => !document.getElementById('popup').open, 'saved and closed', 6000)")
s = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json()).then((v) => v.settings.day_types['5'])")
expect("5 Sep (Sat) is a rest day", s, "rest")
# Review Focus 2: an open pop-up closes when the address changes
await page.ev("T.click('Month settings'); document.getElementById('step-check').click(); T.sleep(600)")
expect("closed on leaving step 3", await page.ev("document.getElementById('popup').open"), False)
# company settings: same pop-up, over the company
await page.ev(f"location.hash = '#/payroll/{M}/c/' + encodeURIComponent('MAJU JAYA')")
await page.ev("T.until(() => !document.getElementById('company').hidden, 'company'); T.click('Company settings')")
expect("company settings title", "MAJU JAYA" in await page.ev("document.getElementById('popup-title').textContent"), True)
```

- [ ] **Step 2: Run** `sh tools/clickthrough/run.sh popups` → PROBLEM (no `#popup`).
- [ ] **Step 3: Implement** the three functions in `app.js`; `openMonthSettings()` and `openCompanySettings()` build
  the same editor and Save / Cancel and call `openPopup` (icon `calendar-cog`) instead of filling a section; Save
  closes the pop-up on success and shows the error inside the pop-up (a `.banner.error` at the top of `#popup-body`)
  on failure. The seven weekday checkboxes are drawn as toggle pills (`label.wd > input + span`), still
  `input[data-weekday]`. `route()` calls `closePopup()` before drawing.
- [ ] **Step 4: Run** `popups`, `rest_days`, `people_page` → "No problems"; i18n checks.
- [ ] **Step 5: Commit** ("Step 3: Month and Company settings open as a pop-up").

### Task 3: The bell

**Files:**
- Create: `static/bell.js` (loaded after `paycommon.js`), `tools/clickthrough/bell.py`
- Modify: `static/index.html` (bell button and `#bell-list`, `#bell-toast` in the month bar; remove `#mo-info`),
  `static/people.js` (`ppNotes`, `monthNotesText` use replaced), `static/paycommon.js` (`noteLine`), `static/app.css`,
  `tools/clickthrough/check_reading.py` (the note is read from the bell)
- Delete: `tools/clickthrough/closable_notes.py` (its checks move to `bell.py`)

**Interfaces:**
- Consumes: `icon`, `iconButton`.
- Produces: message `{ id: string, icon: string, line: string, detail: string, action?: "payroll-folder", seen: boolean }`;
  `bellAdd(month: string, msg: {icon, line, detail, action?}) -> void` (stores, toasts 4 s, redraws);
  `bellDraw(month: string) -> void`; `noteLine(note: {added, numbered}) -> string` (short: "AMIN added · 1 card",
  "1 new Employee No."; joined with " · ").
- Storage: `bell.<month>` JSON list, newest first, at most 20; if storage throws, the list lives in a module variable
  for this visit.

- [ ] **Step 1: Write the failing click-through** `bell.py` (the made-up note of `closable_notes.py` reused):

```python
await page.ev(f"sessionStorage.setItem('notes.{M}', {NOTE!r}); location.hash = '#/payroll/{M}'")
await page.ev("T.until(() => T.text('#bell-count') === '1', 'one unread', 6000)")
expect("no banner above the list", await page.ev("document.getElementById('mo-info') === null"), True)
expect("toast", "AMIN" in await page.ev("document.getElementById('bell-toast').textContent"), True)
await page.ev("T.click('Messages'); T.until(() => !document.getElementById('bell-list').hidden, 'list')")
expect("short line", await page.ev("document.querySelector('#bell-list .msg-line').textContent"), "AMIN added · 1 card · 1 new Employee No.")
expect("read: count gone", await page.ev("document.getElementById('bell-count').hidden"), True)
# another employee: the message stays in the bell (nothing sits above the list any more)
await page.ev(f"location.hash = '#/payroll/{M}/e/{siti}'; T.sleep(800)")
expect("kept", await page.ev("document.querySelectorAll('#bell-list .msg').length"), 1)
await page.ev("document.querySelector('#bell-list .msg .icon-btn[title=\"Close\"]').click()")
expect("× removes it", await page.ev("document.querySelectorAll('#bell-list .msg').length"), 0)
# Review Focus 3: storage refused
await page.ev("Storage.prototype.setItem = () => { throw new Error('refused'); }")
await page.ev("bellAdd('2026-09', { icon: 'users', line: 'Employee list imported · 3', detail: '' })")
expect("still shown", await page.ev("T.text('#bell-count')"), "1")
```

- [ ] **Step 2: Run** `sh tools/clickthrough/run.sh bell` → PROBLEM.
- [ ] **Step 3: Implement.** `showPeople`/`ppLoad`: each note taken (`takeMonthNotes`, or `added_by_themselves` /
  `numbered` from `/people`) becomes `bellAdd(month, { icon: "file-plus", line: noteLine(n), detail: monthNotesText([n]) })`.
  The Million list import (`mo-million-file` change) adds `{ icon: "users", line: t("Employee list imported") }`.
  The list closes on a click outside it or on Esc. Remove the session-25 code that hid `mo-info` on a new selection.
  `#bell-count` is a badge **beside** the bell button (positioned over its corner), not inside it, so the button's
  text stays "Messages" for `T.click`.
- [ ] **Step 4: Run** `bell`, `check_reading` (`SLOW_FILE=1`), `people_page`, `cross_steps` → "No problems"; i18n checks.
- [ ] **Step 5: Commit** ("Step 3: messages go into a bell").

### Task 4: Export in a pop-up, the Million summary inside it

**Files:**
- Modify: `static/people.js` (`openExport`, `showMonthSummary` → pop-up), `static/paycommon.js` (`showMonthRun` →
  `madeMessage`), `static/index.html` (remove `#mo-export`, `#mo-run-result`), `static/app.css`
- Modify: `tools/clickthrough/export.py`, `tools/clickthrough/people_page.py`

**Interfaces:**
- Consumes: `openPopup`, `closePopup` (Task 2); `bellAdd` (Task 3).
- Produces: `openExport(only?: string) -> void` (pop-up, title "Export <month>", icon `download`);
  `summaryNodes(run) -> Node[]` (one line "3 go in · 1 held", then per company, held people with their reason in a
  fold); `madeMessage(run) -> {icon: "file-spreadsheet", line, detail, action: "payroll-folder"}`
  (line e.g. "Million file · MAJU JAYA · 3 in, 1 held").

- [ ] **Step 1: Update the click-throughs first.** The month bar's button is now **Export** (icon + word, was
  "Export…"): `T.click('Export…')` becomes `T.click('Export')`. In `export.py` every `#mo-export` becomes `#popup`; the What
  choice is two large radio cards (`input[name=ex-what]` kept), companies are chips (`input[data-company]`,
  `input[data-all]` kept). After **Make the file**:

```python
expect("pop-up closed", await page.ev("document.getElementById('popup').open"), False)
await page.ev("T.click('Messages')")
expect("made, in the bell", f"Payroll {M} MAJU JAYA (Million).xls" in await page.ev("T.text('#bell-list .msg')"), True)
expect("Open folder", await page.ev("!!T.button('Open folder', document.getElementById('bell-list'))"), True)
# Review Focus 5: many companies stay inside the screen
await page.ev("T.click('Export'); T.until(() => document.getElementById('popup').open, 'again')")
expect("pop-up never taller than the window", await page.ev("document.getElementById('popup').getBoundingClientRect().bottom <= innerHeight"), True)
expect("its body scrolls", await page.ev("getComputedStyle(document.getElementById('popup-body')).overflowY"), "auto")
```

  and the summary shows inside the pop-up before Make (`#popup .summary` contains "go in").
- [ ] **Step 2: Run** `export` → PROBLEM.
- [ ] **Step 3: Implement.** Payroll table: download, then `closePopup()`. Million file: the summary replaces the
  form's lower part inside the pop-up, with **Back** and **Make the file**; Make → `closePopup()`, `bellAdd(month,
  madeMessage(run))`. The bell message's **Open folder** calls `POST /api/folders/payroll/open` (an error goes to
  `moError`). Remove `mo-run-result` and the session-25 lines that hid it.
- [ ] **Step 4: Run** `export`, `people_page`, `bell` → "No problems"; i18n checks.
- [ ] **Step 5: Commit** ("Step 3: Export opens as a pop-up; the Million file's summary is in it and its result in the bell").

### Task 5: Month bar with icons, the short status line, the list with icons

**Files:**
- Modify: `static/index.html` (month bar), `static/people.js` (`ppDraw`, `ppDrawList`, `statusText`), `static/app.css`
- Modify: `tools/clickthrough/people_page.py`

**Interfaces:**
- Consumes: `iconButton` (Task 1). Produces: nothing new for later tasks.

- [ ] **Step 1: Add to `people_page.py`:**

```python
expect("month bar is icons", await page.ev("[...document.querySelectorAll('.doc-bar .icon-btn')].map((b) => b.title)"),
       ["Month before", "Month after", "Messages", "Month settings", "Import employee list from Million"])
expect("status line", await page.ev("T.text('#mo-total .stat')"), "3 ready | 1 to fix")   # the made-up month's counts
expect("ready shown as a tick", await page.ev("!!document.querySelector('#pp-list .side-item use[href$=\"circle-check\"]')"), True)
expect("word kept as tooltip", await page.ev("document.querySelector('#pp-list .side-item .pill').title"), "Ready")
```

  (Read the made-up month's real counts with `fetch('/api/payroll/2026-09/people')` once and put them in the expected
  string.)
- [ ] **Step 2: Run** `people_page` → PROBLEM.
- [ ] **Step 3: Implement.** `#mo-total` = `.stat` spans with icons (`circle-check` ready, `alert-triangle` to fix)
  and the existing "files need you in step 2 →" link; the "not checked against Million" sentence becomes a warning
  dot on the `users` button with the sentence as its `title`. List pills: icon only, the old word as `title`.
- [ ] **Step 4: Run** `people_page`, `cross_steps`, `employee_page` → "No problems"; i18n checks.
- [ ] **Step 5: Commit** ("Step 3: month bar and list with icons, a short status line").

### Task 6: Employee tabs: the frame, To fix and Cards

**Files:**
- Modify: `static/index.html` (`#employee`: head with `#em-more` (dots menu), `#em-tabs`, one body `#em-body`;
  `#em-needs`, `#em-cards`, `#em-window` become drawn by tab), `static/employee.js` (`emDraw`, `emDrawCards`),
  `static/people.js` (`itemNode` short form, `ppDrawEmployeeNeeds`), `static/app.css`
- Create: `tools/clickthrough/employee_tabs.py`; Modify: `employee_page.py`, `add_card.py`

**Interfaces:**
- Consumes: `iconButton`, `openPopup`.
- Produces: `emPane: "fix" | "cards" | "hours" | "pay"`; `emPickPane(hasItems: boolean) -> string` (to fix when it
  has items, else `recall("em.tab")` if one of cards / hours / pay, else `"pay"`); `emShowPane(name) -> void`
  (flushes waiting typing with `emFlush()` first, remembers the choice in `em.tab` unless it is "fix", redraws);
  `itemNode(item, { short: true })` (icon by kind, title, buttons; the old sentences in a `<details>`).
- Item icons: look `eye`, days `calendar`, column `table`, nocard `id`, held `clock-pause`, settings `calendar-cog`,
  offer `users`, empno `id`.

- [ ] **Step 1: Write the failing click-through** `employee_tabs.py`:

```python
await page.goto(f"{BASE}/#/payroll/{M}/e/{ali}")                 # ALI has something to fix in the made-up month
await page.ev("T.until(() => document.querySelector('#em-tabs [aria-selected=true]'), 'tabs')")
expect("tabs", await page.ev("[...document.querySelectorAll('#em-tabs [role=tab]')].map((b) => b.dataset.pane)"), ["fix", "cards", "hours", "pay"])
expect("opens on To fix", await page.ev("document.querySelector('#em-tabs [aria-selected=true]').dataset.pane"), "fix")
expect("details folded", await page.ev("[...document.querySelectorAll('#em-body .need details')].every((d) => !d.open)"), True)
await page.ev("document.querySelector('#em-tabs [data-pane=cards]').click()")
expect("card actions are icons", await page.ev("[...document.querySelectorAll('#em-body .card-row .icon-btn')].slice(0, 3).map((b) => b.title)"),
       ["Check this card", "Move to", "Take off"])
# an employee with nothing to fix opens on the last tab chosen (cards)
await page.ev(f"location.hash = '#/payroll/{M}/e/{siti}'")
await page.ev("T.until(() => document.getElementById('em-title').textContent.includes('SITI'), 'SITI', 6000)")
expect("remembered tab", await page.ev("document.querySelector('#em-tabs [aria-selected=true]').dataset.pane"), "cards")
await page.ev("T.click('More'); T.until(() => T.button('Remove employee'), 'menu')")
```

- [ ] **Step 2: Run** `employee_tabs` → PROBLEM.
- [ ] **Step 3: Implement.** `ppDrawWalk`: "‹ Previous" and **Next to fix ›** (was "Next needing you ›"; update
  `employee_page.py`). Move to: the `arrows-exchange` button opens a pop-up with today's employee choice and
  **Move**. Take off keeps today's question. **Add a card** and "Hours from" stay under the card rows. `employee_page.py`
  and `add_card.py`: open the Cards tab before looking for `#em-cards`-era buttons (`#em-body`).
- [ ] **Step 4: Run** `employee_tabs`, `employee_page`, `add_card`, `cross_steps`, `yellow_confirm` (`YELLOW_FILE=1`)
  → "No problems"; i18n checks.
- [ ] **Step 5: Commit** ("Step 3: the employee in tabs: To fix and Cards").

### Task 7: Hours tab: the month as a calendar

**Files:**
- Create: `static/hours.js` (loaded after `paycommon.js`); Modify: `static/employee.js` (Hours pane),
  `static/index.html`, `static/app.css`; Modify: `tools/clickthrough/employee_tabs.py`

**Interfaces:**
- Consumes: `emView.result.days` (`{day, type: "work"|"rest"|"holiday", status: "ok"|"unclear"|"conflict"|"missing",
  hours, code, printed, clock}`), `emView.result.values`, `emDayNote(d)`.
- Produces: `hoursCalendar(month: string, days: object[], onPick: (d) => void) -> HTMLElement` (7 columns, Monday
  first, leading blanks; a cell is a button with the day number and `code ?? hours` (or "rest" / "holiday" words);
  class `rest`, `holiday`, `bad` (status not ok, except a missing rest day)); `hoursFigures(values) -> HTMLElement`
  (Days Worked, Hours of Worked, overtime hours = ot_1 + ot_1_5 + ot_2 + ot_3, Public Holiday).

- [ ] **Step 1: Add to `employee_tabs.py`:**

```python
await page.ev("document.querySelector('#em-tabs [data-pane=hours]').click()")
expect("30 days in September", await page.ev("document.querySelectorAll('#em-body .cal .d').length"), 30)
expect("1 Sep 2026 is a Tuesday", await page.ev("document.querySelectorAll('#em-body .cal .blank').length"), 1)
expect("Sundays are rest days", await page.ev("[...document.querySelectorAll('#em-body .cal .d.rest')].map((b) => b.dataset.day)"), ["6", "13", "20", "27"])
await page.ev("document.querySelector('#em-body .cal .d[data-day=\"3\"]').click()")
expect("day note", "3" in await page.ev("document.getElementById('cal-note').textContent"), True)
expect("no day-by-day table left", await page.ev("document.getElementById('em-days') === null"), True)
```

- [ ] **Step 2: Run** → PROBLEM. **Step 3: Implement** (`#cal-note` shows "Day 3 · Working day · written: 9 · <note>").
- [ ] **Step 4: Run** `employee_tabs`, `employee_page` → "No problems"; i18n checks. **Step 5: Commit** ("Step 3: Hours tab with the month as a calendar").

### Task 8: Pay tab: Million's fields in groups and sub-tabs

**Files:**
- Modify: `static/employee.js` (`emDrawWindow` → Pay pane; `emTab` gains `"leave"`), `static/app.css`;
  `tools/clickthrough/employee_tabs.py`, `employee_page.py`

**Interfaces:**
- Consumes: `emRow`, `emFigure`, `emLines`, `emAllowanceTab`, `emBasicPayLine` (unchanged). Keeps every input id
  (`ew-empno`, `ew-name`, `ew-rate`, `ew-basis`, the figure ids) so saving and the old checks still work.
- Produces: the Pay pane: sub-tabs **Basic Pay & Overtime · Allowance & Deduction · Leave**; Basic Pay & Overtime =
  three groups (Days: Working Days, Public Holiday, Days Worked, Hours of Worked; Overtime: the six `OT_ROWS`; Time
  off: Lateness, Early Departure, No Pay Hour, Encashing Leave) and the Basic Rate line with the pay preview; Leave =
  `emLines("leave")`; the "Needs checking" pill is a button to the To fix tab; the issues list and day-by-day table
  leave this pane (they are in To fix and Hours).

- [ ] **Step 1: Add to `employee_tabs.py`** (Review Focus 1):

```python
await page.ev("document.querySelector('#em-tabs [data-pane=pay]').click()")
expect("sub-tabs", await page.ev("T.text('#em-body .pw-tabs .tab')"), "Basic Pay & Overtime | Allowance & Deduction | Leave")
await page.ev("T.set('ew-name', 'ALI TABS'); document.querySelector('#em-tabs [data-pane=cards]').click(); T.sleep(1200)")
after = await page.ev(f"fetch('/api/payroll/{M}/employee/{ali}').then((r) => r.json())")
expect("typed then tab: saved", after["employee"]["name"], "ALI TABS")
```

- [ ] **Step 2: Run** → PROBLEM. **Step 3: Implement.** **Step 4: Run** `employee_tabs`, `employee_page`, `add_card`
  → "No problems"; pytest; i18n checks. **Step 5: Commit** ("Step 3: Pay tab with Million's fields in groups").

### Task 9: The company in tabs

**Files:**
- Modify: `static/index.html` (`#company`: head with `calendar-cog` and `download` icon buttons, `#co-tabs`,
  `#co-body`; `#co-million-open` goes), `static/people.js` (`drawCompany`, `drawMillionNew`), `static/paytable.js`
  (draws into the Pay preview pane; its paragraph becomes an `info-circle` tooltip), `static/app.css`
- Create: `tools/clickthrough/company_tabs.py`; Modify: `cross_steps.py` (`#co-items` → `#co-body`)

**Interfaces:**
- Consumes: `iconButton`, `openPopup`, `openExport(only)`, `itemNode(item, {short: true})`.
- Produces: `coPane: "fix" | "pay" | "new"`; New in Million tab only when `million_new` is not empty.

- [ ] **Step 1: Write the failing click-through** `company_tabs.py`:

```python
await page.goto(f"{BASE}/#/payroll/{M}/c/" + "A%20%26%20B%20(M)")
await page.ev("T.until(() => document.querySelector('#co-tabs [role=tab]'), 'company tabs', 6000)")
expect("title", "A & B (M)" in await page.ev("document.getElementById('co-title').textContent"), True)
await page.ev("T.click('Export'); T.until(() => document.getElementById('popup').open, 'export')")
expect("only A & B ticked", await page.ev("[...document.querySelectorAll('#popup input[data-company]:checked')].map((i) => i.dataset.company)"), ["A & B (M)"])
await page.ev("closePopup(); document.querySelector('#co-tabs [data-pane=pay]').click()")
expect("pay table", await page.ev("!!document.querySelector('#co-body table')"), True)
expect("legend is a tooltip", await page.ev("!!document.querySelector('#co-body .icon-btn[title*=\"Million\"]')"), True)
```

- [ ] **Step 2: Run** → PROBLEM. **Step 3: Implement.** **Step 4: Run** `company_tabs`, `cross_steps`, `export`,
  `people_page` → "No problems"; i18n checks. **Step 5: Commit** ("Step 3: the company in tabs").

### Task 10: Words, guides, notes and the full run

**Files:** `static/i18n.js`, `GUIDE - Table Reader to Million.html`, `PANDUAN - Table Reader ke Million.html`
(section C: the bell, the tabs, the pop-ups), `packaging/guide/guide.html` (step 3 paragraph), `PROGRESS.md`,
`NEXT-SESSION.md`

- [ ] **Step 1:** Go through every text step 3 draws (`grep -n "t(\"" static/people.js static/employee.js static/settings.js static/bell.js static/hours.js`)
  and shorten any button or tab name over 3 words and any line over one sentence (into a fold or tooltip). Remove
  Malay entries of texts no longer used only if `check_i18n.py` lists them as unused; otherwise leave them.
- [ ] **Step 2: Run everything:** pytest; both i18n checks; every scenario in `tools/clickthrough/` (`check_reading`
  with `SLOW_FILE=1`, `yellow_confirm` with `YELLOW_FILE=1`) → "No problems".
- [ ] **Step 3:** Notes: PROGRESS.md session entry, NEXT-SESSION.md state box (not merged, not rebuilt).
- [ ] **Step 4: Commit** ("Step 3 redesign: words, guides and notes"). Then stop: merging, rebuilding (the rebuilt
  exe may be blocked by Windows' Application Control, see PROGRESS.md 25) and pushing wait for the user.
