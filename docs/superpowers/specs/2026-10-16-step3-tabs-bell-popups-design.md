# Step 3 Payroll: tabs, a message bell and pop-ups: design

Date: 2026-10-16. Status: written for the user's review; nothing is built yet. All names and figures in this document
are made up.

## 1. Purpose

Staff feedback on step 3 (session 25): the screens are too wordy, and one long page has to be scrolled. They prefer
icons and features, and **one thing at a time with little scrolling**. Two things made it worse: messages ("Million file
made…", "Added by themselves…") stayed at the top while other companies were edited (fixed in session 25 with a ×),
and Month settings / Export open inside the page and push the list down.

The user chose mock-up **A** (session 25): the employee in tabs, messages in a bell, settings and export as pop-ups.
This design changes how step 3 looks and is used. It does not change how days, hours and pay are worked out, what
the Million file holds, or how anything is stored. Steps 1 and 2 are not changed.

## 2. Decisions taken with the user

| Question | Decision |
|---|---|
| Shape | A: month bar with icons; list on the left; the employee (or company) on the right in tabs |
| Messages | Go into a bell on the month bar (number of unread), not banners above the list |
| Month settings, Company settings, Export | Open as pop-ups over the page, not inside it |
| Employee tabs | To fix · Cards · Hours · Pay |
| Hours | A month calendar instead of the day-by-day table |
| Pay | Million's Edit Payroll fields (English labels, as in Million) in small groups, with sub-tabs |

Decisions taken here (the user can overrule them at review):
- **Errors stay a red line under the month bar.** The bell is for news, not for something that went wrong now.
- **The company panel gets the same treatment** (tabs, pop-ups, icons), so step 3 feels like one screen.
- **The calendar shows each day's hours, not its overtime.** Overtime per day is not something the calculation hands
  to the page today; the month's overtime totals are shown above the calendar. (The mock-up's "+2" is dropped.)
- **No new library and nothing from the internet at run time.** The icons are copied into the app once.

## 3. The screen

### 3.1 Month bar

`‹  September 2026  ›` then icon buttons, each with a tooltip and a screen-reader label in the chosen language:

| Icon (Tabler name) | Tooltip | Does |
|---|---|---|
| `bell` + number | Messages | Opens the bell list (3.2) |
| `calendar-cog` | Month settings | Month settings pop-up (3.5) |
| `users` | Import employee list from Million | Picks Million's `rptempepmlist.xls`, as today |
| `download` + "Export" (the one blue button) | Export | Export pop-up (3.5) |

Under it, one short line with icons: `✓ 40 ready · ⚠ 5 to fix · 3 files need you in step 2 →` (the last part only when
there are such files; it is the existing link). The sentence "The Employee Nos. are not being checked against
Million…" becomes the `users` icon with a warning dot and that sentence as its tooltip.

### 3.2 The bell

- A message is: an icon, one short line, optional buttons, and a ×. Newest first. The number on the bell counts the
  messages not seen yet; opening the list marks them seen. **Clear all** empties the list.
- Messages kept: what opening the month did by itself (files added or joined, files left out and why, new Employee
  Nos.), "Million file made" (file names, how many in, how many held, button **Open folder**), "Employee list imported"
  (how many employees). The long sentences of today become the message's detail, shown when the message is opened
  (a fold); the line itself is short ("AMIN added · 1 card", "Million file · MAJU JAYA · 3 in, 1 held").
- Kept in this browser tab for the month (sessionStorage `bell.<month>`, at most 20), like today's month notes.
- A new message also shows for 4 seconds as a small toast under the bell (one line, `aria-live`), so it is not missed.
- **Open folder** opens the payroll folder in Explorer (the server learns the folder name `payroll`, like `inbox` and
  `tables` today).
