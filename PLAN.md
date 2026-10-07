# Plan: Table Reader — scan → table → CSV

Written 2026-10-06. Derived from the PayTrace project (`C:\Users\TENGA CEKAP\Documents\ocr-system`); the reusable
PayTrace files are copied into `reference/from-paytrace/` (read them; do not import from the PayTrace folder).

## 1. Goal
An HR or accounts person drops in a scanned form or photo, presses one button, sees the table it contains
(including handwriting), fixes anything marked uncertain, and downloads a CSV. Nothing else.

Target users are HR and accounting staff who are not technical. They already have **Claude Code installed and
signed in** on their own PC; OCR runs on **their own Claude plan** through the Claude Code CLI. No API key.

## 2. User flow
1. Double-click **"Table Reader"** on the desktop; the app opens in the browser.
2. First time only: "Connect your Claude account" → **Sign in** opens claude.ai → done. The app then shows
   "Connected as name@company.com (Pro)".
3. Drag files onto the page (PDF, JPG, PNG, several at once).
4. Each file shows "Reading page 1 of 3…" (roughly 10–20 seconds per page).
5. The table appears next to the original image. Cells Claude was unsure about are **highlighted yellow**, with the
   reason on hover. Click a cell to type the correct value.
6. **Download CSV** (one per document). Opens correctly in Excel, including Malay names and symbols.
7. "Recent files" list to reopen or re-download earlier results.

No user accounts, no settings page, no database setup.

## 3. Key design decisions
| Decision | Choice | Why |
|---|---|---|
| Where it runs | Each user's own PC, opened at `localhost` | Claude Code sign-in is per computer/person; files never go to a shared server |
| Installing | One Windows `.exe` (PyInstaller, Python bundled) + desktop shortcut | Users never install Python or type commands |
| OCR engine | Signed-in Claude Code CLI (`claude -p`), adapted from `reference/from-paytrace/claude_cli.py` | Uses their existing plan |
| Table shape | Generic: keep whatever columns the document has | Works for attendance sheets, claims, any form |
| Uncertainty | Unreadable cells stay blank + highlighted + reason; **never guessed** | Core rule carried over from PayTrace |
| Storage | One folder per job: `Documents\Table Reader\jobs\<yyyy-mm-dd_hhmm>_<name>\` holding original, page images, `result.json` (Claude's reading, never edited), `edits.json` (user corrections), CSV | Nothing to set up; users can find files in Explorer |
| CSV | UTF-8 with BOM, one row per table row, form fields (Name, Month…) as leading columns, plus `Page` and `Notes` columns | Excel-friendly; uncertainty stays visible |

## 4. Reuse from PayTrace (in `reference/from-paytrace/`) — simplify, don't copy blindly
- `claude_cli.py` — CLI runner (`claude -p --output-format json --json-schema … --tools Read`, temp folder per page),
  sign-in status (`claude auth status`), sign-in launcher (`claude auth login --claudeai`), removal of
  `ANTHROPIC_API_KEY` etc. from the environment so the **plan** is billed, busy lock, plain-language errors
  (not signed in, plan limit, timeout, bad JSON).
- `ocr_providers.py` — `PAGE_SCHEMA`, `SYSTEM_PROMPT`, `validate_page_json`. Make the prompt **generic** (remove the
  payroll/attendance/Malaysian-payroll wording and document-type list; keep the "never guess" rules, `null` + `raw_text`
  + `unclear_reason`, confidence, skip fully empty rows).
- `readers.py` — only `render_pages` (PDF → PNG with pypdfium2; images via Pillow, EXIF-rotated).
- `types.py` — only if useful; a plain dict model is fine for this app.

Leave out everything else from PayTrace: payroll, employees, database, logins/roles, audit triggers, attendance
import, statutory rules, reports, Google Drive.

## 5. Architecture
```
table-reader/
  app.py              FastAPI: endpoints below + serves the page
  ocr.py              Claude CLI runner + generic prompt/schema/validator
  pages.py            PDF/image → page PNGs
  jobs.py             job folders: create, list, progress, save edits, build CSV
  static/index.html   one page: Claude status box, drop zone, recent files, table + image viewer
  static/app.js, static/app.css
  start.py            pick a free port, start server, open browser
  tests/
```
Endpoints:
- `GET  /api/status` — Claude installed? signed in? (email, plan)
- `POST /api/login` — start Claude's own browser sign-in
- `POST /api/jobs` — upload files → background reading
- `GET  /api/jobs`, `GET /api/jobs/{id}` — list / progress + result
- `PUT  /api/jobs/{id}/cells` — save user corrections
- `GET  /api/jobs/{id}/csv` — download
- `GET  /api/jobs/{id}/pages/{n}` — page image

## 6. Build phases
| Phase | Work | Done when |
|---|---|---|
| 1. Engine | Generic prompt/schema + CLI runner; `python ocr.py scan.jpg` prints validated JSON | A real handwritten form reads correctly; unreadable cells are blank with a reason |
| 2. Jobs + CSV | Job folders, background reading with page progress, CSV builder (edits applied over `result.json`) | CSV opens correctly in Excel; corrections kept separate from Claude's reading |
| 3. Screen | Drop zone, Claude status/sign-in box, progress, table beside image, yellow uncertain cells, inline edit, Download CSV, Recent files | A non-technical person completes upload → fix → download unaided |
| 4. Plain-language errors | Not installed / not signed in / plan limit reached (resume later) / timed out / blurry page | Every failure shows one sentence + what to do; nothing fails silently |
| 5. Packaging | PyInstaller `.exe`, desktop shortcut, one-page illustrated guide | Works on a clean Windows PC that only has Claude Code |
| 6. Pilot | 2–3 HR/accounts users, 20+ real forms; measure % of cells needing correction | Agreed accuracy / time-saved target met |

## 7. Risks to check before rollout
- **Plan terms:** confirm that using a Claude subscription through the CLI from a small app on the user's own PC, for
  their own work, is acceptable under Anthropic's current terms for staff using it at work (Team/Enterprise plans may
  be the cleaner fit). Keep an API-key mode as a fallback.
- **Usage limits:** each page uses plan quota; large batches may stop midway → show it and allow resuming.
- **Speed:** ~10–20 s/page; show progress.
- **Accuracy:** handwriting can be wrong yet look confident → highlight-and-check step is essential; measure in pilot.
- **Privacy:** documents go to Anthropic under the user's account; HR/payroll data may need management/PDPA sign-off.
- **Claude Code updates:** CLI flags may change → check minimum version, clear message on failure.

## 8. Open decisions (defaults used until the user says otherwise)
1. App name: "Table Reader" (default).
2. CSV: one per document (default) vs one combined per batch — ask.
3. Form fields (Name, Month): leading columns on every row (default) vs separate section.
4. Real sample forms for testing — ask the user (personal details may be blanked out).
