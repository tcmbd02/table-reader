# Company-first payroll screens: design

Date: 2026-10-12. Status: written for the user's review; nothing is built yet.
All names and figures in this document are made up.

## 1. Purpose

Table Reader's goal is: time cards go in, a Million Payroll import file comes out, with as little clicking,
scrolling and typing as possible, for about 40 client companies and around 84 employees a month.

Today the Payroll page is one long page. Every employee is a card that carries a tick list of all the month's files,
so matching files to employees means scrolling through about 100 files and 84 employees at once. The page also holds
the calendar, the employee list, the results and the pay preview together, and has collected many bulk buttons.

This design reorganises the payroll part of the app around the company. It changes screens and navigation. It does
not change how days and hours are calculated or what the Million file contains.

## 2. Decisions taken with the user

| Question | Decision |
|---|---|
| How a month is worked | One company at a time |
| How much is reviewed | Only the problems; everything else is done without opening it |
| Yellow cells that affect pay | One look per employee: all of an employee's yellow cells in one panel beside the card picture, one button accepts them after a look; incomplete cells must be typed |
| Million file | One file at month end; finishing a company only marks it Ready |
| New employees | A "New in Million" list per company now; whether Million can import new employees from a file is a separate, later investigation |
| Calendar and hours | One default per month; a company can have its own where it differs |
| Approach | New company-first screens on the existing calculation and storage (approach A) |

Rules that stay as they are:

- **Never guess.** Nothing uncertain reaches the payroll until a person has had it in front of them. Claude's reading
  (`result.json`) is never modified; what the user accepts or corrects is saved as a correction (`edits.json`).
- OCR only through the user's own signed-in Claude Code. No settings screens beyond what is described here, no accounts.
- Plain-language messages that say what happened and what to do next. English and Bahasa Melayu.
- Personal data stays on the PC.

## 3. Screens

### 3.1 Start page

Unchanged: drop files or use the Inbox folder; recent files. The top bar keeps one link, **Payroll**.

### 3.2 Month overview (new; the first payroll screen)

```
Payroll  September 2026  [< month >]   [Month settings]   [Import Million's list]   [Make the month's Million file]

 Company          Employees   Status
 BINA KUAT            3       Needs you: 2 things
 ACME                 9       Needs you: 5 things
 (no company)         2 files Needs you: choose a company
 MAJU JAYA            6       Ready
 TEGUH                4       Ready, 1 waiting for Million        own settings
 SURIA                0       No files yet

 2 of 5 companies ready - 9 employees would be in the file now
```

- One row per company that has files or employees in the month, plus companies known from earlier months with nothing
  yet ("No files yet").
- Order: companies that need the user first, then Ready, then No files yet; alphabetical inside each group.
- Files with no company are one row, "(no company)". Opening it lists those files with a company chooser for each.
- A company with its own calendar or hours is marked "own settings".
- **Month settings** opens the month's default calendar, normal hours and break (what "1. Month and days" is today).
- **Import Million's list** is here because the list covers every company.
- The last line says how many companies are ready and how many employees the file would hold now.

Company status, exactly one of:

| Status | Meaning |
|---|---|
| No files yet | No finished file and no employee for this company in the month |
| Needs you: n things | n items in the company's "Needs you" list, not counting "New in Million" |
| Ready, n waiting for Million | No items left except n employees Million does not have yet |
| Ready | No items at all |

### 3.3 Company screen (new)

```
< All companies     BINA KUAT - September 2026            Needs you: 2 things

 NEEDS YOU
 1. ALI: 4 times to look at on his card                         [Look]
 2. A card with no name on it: whose is it?        [ALI] [SITI] [ZUL] [New employee]

 EMPLOYEES                          Days  OT 1.5  Rest day  Status
 BINAKUA001  ALI                     24    12.0      1      Waiting for item 1
 BINAKUA002  SITI                    26     0.0      0      Ready
 BINAKUA003  ZUL                     25     6.5      0      Ready

 [Employees] [Pay preview]      [Company settings]      [New in Million: 1 employee]
```

- "Needs you" is the work. When it is empty the company's status changes by itself; there is no "mark as done".
- The employee table is for a glance: Employee No., name, the main figures, a status. No file lists.
- Clicking an employee opens the employee detail view: today's Results window (every figure, overrides, allowances and
  deductions, the message) plus, moved here from the main screen: changing the Employee No. or name, the list of that
  employee's cards with "move to another employee" and "take off", the hours-column choice, and "Remove employee".
