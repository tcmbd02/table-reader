# Three-step workflow: design

Date: 2026-10-14. Status: written for the user's review; nothing is built yet.
All names and figures in this document are made up.

## 1. Purpose

The app has grown to seven screens: the start page, a file's page, the month overview, a company screen, the Look
panel, the Layout page and the employee view. Staff move between them with "← back" links and new browser tabs, and
it is not clear which step of the work they are in.

The user's rule for this change: **the app has one workflow of three pages — Upload → Check reading → Employee
payroll — and every page has buttons leading to the others.**

This design rearranges the screens into those three pages. It does not change how days and hours are worked out,
what the Million file contains, or how files, corrections and the payroll are stored.

## 2. Decisions taken with the user

| Question | Decision |
|---|---|
| The three pages | 1 Upload, 2 Check reading, 3 Payroll |
| Shape of step 3 | A list of the month's employees on the left (grouped by company), the chosen employee on the right |
| Shape of step 2 | A list of files on the left, the chosen file (picture beside the table) on the right |
| Problems that belong to a file (whose card, which month, unknown card layout, set aside) | On that file in step 2, in a "This file needs you" box above its table |
| Approach | Rebuild the screens as three pages on the existing server; the server gains two read requests (approach A) |
| Opening things | In the same tab, never a new tab; each step remembers what was open |

Rules that stay as they are:

- **Never guess.** Unclear cells stay blank and highlighted; the payroll reports what it cannot work out and marks the
  employee as needing checking. `result.json` is never modified; corrections go to `edits.json`.
- OCR only through the user's own signed-in Claude Code; no settings screens beyond those that exist, no accounts.
- Plain-language messages; every new text in English and Bahasa Melayu (`static/i18n.js`). The Edit Payroll window's
  labels stay English.
- Personal data stays on the PC.

## 3. Moving between the steps

### 3.1 The top bar

The top bar of every page has three step buttons in place of today's "Payroll" link:

`[1 Upload] [2 Check reading · 12] [3 Payroll · 5]`

- The step being shown is highlighted.
- "Check reading" shows the number of yellow cells left in the files of the chosen month (or of all files when step 2
  shows all months). It comes from `GET /api/jobs` (`cells_to_check`), which the page already polls.
- "Payroll" shows how many things need the user in step 3. It is shown once the month has been loaded in this visit
  (by step 2 or 3), and left without a number before that, because loading a month joins newly read files to it.
- Claude's sign-in box, Bahasa Melayu and Quit Table Reader stay where they are.

A step button opens that step where the user last was (the file or employee last opened in this browser tab), or
the step's first screen when nothing was opened yet. What was last open is kept in `sessionStorage`, read and written
inside `try/catch`, so a private window simply starts afresh.

### 3.2 Same tab

