# Table Reader — guide for Claude sessions

Small Windows app for HR/accounting staff: upload scans/photos → Claude reads the table (incl. handwriting) →
user checks highlighted cells → download CSV. Full plan, phases and open decisions: **`PLAN.md`** (read first).
Progress log: `PROGRESS.md` (create/update at the end of every session).
**Continuing work? Read `NEXT-SESSION.md` first** (current state, open items, next step, how to build/run).

## Rules
- **Never guess.** Unreadable or uncertain cells stay blank, keep the raw marks (`raw_text`, `?` for unreadable
  characters) and an `unclear_reason`, and are highlighted for the user. Never fill gaps from patterns, other rows
  or totals.
- Claude's reading (`result.json`) is never modified; user corrections go to `edits.json`; the CSV applies edits on top.
- OCR runs only through the **signed-in Claude Code CLI on the user's own PC** (their Claude plan). Strip
  `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_*` from the CLI's environment. The app never asks for,
  sees or stores Claude credentials; sign-in is Claude's own browser flow (`claude auth login --claudeai`).
- Keep it simple for non-technical users: no settings screens, no accounts, plain-language messages that say what
  happened and what to do next.
- Payroll step (`payroll.py`): pure, visible calculation from *confirmed* cells (rules shown to the user, any figure can be
  overridden). Never fill gaps: unclear/missing/conflicting days are reported and the row is marked INCOMPLETE. OCR itself
  still never calculates.
- Documents may contain personal data: keep everything on the local PC; don't echo personal details in chat.

## Reference code
`reference/from-paytrace/` holds working code from the earlier PayTrace project (`claude_cli.py`, `ocr_providers.py`,
`readers.py`, `types.py`). Adapt the parts listed in PLAN.md §4 into this project; don't import from the reference
folder or from the PayTrace folder.

## Environment (this laptop)
- Windows, PowerShell 5.1, Python 3.14. No Node/npm, no git. Use a no-build frontend (plain HTML/JS/CSS).
- PowerShell strips embedded `"` from `python -c "..."` → write scratch scripts to files.
- Claude Code CLI is at `C:\Users\TENGA CEKAP\.local\bin\claude.exe` (on PATH in new terminals).
- Create a venv in `.venv` and a `requirements.txt` (fastapi, uvicorn, python-multipart, pypdfium2, pillow, pytest,
  later pyinstaller).