- The banners `mo-info` and `mo-run-result` go away (session 25's × fix is replaced by the bell).

### 3.3 The list (left)

As today (search, companies with their employees), with icons instead of words: `alert-triangle` (needs you),
`circle-check` (ready), `clock-pause` (waiting for Million); the company line shows its count of things to fix as a
small number. The words stay as tooltips.

### 3.4 The employee (right)

Head: name, Employee No., "Saved" state, a `dots` menu with **Remove employee**. Then four tabs:

1. **To fix (n)**: one row per item: icon by kind, a short title, its buttons (the same actions as today: Look, Check
   this card, Use <no>, Open settings, It is right…). The full sentences of today are the row's detail, behind a
   small `chevron-down` fold. With nothing to fix: "Nothing to fix" with a check.
2. **Cards (n)**: one row per card: picture icon, the card's name, the days it covers when known; icon buttons `eye`
   (Check this card), `arrows-exchange` (Move to: a small pop-over with the employee choice and Move), `x` (Take off,
   with today's question). Under the rows: **Add a card** (today's choice) and "Hours from: <column>" (today's
   Hours column choice, smaller). A card read with a saved layout keeps its one-line note.
3. **Hours**: four figures (Days worked, Hours of worked, overtime hours, public holidays) from the employee's
   figures, then the month as a calendar, Monday first: each day shows its hours or its mark (rest, holiday, PH, MC…);
   colours: rest grey, public holiday yellow, no entry / unclear / written twice red. Clicking a day shows under the
   calendar what today's day-by-day table says for it (written on the card, the note).
4. **Pay**: Million's Edit Payroll window, labels in English as in Million, in sub-tabs **Basic Pay & Overtime ·
   Allowance & Deduction · Leave**. Basic Pay & Overtime shows three small groups (Days, Overtime, Time off) and the
   Basic Rate line with the pay preview. The "Needs checking" mark links to the To fix tab. Saving works as today.

Which tab opens: an employee with something to fix opens on **To fix**; otherwise the tab last chosen in this browser
tab (sessionStorage `em.tab`), Pay the first time. **‹ Previous / Next to fix ›** stay under the tabs. The Look panel
(`…/e/<id>/look`) is unchanged.

### 3.5 Pop-ups

One pop-up at a time, over the page (the HTML `<dialog>` element), with a title and icon, a ×, and Esc to close.
- **Month settings**: normal hours and break side by side, "Rest days every week" as seven day buttons (M T W T F S
  S), the calendar, the count line, Cancel / Save. Same editor and saving as today.
- **Company settings**: the same, with "Same as the month / This company is different" and "next month" as today.
- **Export**: What as two large choices (Payroll table, Million file), Companies as chips (All, or ticked ones), Format
  (CSV / Excel; off for the Million file) and Files (One / One per company) as two-way switches. For the Million file
  the summary (who goes in, who is held and why, per company) appears **inside the pop-up**; **Make the file** makes it,
  closes the pop-up and puts the result in the bell (with the toast). The payroll table downloads as today and closes
  the pop-up.

### 3.6 The company (right)

Head: company name, its status line, icon buttons `calendar-cog` (Company settings pop-up) and `download` (Export
pop-up with only this company ticked). Tabs: **To fix (n)** (its items and "files need you in step 2"), **Pay preview**
(today's pay table with Download and Add employee), **New in Million (n)** (today's list with Copy / Copy all; the tab
is there only when the list is not empty).

## 4. Words and icons

- Buttons and tab names: 1-3 words. Rows: one short line; longer explanations go into a fold or a tooltip, never
  a paragraph on the page. The legends that explain a screen (for example the Pay preview's paragraph) become an
  `info-circle` icon with the text as its tooltip.
- Icons: Tabler Icons (outline, MIT licence), only the ones used (about 25), copied once into `static/icons.svg` as a
  sprite with the licence text in `static/icons-LICENSE.txt`. Copying them needs the user's OK at build time (a
  download from the internet). Every icon-only button has a tooltip and an `aria-label`.
- Every new text has a Malay entry in `static/i18n.js`; Million's English labels stay English as today.

## 5. What does not change

The server's calculations and data, the employee view's saving (one change at a time), the Look panel, steps 1 and 2,
the addresses (`#/payroll/<month>[/e/<id>[/look] | /c/<company>]`), the yellow-cell question before payroll.

## 6. Testing

- Click-throughs in `tools/clickthrough/` (made-up data): new `bell`, `popups`, `employee_tabs`, `company_tabs`; the
  ones that use the old banners or panels (`export`, `people_page`, `employee_page`, `rest_days`, `add_card`,
  `cross_steps`, `check_reading`, `closable_notes`) are updated, and all must say "No problems".
- `pytest`: the payroll folder opens; every icon used in `static/*.js` and `index.html` is in the sprite.
- No real-data check is needed (nothing is worked out differently), but the user looks at the new screens on a real
  month before the app is rebuilt for staff.

## 7. Open for the user

1. OK to download the Tabler icons once (from GitHub or unpkg) at build time?
2. Later, the same look for steps 1 and 2?