- **Pay preview** is a tab of this screen showing today's pay table for this company only.
- **Add employee** (by hand) is a small link under the table; it is the exception, not the main route.

### 3.4 What is removed or moved

- Removed: the tick list of all files under every employee; "Add employees from files" (it already happens when the
  month is opened); the bulk buttons "Use all suggested Employee Nos." and "Give employees a new one"; the per-company
  "Download Million file (.xls)" on the main screen.
- Moved into the employee detail view: see 3.3.
- Kept: the start page, the document page, the payroll CSV download (on the company screen and the month overview).

## 4. "Needs you" items

An item appears only when the app cannot go on without a person. Each is one line with the button that fixes it.

| Item | When it appears | How it is cleared |
|---|---|---|
| Times to look at | The employee has yellow cells in cells the calculation reads | **Look** opens the one-look panel (section 5) |
| Cells to type | A cell the calculation reads is blank-and-yellow or has a `?` in it | The same panel; these boxes must be typed |
| Whose card is this? | A card, page or grid row could not be matched to one employee of the company | Click the employee, or **New employee** |
| Which month? | A file of this company has no month, or two different months | Pick the month, or **Not a time card** (it is then never asked again) |
| Days that don't add up | A day is missing; a day is on two cards with different hours; the card marks a public holiday where the calendar has a working day; a printed total does not match | Opens the one-look panel at that day; fix the cell, or change the calendar |
| Can't work out the days | No column the calculation recognises | Choose the hours column, or type the figures in the employee detail view |
| Employee No. | Two employees share a number; Million has another name for the number; Million's list offers a number (one click to use it) | Type or accept the right number |
| New in Million | The employee's number is not in Million's imported list | Section 7 |

"Times to look at" and "Cells to type" for one employee are one item (one line, one panel).

Not items: yellow cells in cells the calculation does not read (signatures, remarks); employees whose number came
from an earlier month or from Million's list on a whole-name match.

**Cells the calculation reads**, per employee: the date column, the chosen or automatic hours column, the IN/OUT
columns, the day columns of a month grid, the columns of a clock report that are added up, the printed totals that
are checked, and the name cell of a grid row. This is taken from the calculation itself, not from a separate list, so
the two cannot drift apart.

## 5. The one-look panel

```
ALI - BINA KUAT - September 2026                     card 1 of 2   [< >]

 +---------------------------+    Day   IN       OUT      why yellow
 |                           |     3   [07:22]  [17:05]   digits uncertain
 |   picture of the card,    |     9   [07:58]  [18:3 ]   last digit faded   <- must be typed
 |   the row being checked   |    14   [08:01]  [17:00]   overwritten
 |   is highlighted          |    21   [    ]   [17:10]   could not read     <- must be typed
 +---------------------------+
                                  2 cells still need typing     [Accept all 6]
```

- One panel per employee, covering all of that employee's cards, one card at a time.
- Left: the card's picture. Right: only the rows that have a yellow cell the calculation reads, with every such cell of
  the row as a box. Clicking a row scrolls the picture to it.
- A complete reading is prefilled (a `?` at the start or end dropped, as on the document page). An incomplete one
  (blank, or a `?` inside) is shown as it is and marked "must be typed".
- **Accept all** is disabled while a "must be typed" box is unchanged. A box the user clears counts as typed: the cell
  is accepted as empty.
- **Accept all** saves every box shown on that card as a correction on the document, exactly as pressing Enter in each
  cell does today. Each such correction is marked as accepted through the panel (a `via: "look"` field on the
  correction), so it can be told apart from a typed one later. Claude's reading is not changed.
- After accepting, the panel moves to the employee's next card with yellow cells, and closes after the last.
- The document page stays as it is, for looking at a whole table.

## 6. Company settings and storage

### 6.1 Settings

The month keeps one default: calendar (working / rest / public holiday per day), normal hours per day, break.

```
BINA KUAT - settings for September 2026

 ( ) Same as the month's default
 (o) This company is different:
       Normal hours per day   [ 9 ]      Break [ 1 ] hour
       Calendar: click a day to change it

 [x] Use the same settings for this company next month
```

- A company either follows the default completely or has its own complete set (hours, break, calendar). Its own set
  starts as a copy of the default.
