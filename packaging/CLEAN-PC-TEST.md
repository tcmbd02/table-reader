# Clean-PC test checklist

Goal: prove that Table Reader installs and works for a person who has **only Claude Code** on their PC (the "done when"
of Phase 5). Do it in a new Windows user account, a VMware/VirtualBox machine, or a colleague's PC.

Use a **harmless test form** (invented or blanked-out data), not real staff documents. You need:
- `Table Reader.zip` (from `dist\`, built by `packaging\build.ps1`) copied to the test PC (USB stick, shared folder, e-mail to yourself…)
- one multi-page PDF (3+ pages) and one phone photo (JPG), ideally one of them slightly sideways or blurry

Tester name: ____________  Date: ____________  Where tested: ☐ new user on my laptop ☐ VM ☐ other PC ____________
Windows version: ____________  Claude Code installed? ☐ yes ☐ no (part A tests this)

Mark each line ✔ or ✘. For every ✘ write what you saw (exact message, and a screenshot if possible) in the Notes at the end.

---

## A. Before installing (the PC really is clean)
- ☐ A1. The PC has **no** `Table Reader` folder, no Python needed, and no copy of this project (the test must not secretly rely on them).
- ☐ A2. Open the zip → unzip the **whole folder** (right-click → Extract All). Files seen: `Table Reader.exe`, `Install Table Reader.bat`, `install.ps1`, `Table Reader guide.pdf`, `_internal`.
- ☐ A3. **Without Claude Code installed yet:** double-click `Table Reader.exe` straight from the unzipped folder. The page opens and the top shows a plain message that Claude Code is not installed (no error window, no crash).
- ☐ A4. Close it with **Quit Table Reader**. Then install Claude Code, run `claude` once, and sign in with a Claude account.

## B. Install
- ☐ B1. Double-click **Install Table Reader.bat**. If Windows shows a blue "Windows protected your PC" (SmartScreen) box, note it (the .exe is unsigned): *More info → Run anyway*.  Warning seen? ☐ yes ☐ no
- ☐ B2. No administrator password was asked for.
- ☐ B3. The window ends with "Table Reader is installed…" (and **no** yellow "Claude Code was not found" note now that it is installed).
- ☐ B4. A **Table Reader** icon (blue tile with a table) is on the desktop.
- ☐ B5. `%LOCALAPPDATA%\Table Reader\Table Reader.exe` exists (paste that path in the File Explorer address bar).
- ☐ B6. Antivirus did not delete or quarantine anything. Product: ____________

## C. First start
- ☐ C1. Double-click the desktop icon. The browser opens Table Reader within **about 15 seconds** (first start may be slower while Windows scans the files). Seconds: ______
- ☐ C2. No black console window appears.
- ☐ C3. Top of the page: "✓ Claude connected" with the right e-mail and plan.
  - If instead it says *not signed in*: press **Sign in**, finish in the browser, and the page switches to "connected" by itself (about 3–10 s). ☐ worked
- ☐ C4. Double-click the desktop icon **again** while it is running: the page opens again, and Task Manager shows only **one** "Table Reader" process.

## D. Reading files
- ☐ D1. Drag the **multi-page PDF** onto the box. It appears under Recent files and the page shows "Reading page 1 of N…" then moves on. Time per page: ______ s (expected roughly 10–60 s)
- ☐ D2. Pages appear in the table as they are read; the original page picture is shown next to the table.
- ☐ D3. While it is reading, add the **photo** too. It shows "Waiting…" and is read after the PDF.
- ☐ D4. A sideways photo (if you have one) ends up upright in the picture viewer.
- ☐ D5. Add a file that is **not** a PDF or picture (for example a .docx). A plain sentence says it cannot be used; the other files are unaffected.
- ☐ D6. **Cancel**: add another multi-page file and press **Cancel reading** (on the document, or **Cancel** in Recent files) while it reads. It stops within a few seconds, shows "Cancelled", and no `claude` process stays in Task Manager. Press **Continue reading**: it carries on from the page where it stopped.

## E. Checking and correcting
- ☐ E1. Unsure cells are **yellow** with a reason; hovering shows the reason too.
- ☐ E2. **Use this** saves Claude's reading at once (the yellow goes, a blue edge shows, the counter drops by one).
- ☐ E3. Typing a value + Enter saves it. **It's empty** saves an empty cell. **Undo my change** brings the original back.
- ☐ E4. **Go to next cell to check** jumps to the next yellow cell.
- ☐ E5. Type a correction, close the browser tab, open Table Reader again from the desktop icon → Recent files → Open: the correction is still there.

## F. CSV
- ☐ F1. **Download CSV** with yellow cells left: it asks "N cells are still highlighted… Download anyway?"
- ☐ F2. Open the CSV in **Excel** by double-clicking. Letters such as é, Malay names and symbols look right (no garbled characters).
- ☐ F3. Corrected cells are filled in; unfixed yellow cells are blank with an explanation in the **Notes** column; `Page` column present.
- ☐ F4. Known issue to look at: numbers with leading zeros (IC, phone) lose the zero in Excel? ☐ yes ☐ no ☐ no such data

## G. Failure messages (do the ones you can)
- ☐ G1. Sign out of Claude (`claude auth logout` in a terminal), then try to add a file: the page says Claude is not signed in and what to do (press Sign in). After signing in, **Continue reading** works.
- ☐ G2. Turn off Wi-Fi/unplug the network while a page is reading: a plain message appears (not a stack trace) and **Continue reading** works once back online.
- ☐ G3. Plan limit (only if it happens): message says to wait for the limit to reset and press Continue; finished pages are kept.

## H. Closing and leftovers
- ☐ H1. Press **Quit Table Reader**, confirm. The page says "Table Reader has closed." and Task Manager shows no "Table Reader" or `claude` process after ~5 s.
- ☐ H2. While a file is reading, press **Quit Table Reader**: it warns that files are being read, then stops them cleanly. Next start shows the file as "Cancelled" and Continue works.
- ☐ H3. Files are in `Documents\Table Reader\jobs\<date>_<name>\` (original, pages, CSV). If something misbehaved, send `Documents\Table Reader\table-reader.log` to the developer **after checking it holds nothing private** (it should hold no document contents).
- ☐ H4. Restart the PC; double-click the icon: it still starts normally.

## I. Remove it (optional, to test again from scratch)
There is no uninstaller yet: delete the desktop shortcut and the folder `%LOCALAPPDATA%\Table Reader`. Your documents in
`Documents\Table Reader` stay until you delete them.

---

## Result
☐ **Pass** (every line ✔, or only small notes)  ☐ **Pass with problems** (list below)  ☐ **Fail** (could not install or read a file)

Time from "unzip" to "first CSV downloaded", counting the Claude sign-in: ______ minutes

## Notes (what went wrong, exact messages, screenshots, ideas)