Every button opens its target in the same tab, including the ones that open a new tab today ("Open employee", "Open
the card", "Add employee"). The browser's Back button works, because each place has its own address (3.3).

### 3.3 Addresses

| Address | Shows |
|---|---|
| `#/` | 1 Upload |
| `#/check` | 2 Check reading, the last file opened, or the first file needing the user |
| `#/check/<file>` | 2 Check reading, that file |
| `#/check/<file>/columns/<page>` (optionally `/h/<hours column>`) | 2, that file with its column choice open (today's Layout page) |
| `#/payroll` | 3 Payroll, the default month (as today) |
| `#/payroll/<month>` | 3, the last employee opened, or the first employee needing the user |
| `#/payroll/<month>/e/<employee>` | 3, that employee |
| `#/payroll/<month>/e/<employee>/look` | 3, that employee with the Look panel open |
| `#/payroll/<month>/c/<company>` | 3, that company's panel |

Old addresses keep working by opening the matching new place:

| Old | Opens |
|---|---|
| `#/doc/<file>` | `#/check/<file>` |
| `#/payroll/<month>/look/<employee>` | `#/payroll/<month>/e/<employee>/look` |
| `#/payroll/<month>/layout/<file>/<page>[/h/<col>]` | `#/check/<file>/columns/<page>[/h/<col>]` |
| `#/payroll/<month>/old[/e/<employee>]` | as today: the month or the employee |

### 3.4 The working month

Steps 2 and 3 share one month (the "working month"). Step 3's ‹ › and step 2's Month filter change the same value,
kept in `sessionStorage` (inside `try/catch`); it starts as today's default payroll month. Step 2's Month filter also
has **All months**: then the list shows every file with its yellow cells and reading state, but no payroll problems
(working those out opens a month's payroll, and old months must not be opened in the background).

### 3.5 Buttons between the steps

| Where | Button | Goes to |
|---|---|---|
| 1 Upload | **Check them →** | 2, the first of the files just added (or `#/check` when none were added in this visit) |
| 2, a file | **Next file with yellow cells →** | 2, the next file in the list (in list order, wrapping) with yellow cells or a problem |
| 2, a file on employees | **See {name} in payroll →** (one per employee the file's cards are on) | 3, that employee |
| 2, bottom | **Go to payroll for {month} →** | 3, the file's month, or the working month |
| 3, top line | **{n} files need you in step 2 →** | 2, the first file with a problem |
| 3, an employee's card | **Check this card →** | 2, that file |
| 3, an employee | **‹ Previous** / **Next needing you ›** | 3, the employee before / the next one needing the user (list order) |

## 4. The pages

### 4.1 Step 1: Upload

- The drop box, its "click to choose files", and the line about the Inbox and Tables folders with their two buttons,
  as today. Upload messages (errors, "already read", ...) as today.
- **Just added:** the files dropped in this visit (their ids kept in `sessionStorage`) and every file still waiting or
  being read (also from the Inbox folder). Each row: name, company (with **Set company** when there is none, the same
  company box as today), progress ("Reading page 2 of 5…"), **Cancel** while reading.
- **Check them →** under the list. When nothing is being read the list header says "Everything is read".
- The full Recent files list is no longer here; it becomes step 2's list.

### 4.2 Step 2: Check reading

**Left: the list of files**, newest first.

- Filters above it: **Company** (the existing chooser, moved here from the start page, still remembered in
  `localStorage`) and **Month** (3.4).
- A row per file: name, company, and one state: "Reading page 2 of 5…" / "Stopped" / "Cancelled" / "{n} yellow" /
  "! Needs you" / "✓". A file that is both yellow and needs the user shows both. A failed file shows its message.
- The list refreshes every 4 seconds while any file is waiting or being read (as the start page does today).

**Right: the chosen file**, top to bottom:

1. The file's name; its company (click to change; the existing company box and its "other files that start with it
   go under it too"); **Cancel reading** / **Continue reading** while relevant; **Download CSV** (with today's warning
   about highlighted cells).
2. **This file needs you** (only when there is something), one entry per problem, with today's buttons and wording:
   - *No company yet*: the company box, open.
   - *Whose card is this?* (today's "unplaced"): a button per employee of the company, **New employee**, **Not a time
     card** (for a whole file), as today.
   - *Which month is this for?* (today's "month"): **It is for {month}**, **Not a time card**.
   - *A card layout Table Reader does not know* / *the days cannot be worked out with the saved card layout* (today's
     "layout"): **Check the columns** opens today's Layout page as a section right under the box (address
     `#/check/<file>/columns/<page>`), with **Ask Claude**, **It is right as it is**, **Save**; closing it or saving
     returns to the file. **It is right as it is** also stays on the entry itself, as today.
   - *Set aside, or read as another month and on nobody there* (today's folded "other files"): "It is for {month}"
     takes it into the working month.
3. Claude's notes, then each page: the picture beside the table with its yellow cells, exactly as today, with **Go to
   next cell to check**.
4. At the bottom: **Next file with yellow cells →**, **See {name} in payroll →** per employee, **Go to payroll for
   {month} →**.

When the list is empty: "Nothing here yet. Add files in step 1." with a button to step 1.

### 4.3 Step 3: Payroll

**Top bar**: "Payroll {month}" with ‹ ›; **Month settings**; **Import employee list from Million**; **Download payroll
CSV**; **Make the month's Million file (all companies)** with its summary first, as today. Under it one line: "{a} of
{b} employees ready." plus, when there are any, "**{n} files need you in step 2 →**", and today's notes on files that
joined by themselves and new Employee Nos.

**Left: the list of people**

- A search box (filters by name or Employee No.).
- Each company as a heading with its status ("Needs you: 2 things", "Ready", "Ready, 1 waiting for Million", "own
  settings"), its employees under it, sorted as the overview sorts companies today (those needing the user first).
  Each employee: Employee No. and name, and "!" when something needs them or "✓" when ready. Employees with no
  company sit under "(no company)".
- The Company chooser of step 2 filters this list too.

**Right: what was clicked**

- **An employee**:
  1. *What needs them*, with today's wording and buttons: Employee No. to fix, **Use {no}** (Million has a number for
     this name), not ready for the Million file (with the reasons), no time card yet, Table Reader cannot work out the
     days.
  2. "{n} lines of the time cards to check." with **Look**: today's Look panel opens in the right side in place of the
     employee's details (address `.../e/<employee>/look`), with "← Back to {name}"; its Accept returns to the
     employee when no card is left.
  3. Today's employee view: the cards (each with move to another employee, take off, **Check this card →**), the Edit
     Payroll window, the Hours column choice, Remove.
  4. **‹ Previous** / **Next needing you ›**.
- **A company heading**: Company settings; the "month's default changed after this company got its own settings"
  entry with **Open settings** / **It is right**; the Pay preview table with **Download the pay table (CSV)**; **Add
  employee** (opens the new employee in the right side, same tab); New in Million with Copy / Copy all; that company's
  **Download payroll CSV**; and, when the company has files that need the user, "{n} files need you in step 2 →".
- **Nothing chosen**: the first employee needing the user, or the first employee, or "No employees for this month yet.
  Add time cards in step 1." with a button to step 1.

## 5. Server

The calculation, the plan files and the Million file are unchanged. Two read requests are added, built from the same
`month_state` the overview and the company screen use today, so their figures cannot differ from today's.

### 5.1 `GET /api/payroll/{month}/people`

Everything step 3's list and panels need for the month, in one request:

```json
{
  "month": "2026-09",
  "companies": [
    {"company": "MAJU JAYA", "status": "needs", "needs": 2, "waiting": 0, "own": false,
     "items": [{"kind": "settings", "company": "MAJU JAYA"}],
     "files_needing": 1,
     "employees": [{"id": "e1", "emp_no": "MAJUJAY001", "name": "ALI", "status": "needs",
                    "items": [{"kind": "empno", "employee": "e1", "why": "empty"}]}],
     "million_new": [], "settings": {}}
  ],
  "files_needing": 3,
  "ready_employees": 8, "employees": 84, "ready_companies": 1,
  "checked_with_million": true, "settings": {},
  "added_by_themselves": null, "numbered": 0
}
```

- A company's `items` here are only its company items (`settings`); each employee carries its own items (those with
  its `employee` id). File items (`unplaced`, `month`, `layout`) are not in step 3: they are counted in
  `files_needing` (per company and for the month) and listed by 5.2.
- A company's `status` and `needs` count only its employee and company items, so a company whose only problem is a
  file shows its employees as ready and points to step 2.
- Files with no company count in the month's `files_needing`.
- Each `look` item keeps its `places` and its `cards` as `[{"id", "name"}]` (as the company request gives today).

### 5.2 `GET /api/payroll/{month}/files`

The problems of the files, for step 2:

```json
{
  "month": "2026-09",
  "files": {
    "<file id>": [{"kind": "unplaced", "ref": "...", "name": "...", "readable": true},
                  {"kind": "layout", "page": 1, "columns": ["..."], "confirmed": false, "hours_column": null}],
    "<file id 2>": [{"kind": "company"}],
    "<file id 3>": [{"kind": "other", "month": "none"}]
  },
  "employees": {"<file id>": [{"id": "e1", "name": "ALI"}]},
  "choices": {"MAJU JAYA": [{"id": "e1", "name": "ALI", "emp_no": "MAJUJAY001"}]}
}
```

- `files`: today's `file_items` (unplaced, month), `layout_items` and `other_files`, regrouped by file instead of by
  company; plus `{"kind": "company"}` for a finished file with no company.
- `employees`: for each file, the employees of the month its cards are on (for "See {name} in payroll →").
- `choices`: per company, the employees a "whose card is this?" entry offers (today the company screen uses its own
  employee list for those buttons).

### 5.3 What goes

`GET /api/payroll/{month}/companies` and `GET /api/payroll/{month}/company` are removed once nothing uses them; their
tests are moved to the two new requests. `GET /api/payroll/{month}/look` and every request that changes something
(place, file-month, layouts, company, employee, lists, settings, run, ...) stay as they are.

## 6. Front end

- `static/index.html`: three `<main>` sections (`upload`, `check`, `payroll`) in place of `home`, `doc`, `month`,
  `company`, `look`, `layout`, `employee`. The Look and Layout panels and the employee view become parts inside them.
- Scripts are split by page, each small: `steps.js` (top bar, addresses, remembered places, working month),
  `upload.js`, `check.js` (list, file, its problems; the file page code moves here from `app.js`), `columns.js` (today's
  `layout.js`), `people.js` (step 3 list, top bar, company panel; replaces `companies.js`), `employee.js`, `look.js`,
  `paytable.js`, `settings.js`, `paycommon.js` (kept). `app.js` keeps the shared helpers (`el`, `api`, sign-in, quit,
  language).
- Removed: the Recent files list of the start page, the month overview, the company screen, the separate Look and
  Layout pages, every "← back" link, `openInNewTab`.
- Narrow windows: the two columns of steps 2 and 3 stack (list above, chosen item below).

## 7. Testing

- Server tests first for `people` and `files`: the same figures and items as the company request gives today, items
  split as 5.1 says, files with no company, other files, `files_needing` counts, a plan that cannot be validated.
- Scripted click-throughs in headless Edge on made-up data (MAJU JAYA: ALI, SITI on day cards, ZUL on a confirmed
  card layout, AMIN on an August card): every row of the table in 3.5, every old address in 3.3, the Look panel in
  step 3, the column choice in step 2, a file with no company, Back button behaviour, a fresh tab.
- Real September data, on copies, counts only (scripts deleted afterwards): every employee's figures and the month's
  Million file identical before and after (84 employees; 8 ready, 76 held), and every file problem the company
  screens show today appears in step 2 (same count per kind).
- `tools/check_i18n.py` and `tools/check_patterns.py`: no text without Malay.
- One fresh reviewer for the whole branch.
- Guides: `GUIDE - Table Reader to Million.html`, `PANDUAN - Table Reader ke Million.html` and
  `packaging/guide/guide.html` rewritten for the three steps (the PDF and its pictures only with the user's OK).

## 8. Order of work

On branch `three-steps` from `pdf-text`:

1. The two server requests, with tests.
2. Top bar, addresses (with the old ones), same-tab opening, remembered places, working month; the Upload page.
3. Step 2: list, file, "This file needs you", the column choice in place.
4. Step 3: list, employee panel with Look in place, company panel, top bar.
5. Old screens and the two old requests removed; guides; real-data comparison; review and fixes.

Merging, rebuilding the app, pushing and the `download` branch each wait for the user's OK.

## 9. Known effects

- A company's status in step 3 no longer counts its file problems (they are in step 2). The month's Million file is
  unaffected: a card on nobody was never in it.
- The start page no longer shows every file; files are found in step 2.
- Opening step 2 for a month opens that month's payroll (as opening Payroll does today), so newly read files of the
  month join it then. With "All months" nothing is opened.