- When the default changes later, companies following it change with it; a company with its own set does not, and its
  settings screen says "The month's default was changed after this; check the calendar."
- With "next month" ticked, the next month's plan starts this company with: the same normal hours and break, and a
  calendar where a weekday is a rest day if every one of its days was a rest day this month. Public holidays are never
  carried over; they are taken from the new month's default.

### 6.2 Storage

- Still one JSON file per month in `Documents\Table Reader\payroll`, same format. Existing months open unchanged;
  nothing is converted.
- One addition to the month file: `companies`, `{company name: {normal_hours, break_hours, day_types, keep}}`, holding
  only companies with their own settings.
- One addition to a correction in `edits.json`: the optional `via` field (section 5).
- `result.json` is never modified.

### 6.3 Calculation

The calculation code is unchanged. When an employee is worked out, it is given the settings of the employee's company
(own set, else the month's default). An employee with no company uses the default.

### 6.4 Million file

Unchanged. A company with its own calendar gets its own Working Days figure, because that figure comes from the
calendar. The open question with HR (should Working Days sent to Million include the public holiday?) applies to
every company equally and is not settled here.

## 7. New in Million

```
BINA KUAT - 1 employee Million does not have yet

 Employee No.   Name
 BINAKUA003     ZUL                                   [Copy]            [Copy all]

 Create them in Million with exactly these numbers, then export Million's
 employee list and import it on the month page.
```

- Lists the company's employees whose Employee No. is not in Million's imported list.
- Only these employees are held back from the month file; the rest of the company goes in.
- When an imported list contains them, they leave this list and join the file by themselves.
- If no list from Million has been imported at all, nobody is held back for this reason (as today), and the month
  overview says that numbers are not being checked against Million.

## 8. The month file

One button on the month overview. Before the file is made, a summary is shown: companies and employees going in, and
who is held back, grouped by company, each with its reason. The file, its checks and its place on disk are as today.
Making it again after fixing things makes the whole file again.

## 9. How it is built

### 9.1 Server

- `payroll.py`: a function that turns the existing per-employee issues into "Needs you" items per company (item kind,
  employee, text, what the button does), the list of cells the calculation reads per employee, and per-company
  settings resolved against the month default. No change to the arithmetic.
- `app.py`: two read endpoints (month overview; one company with its items, employees and figures) and the actions the
  items need (place a card, set a file's month or "not a time card", accept a panel's cells, save company settings).
  Existing endpoints stay until stage 4.
- Everything that changes a plan keeps going through `validate_plan` and the existing lock.

### 9.2 Pages

- `static/payroll.js` is replaced by smaller files: month overview, company screen, one-look panel, employee detail,
  company settings. Plain HTML/JS/CSS as now, no build step.
- Every new text gets a Malay entry; the translation checks stay green.

### 9.3 Stages

Each stage is usable and can be shipped by itself.

1. Month overview and company screen with the "Needs you" list. Items that need the panel link to the document page
   for now.
2. One-look panel.
3. Company settings.
4. "New in Million" list; the summary before the month file. The old Payroll page is removed at the end of this stage.

Until the end of stage 4 the old Payroll page stays reachable through a link ("Old payroll page"), so nothing the user
relies on disappears early.

## 10. Errors

- An action that cannot be done says why and what to do (for example "This card already belongs to SITI. Take it off
  her first."), using the existing message style.
- If a month's plan cannot be saved as it is (old data), the overview still opens and shows what blocks it, as the
  Payroll page does today.
- A file still being read is shown on the company screen as "being read" and is not an item.

## 11. Testing

- Unit tests on made-up cards for every item kind: it appears when it should and disappears when fixed.
- Unit tests for company settings: default followed, own set used, default changed afterwards, carry-over to the next
  month.
- A comparison run on the real September payroll, in memory and printing counts only: every employee's calculated
  figures with the new code equal today's. The redesign must not change one figure.
- Each stage is clicked through in a browser on made-up data before it is called done.
- Translation checks and the real-name scan before every commit, as now.

## 12. Not in this design

- Phase C (Claude names columns Table Reader does not recognise).
- The open-source OCR track (`PLAN-OCR-ENGINE.md`).
- Reading the files of companies E to Z.
- Whether Million Payroll can import new employees from a file (a separate investigation after stage 4).
- The open HR questions on Working Days and the daily overtime rule.
