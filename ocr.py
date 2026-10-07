"""Read the table in a scan or photo through the user's own signed-in Claude Code CLI (their Claude plan, no API key).

    python ocr.py scan.jpg            prints the validated reading as JSON
    python ocr.py scan.jpg -o out.json

Rules this module enforces (see CLAUDE.md):
- Nothing is guessed. A cell that is unreadable or uncertain keeps value ``None``, keeps the raw marks (``raw_text``,
  ``?`` for unreadable characters) and an ``unclear_reason``, and is flagged ``needs_review``.
- The app never asks for, sees or stores Claude credentials. It only asks the CLI whether it is signed in.
- Everything stays on this PC except what the CLI itself sends to Claude under the user's own account.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# ----------------------------------------------------------------------------------------------- schema and prompt
_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_CELL = {
    "type": "object",
    "properties": {
        "value": _NULLABLE_STR,
        "raw_text": {"type": "string"},
        "confidence": {"type": "number"},
        "unclear_reason": _NULLABLE_STR,
    },
    "required": ["value", "raw_text", "confidence", "unclear_reason"],
    "additionalProperties": False,
}
PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "rotate_clockwise_degrees": {"type": "integer", "enum": [0, 90, 180, 270]},
        "quality": {"type": "string", "enum": ["CLEAR", "MOSTLY_CLEAR", "FADED", "ILLEGIBLE"]},
        "header_fields": {"type": "array", "items": {
            "type": "object",
            "properties": {"label": {"type": "string"}, "cell": _CELL},
            "required": ["label", "cell"], "additionalProperties": False}},
        "column_labels": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {
            "type": "object",
            "properties": {"cells": {"type": "array", "items": {
                "type": "object",
                "properties": {"column": {"type": "string"}, "cell": _CELL},
                "required": ["column", "cell"], "additionalProperties": False}}},
            "required": ["cells"], "additionalProperties": False}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["rotate_clockwise_degrees", "quality", "header_fields", "column_labels", "rows", "notes"],
    "additionalProperties": False,
}

# Compact answer format (the default): the table is plain rows of strings, and only the cells Claude doubts are described
# (in "doubts"). Claude writes far fewer characters than with the full per-cell objects above, and writing the answer is
# most of the time a page takes. A cell not listed in "doubts" is one Claude is sure of.
COMPACT_SCHEMA = {
    "type": "object",
    "properties": {
        "rotate_clockwise_degrees": {"type": "integer", "enum": [0, 90, 180, 270]},
        "quality": {"type": "string", "enum": ["CLEAR", "MOSTLY_CLEAR", "FADED", "ILLEGIBLE"]},
        "header_fields": PAGE_SCHEMA["properties"]["header_fields"],
        "column_labels": {"type": "array", "items": {"type": "string"}},
        "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "doubts": {"type": "array", "items": {
            "type": "object",
            "properties": {"row": {"type": "integer"}, "column": {"type": "integer"}, "raw_text": {"type": "string"},
                           "reason": {"type": "string"}},
            "required": ["row", "column", "raw_text", "reason"], "additionalProperties": False}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["rotate_clockwise_degrees", "quality", "header_fields", "column_labels", "rows", "doubts", "notes"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You transcribe the table in a scanned form or photo (printed text, handwriting, tick grids, stamps) \
into structured data, for staff who will check your work against the original and then use the numbers. A wrong value \
that looks confident is far worse than a blank one. Accuracy matters far more than completeness.

Rules:
- Orientation comes first. If the text reads normally (left to right, top of the page at the top) set \
rotate_clockwise_degrees to 0. If the page is sideways or upside down, set it to the clockwise turn that would make it \
upright: 90 if the top of the page is currently at the left edge, 180 if it is upside down, 270 if the top of the page \
is currently at the right edge. Slight tilt or skew is not a rotation: use 0. When you give a non-zero turn, do not \
transcribe: return empty header_fields, column_labels, rows and notes (and your best guess for quality); the page will \
be turned upright and shown to you again.
- Transcribe exactly what is written. Never infer, complete, correct or calculate a value. Do not fill a blank from \
neighbouring rows, from a pattern, from totals, or from what the document "should" say. Do not add up or check totals.
- If a value is faded, overlapping a grid line, smudged, cropped, partly obscured, ambiguous, or you are not sure, set \
"value" to null, put whatever marks you can see in "raw_text" (use "?" for unreadable characters), and explain in \
"unclear_reason" (for example "Last digit faded", "Tick overlaps the line between two cells").
- Blank cells: value null, raw_text "", unclear_reason null. An empty box, an unsigned signature space, or a printed \
dotted or underscore line waiting to be filled in is a blank cell, not an unclear one: use unclear_reason only when \
something is actually written there that you cannot read.
- Tick grids: write "✓" for a tick and "✗" for a cross, only when the mark is clearly inside that cell. If a \
mark sits on a boundary or could belong to two cells, set value null for both cells and explain.
- Times, dates, amounts, names: copy as written, in the original language and spelling. Do not reformat, convert \
12-hour to 24-hour, translate or normalise.
- A value that was crossed out and overwritten: value null, raw_text with both readings, reason "Overwritten".
- confidence is 0-100 for how sure you are that "value" matches the document; use below 70 when in doubt.
- Transcribe every row on the page, from the first to the last, even when most of its cells are unreadable (leave \
those null with a reason). Never stop part-way; if you truly cannot finish, say exactly which rows are missing in notes.
- One output row per table row on the page, in the order shown. Skip rows that are completely empty (no writing in any \
cell) and say how many in notes. A total or subtotal row inside the table is an ordinary row: copy it as written.
- Keep every column, including ones you do not understand, using the printed column label. If a column has no label \
use "COL1", "COL2"... by position. If the heading has two levels, join them like "Overtime / Hours". Every row must \
list a cell for every column.
- Put form fields outside the table (name, month, department, company, signatures present or absent, totals written \
below the table) in header_fields as label + cell.
- If the page contains no table, return no rows and say so in notes.
- notes: anything a reviewer should know (stamps over data, cropped edge, rotated page, corrections or overwrites)."""

COMPACT_PROMPT = """You transcribe the table in a scanned form or photo (printed text, handwriting, tick grids, stamps) \
into structured data, for staff who will check your work against the original and then use the numbers. A wrong value \
that looks confident is far worse than a blank one. Accuracy matters far more than completeness.

Answer format: "column_labels" lists the columns. "rows" has one array per table row, and each array holds exactly one \
string per column, in the same order as column_labels (use "" for a blank cell). Do not repeat column names in rows. \
"doubts" lists every cell you are not sure of: "row" is the 0-based position of the row in "rows", "column" the 0-based \
position in column_labels, "raw_text" the marks you can see (use "?" for unreadable characters), "reason" a short \
explanation. Put "" in rows for every doubted cell; its marks go only in doubts.

Rules:
- Orientation comes first. If the text reads normally (left to right, top of the page at the top) set \
rotate_clockwise_degrees to 0. If the page is sideways or upside down, set it to the clockwise turn that would make it \
upright: 90 if the top of the page is currently at the left edge, 180 if it is upside down, 270 if the top of the page \
is currently at the right edge. Slight tilt or skew is not a rotation: use 0. When you give a non-zero turn, do not \
transcribe: return empty header_fields, column_labels, rows, doubts and notes (and your best guess for quality); the \
page will be turned upright and shown to you again.
- Transcribe exactly what is written. Never infer, complete, correct or calculate a value. Do not fill a blank from \
neighbouring rows, from a pattern, from totals, or from what the document "should" say. Do not add up or check totals.
- A cell that is faded, overlapping a grid line, smudged, cropped, partly obscured, ambiguous, or that you are less than \
about 70% sure of, is a doubt (explain it, for example "Last digit faded", "Tick overlaps the line between two cells"). \
Never put a guess in rows: when in doubt, rows has "" and doubts has the marks. Only cells you are sure of go in rows.
- Blank cells: "" in rows and no doubt. An empty box, an unsigned signature space, or a printed dotted or underscore line \
waiting to be filled in is a blank cell, not a doubt: use a doubt only when something is actually written there that \
you cannot read.
- Tick grids: write "✓" for a tick and "✗" for a cross, only when the mark is clearly inside that cell. If a mark sits \
on a boundary or could belong to two cells, make both cells doubts and explain.
- Times, dates, amounts, names: copy as written, in the original language and spelling. Do not reformat, convert \
12-hour to 24-hour, translate or normalise.
- A value that was crossed out and overwritten is a doubt: raw_text with both readings, reason "Overwritten".
- Transcribe every row on the page, from the first to the last, even when most of its cells are unreadable (make those \
doubts). Never stop part-way; if you truly cannot finish, say exactly which rows are missing in notes.
- One row per table row on the page, in the order shown. Skip rows that are completely empty (no writing in any cell) \
and say how many in notes. A total or subtotal row inside the table is an ordinary row: copy it as written.
- Keep every column, including ones you do not understand, using the printed column label. If a column has no label \
use "COL1", "COL2"... by position. If the heading has two levels, join them like "Overtime / Hours".
- Put form fields outside the table (name, month, department, company, signatures present or absent, totals written \
below the table) in header_fields as label + cell (value, raw_text, confidence 0-100, unclear_reason; use value null \
with raw_text and unclear_reason when unsure, as for a doubt).
- If the page contains no table, return no rows and say so in notes.
- notes: anything a reviewer should know (stamps over data, cropped edge, rotated page, corrections or overwrites)."""

UNSURE_BELOW = 70.0         # a value Claude is less sure of than this is not trusted: it is blanked and highlighted
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
MAX_SIDE = 2400              # longest image side sent to Claude, in pixels
DEFAULT_TIMEOUT = 300        # seconds per page
OUTPUT_FORMAT = os.environ.get("TABLE_READER_FORMAT", "compact")   # "compact" (default) or "full": for speed comparisons
MODEL = "claude-sonnet-5-5"  # every page is read with this model and effort, so all PCs behave the same
EFFORT = "medium"
MAX_LOOKS = 3                # a sideways page is turned and shown again; never more than this many readings

# Variables that would make the CLI bill an API account or cloud provider instead of the user's plan.
_BILLING_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                "CLAUDE_CODE_USE_FOUNDRY")


class OcrError(Exception):
    """A failure with a plain-language message that says what happened and what to do next."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# --------------------------------------------------------------------------------------------- Claude CLI access
def cli_path() -> str | None:
    """Claude Code's command. A shortcut started from the desktop may not have the folder it installs into on PATH, so
    the installer's usual location is tried too."""
    found = shutil.which("claude")
    if found:
        return found
    for candidate in (Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude"):
        if candidate.is_file():
            return str(candidate)
    return None


def _env() -> dict[str, str]:
    env = os.environ.copy()
    for key in _BILLING_ENV:
        env.pop(key, None)
    return env


def auth_status() -> dict:
    """{installed, logged_in, email, plan, message}. Never raises, never reads credentials."""
    out = {"installed": False, "logged_in": False, "email": None, "plan": None, "message": None}
    cli = cli_path()
    if not cli:
        out["message"] = ("Claude Code is not installed on this computer. Install it from claude.com/claude-code, "
                          "then open this app again.")
        return out
    out["installed"] = True
    try:
        proc = subprocess.run([cli, "auth", "status"], capture_output=True, text=True, timeout=30, env=_env(),
                              encoding="utf-8", errors="replace")
        data = json.loads(proc.stdout or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        out["message"] = "Could not check whether Claude is signed in. Close this app and open it again."
        return out
    out["logged_in"] = bool(data.get("loggedIn"))
    out["email"] = data.get("email")
    out["plan"] = data.get("subscriptionType")
    if out["logged_in"] and data.get("authMethod") != "claude.ai":
        out["logged_in"] = False
        out["message"] = ("Claude Code is signed in with an API account, not with your Claude plan, so reading would "
                          "be billed per use. Sign in again with your Claude account.")
    elif not out["logged_in"]:
        out["message"] = "You are not signed in to Claude. Press Sign in and finish the steps in your browser."
    return out


def start_login() -> None:
    """Start Claude's own browser sign-in. The user finishes it on claude.ai; this app never sees credentials."""
    cli = cli_path()
    if not cli:
        raise OcrError("CLAUDE_CLI_MISSING", "Claude Code is not installed on this computer. Install it from "
                       "claude.com/claude-code, then open this app again.")
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    subprocess.Popen([cli, "auth", "login", "--claudeai"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, env=_env(), creationflags=flags)


# ----------------------------------------------------------------------------------------------- validation
def validate_page_json(data, schema: dict = PAGE_SCHEMA, path: str = "$") -> list[str]:
    """Minimal JSON-schema check for the subset PAGE_SCHEMA uses. Returns a list of error messages (empty = valid)."""
    errors: list[str] = []
    if "anyOf" in schema:
        if all(validate_page_json(data, s, path) for s in schema["anyOf"]):
            errors.append(f"{path}: value {data!r} does not match any allowed type")
        return errors
    t = schema.get("type")
    checks = {"object": dict, "array": list, "string": str, "null": type(None)}
    if t == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            return [f"{path}: expected a number, got {type(data).__name__}"]
    elif t == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            return [f"{path}: expected a whole number, got {type(data).__name__}"]
    elif t in checks and not isinstance(data, checks[t]):
        return [f"{path}: expected {t}, got {type(data).__name__}"]
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: {data!r} is not one of {schema['enum']}")
    if t == "object":
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}: missing required key '{key}'")
        if schema.get("additionalProperties") is False:
            for key in data:
                if key not in schema.get("properties", {}):
                    errors.append(f"{path}: unexpected key '{key}'")
        for key, sub in schema.get("properties", {}).items():
            if key in data:
                errors.extend(validate_page_json(data[key], sub, f"{path}.{key}"))
    if t == "array":
        for i, item in enumerate(data):
            errors.extend(validate_page_json(item, schema.get("items", {}), f"{path}[{i}]"))
    return errors


# ------------------------------------------------------------------------------------------------ never guess
_FILL_IN_LINE = re.compile(r"[._…]{3,}|…{2,}|-{3,}")


def _is_fill_in_line(raw: str) -> bool:
    """Only dots, underscores or dashes: the printed line of an empty field (........, ______), not handwriting."""
    return bool(_FILL_IN_LINE.fullmatch(re.sub(r"\s+", "", raw)))


def normalize_cell(cell: dict) -> dict:
    """Apply the "never guess" rule to one cell. Returns a new cell with a fixed shape:
    value, raw_text, confidence, unclear_reason, needs_review.

    A cell is trusted only when it has a value, Claude gave no reason to doubt it, it has no "?" marks and its
    confidence is at least UNSURE_BELOW. Anything else loses its value (the marks stay in raw_text) and carries a
    reason, so it is highlighted for the user instead of being passed on as if it were certain.
    """
    value = cell.get("value")
    if isinstance(value, str) and value.strip() == "":
        value = None
    raw = cell.get("raw_text") or ""
    reason = (cell.get("unclear_reason") or "").strip() or None
    try:
        confidence = max(0.0, min(float(cell.get("confidence") or 0), 100.0))
    except (TypeError, ValueError):
        confidence = 0.0

    if value is not None:
        if not raw:
            raw = value
        if reason is None and "?" in raw:
            reason = "Some characters could not be read"
        if reason is None and confidence < UNSURE_BELOW:
            reason = f"Claude was not sure ({confidence:.0f}% confident)"
        if reason is not None:
            value = None                       # uncertain: keep the marks, not a value
    elif reason is None and _is_fill_in_line(raw):
        raw = ""                                       # a printed dotted line waiting to be filled in is just empty
    elif raw.strip() and reason is None:
        reason = "Could not be read with confidence"   # marks present but no value and no explanation

    if value is None and reason is None:       # genuinely empty cell
        confidence = 0.0
    return {"value": value, "raw_text": raw, "confidence": confidence, "unclear_reason": reason,
            "needs_review": reason is not None}


def _missing_cell() -> dict:
    return {"value": None, "raw_text": "", "confidence": 0.0,
            "unclear_reason": "Claude did not report this cell", "needs_review": True}


def _unique(labels: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for label in labels:
        label = label.strip() or "COL"
        seen[label] = seen.get(label, 0) + 1
        out.append(label if seen[label] == 1 else f"{label} ({seen[label]})")
    return out


def expand_compact(data: dict) -> dict:
    """Turn the compact answer (rows of strings + doubts) into the full per-cell shape that normalize_page handles.
    A cell in "doubts" has no value (its marks and reason are kept); every other non-empty string is a value Claude is
    sure of. A row that is too short gets its missing cells flagged by normalize_page; a doubt that points at no cell is
    not lost: it goes to the notes."""
    labels = list(data["column_labels"])
    notes = list(data["notes"])
    doubts: dict[tuple[int, int], dict] = {}
    rows_in = data["rows"]
    for d in data["doubts"]:
        r, c = d["row"], d["column"]
        if 0 <= r < len(rows_in) and 0 <= c < max(len(labels), max((len(x) for x in rows_in), default=0)):
            doubts[(r, c)] = d
        else:
            notes.append(f"Claude reported a doubt it could not place ({d['reason']}: {d['raw_text']}). Check the page.")
    rows = []
    for r, strings in enumerate(rows_in):
        cells = []
        for c, text in enumerate(strings):
            while c >= len(labels):
                labels.append(f"COL{len(labels) + 1}")             # more cells than column labels: keep them
            d = doubts.pop((r, c), None)
            if d is not None:
                cell = {"value": None, "raw_text": d["raw_text"], "confidence": 0, "unclear_reason": d["reason"] or None}
                if not cell["unclear_reason"]:
                    cell["unclear_reason"] = "Claude was not sure"
            else:
                cell = {"value": text, "raw_text": text, "confidence": 100 if text.strip() else 0, "unclear_reason": None}
            cells.append({"column": labels[c], "cell": cell})
        rows.append({"cells": cells})
    for (r, c), d in doubts.items():                                # doubt on a cell the row did not have
        while c >= len(labels):
            labels.append(f"COL{len(labels) + 1}")
        rows[r]["cells"].append({"column": labels[c], "cell": {
            "value": None, "raw_text": d["raw_text"], "confidence": 0, "unclear_reason": d["reason"] or "Claude was not sure"}})
    return {**data, "column_labels": labels, "rows": rows, "notes": notes}


def normalize_page(data: dict) -> dict:
    """Turn validated Claude output into the page record: never-guess applied to every cell, every row rectangular
    (one cell per column, in column order). A cell Claude left out is flagged, never silently treated as empty."""
    if "doubts" in data:
        data = expand_compact(data)
    data = copy.deepcopy(data)
    labels = _unique(list(data["column_labels"]))
    rows = []
    for row in data["rows"]:
        by_col: dict[str, dict] = {}
        for item in row["cells"]:
            col = item["column"].strip() or "COL"
            if col not in labels:
                # A column Claude used in a row but never listed: add it rather than lose the data.
                labels.append(col)
            key = col
            n = 2
            while key in by_col:            # same column reported twice in one row: keep both, don't overwrite
                key = f"{col} ({n})"
                n += 1
                if key not in labels:
                    labels.append(key)
            by_col[key] = normalize_cell(item["cell"])
        rows.append(by_col)
    out_rows = [{"cells": {lab: by_col.get(lab) or _missing_cell() for lab in labels}} for by_col in rows]
    return {
        "quality": data["quality"],
        "header_fields": [{"label": f["label"], "cell": normalize_cell(f["cell"])} for f in data["header_fields"]],
        "column_labels": labels,
        "rows": out_rows,
        "notes": list(data["notes"]),
    }


# --------------------------------------------------------------------------------------- running Claude on a page
def prepare_image(src: Path, dst_dir: Path, rotate_clockwise: int = 0) -> Path:
    """Copy of the page for Claude: upright (EXIF), turned clockwise by ``rotate_clockwise`` degrees (0/90/180/270),
    RGB, at most MAX_SIDE px on the longest side, as PNG. The original file is never touched."""
    from PIL import Image, ImageOps

    try:
        with Image.open(src) as im:
            im.seek(0)
            img = ImageOps.exif_transpose(im.convert("RGB"))
    except Exception as exc:  # noqa: BLE001 - any decoder failure means "not a readable picture"
        raise OcrError("IMAGE_UNREADABLE", f"{src.name} could not be opened as a picture. Check that the file is not "
                       "damaged, or take the photo again.") from exc
    if rotate_clockwise % 360:
        img = img.rotate(-(rotate_clockwise % 360), expand=True)     # PIL turns counter-clockwise for positive angles
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    target = dst_dir / "page.png"
    img.save(target)
    return target


def parse_cli_output(stdout: str, stderr: str = "", returncode: int = 0) -> dict:
    """Turn the CLI's ``--output-format json`` envelope into a validated page dict (raw, before never-guess).
    Raises OcrError with a plain-language message for every failure. Pure function: no Claude needed to test it."""
    try:
        envelope = json.loads(stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        detail = (stderr or stdout or "").strip()[:200]
        raise OcrError("CLAUDE_CLI_ERROR", "Claude Code did not return a reading"
                       + (f" ({detail})" if detail else "") + ". Try again; if it keeps happening, open Claude Code "
                       "once on its own to check that it works.") from exc
    if not isinstance(envelope, dict):
        raise OcrError("CLAUDE_CLI_BAD_JSON", "Claude's answer was not in the expected form. Try this file again.")
    if envelope.get("is_error"):
        msg = str(envelope.get("result") or "")[:300]
        low = msg.lower()
        # limit wording first: a limit message can also mention "login" or "expired" (e.g. "resets at 5pm")
        if any(k in low for k in ("usage limit", "rate limit", "limit reached", "429", "quota", "session limit")):
            raise OcrError("CLAUDE_PLAN_LIMIT", "Your Claude plan has reached its usage limit for now. Wait until "
                           "the limit resets (Claude Code shows when), then press Continue; pages already read are kept.")
        if any(k in low for k in ("not logged in", "please run /login", "login", "401", "authenticat", "invalid api key",
                                  "expired")):
            raise OcrError("CLAUDE_LOGIN_REQUIRED", "Your Claude sign-in has expired. Press Sign in (top right), then "
                           "press Continue.")
        raise OcrError("CLAUDE_CLI_ERROR", f"Claude reported a problem: {msg or 'no details given'}. "
                       "Try this file again.")
    data = envelope.get("structured_output")
    if data is None:
        text = envelope.get("result")
        try:
            data = json.loads(text) if isinstance(text, str) else None
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        raise OcrError("CLAUDE_CLI_BAD_JSON", "Claude's answer was not in the expected form, so nothing was read. "
                       "Try this file again.")
    errors = validate_page_json(data, COMPACT_SCHEMA if "doubts" in data else PAGE_SCHEMA)
    if errors:
        raise OcrError("CLAUDE_CLI_BAD_JSON", f"Claude's answer did not match the expected form ({errors[0]}), so "
                       "nothing was read. Try this file again.")
    return data


def build_command(cli: str, work_dir: Path, model: str | None = None) -> list[str]:
    compact = OUTPUT_FORMAT == "compact"
    cmd = [cli, "-p", "--output-format", "json", "--json-schema", json.dumps(COMPACT_SCHEMA if compact else PAGE_SCHEMA),
           "--system-prompt", COMPACT_PROMPT if compact else SYSTEM_PROMPT, "--tools", "Read", "--allowedTools", "Read",
           "--permission-mode", "dontAsk", "--no-session-persistence", "--strict-mcp-config",
           "--disable-slash-commands", "--add-dir", str(work_dir)]
    cmd += ["--model", model or MODEL, "--effort", EFFORT]
    return cmd


def read_image(path: str | Path, *, timeout: int = DEFAULT_TIMEOUT, model: str | None = None) -> dict:
    """Read one page image with the signed-in Claude Code CLI. Returns the normalised page record, which also holds
    ``rotated_clockwise``: how far the picture had to be turned for Claude to read it (0 if it was already upright).
    A page Claude finds sideways or upside down is turned and read again once; only the second reading is kept.
    Raises OcrError (plain-language message) on any failure; never returns a partly guessed result."""
    path = Path(path)
    if not path.is_file():
        raise OcrError("FILE_MISSING", f"The file {path.name} was not found.")
    if path.suffix.lower() not in IMAGE_EXT:
        raise OcrError("FILE_TYPE", f"{path.name} is not a picture file. Use JPG or PNG.")
    status = auth_status()
    if not status["installed"] or not status["logged_in"]:
        raise OcrError("CLAUDE_LOGIN_REQUIRED" if status["installed"] else "CLAUDE_CLI_MISSING", status["message"])
    cli = cli_path()

    # Claude sometimes picks the wrong direction (90 instead of 270): the next look then sees the page upside down and
    # says so, which brings the total turn right. The last look must transcribe whatever it sees.
    turn = 0
    unsure_way_up = False
    looks: list[dict] = []
    started = time.monotonic()
    for look in range(1, MAX_LOOKS + 1):
        last = look == MAX_LOOKS
        raw = _ask_claude(cli, path, turn, timeout, model, must_transcribe=last, stats=looks)
        more = raw["rotate_clockwise_degrees"]
        if not more:
            break
        if last:
            unsure_way_up = True
            break
        turn = (turn + more) % 360
    record = normalize_page(raw)
    record["rotated_clockwise"] = turn
    record["timing"] = {                 # where the time went; used by bench.py and shown in the job log, never in the CSV
        "seconds": round(time.monotonic() - started, 1), "looks": len(looks),
        "claude_seconds": [s["seconds"] for s in looks], "output_tokens": [s["output_tokens"] for s in looks],
        "model": model or MODEL, "effort": EFFORT, "format": OUTPUT_FORMAT}
    if unsure_way_up:
        record["notes"].append("Claude was not sure which way up this page is. Check every cell against the picture.")
    return record


_cancel = threading.local()


def set_cancel_event(event: threading.Event | None) -> None:
    """Let the calling thread's Claude run be stopped: when ``event`` is set, the running CLI is killed and the page
    read raises OcrError("CANCELLED"). Per thread, so each background worker has its own."""
    _cancel.event = event


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":                                  # the CLI may start helper processes of its own
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    proc.kill()
    try:
        proc.communicate(timeout=5)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass


def _run_cli(cmd: list[str], *, input: str, timeout: float, cwd: str, env: dict) -> subprocess.CompletedProcess:
    """Run the CLI like subprocess.run, but check twice a second whether the user pressed Cancel."""
    cancel = getattr(_cancel, "event", None)
    cancelled = OcrError("CANCELLED", "Reading was cancelled. Pages already read are kept; press Continue to read the "
                                      "rest.")
    if cancel is not None and cancel.is_set():
        raise cancelled
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", cwd=cwd, env=env)
    deadline = time.monotonic() + timeout
    to_send = input
    while True:
        try:
            out, err = proc.communicate(input=to_send, timeout=0.5)
            return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr=err)
        except subprocess.TimeoutExpired:
            to_send = None                               # the prompt has been handed over; just keep waiting
            if cancel is not None and cancel.is_set():
                _kill_tree(proc)
                raise cancelled from None
            if time.monotonic() >= deadline:
                _kill_tree(proc)
                raise subprocess.TimeoutExpired(cmd, timeout) from None


def _ask_claude(cli: str, path: Path, rotate_clockwise: int, timeout: int, model: str | None,
                must_transcribe: bool = False, stats: list[dict] | None = None) -> dict:
    """One Claude call on one page (turned by ``rotate_clockwise``). Returns the validated raw answer; if ``stats`` is
    given, how long the call took and how much Claude wrote is appended to it."""
    began = time.monotonic()
    # Claude works in an empty temp folder that holds only a copy of this page; its only tool (Read) is confined there.
    with tempfile.TemporaryDirectory(prefix="table-reader-") as tmp:
        work = Path(tmp)
        page = prepare_image(path, work, rotate_clockwise)
        prompt = (f"Use the Read tool to view the image file {page.name} in the current directory, then transcribe "
                  "its table following the rules and the required JSON schema.")
        if must_transcribe:
            prompt += (" This is the last look at this page: transcribe it exactly as shown, even if you think it is "
                       "still sideways (you may still say in rotate_clockwise_degrees what you think is needed).")
        try:
            proc = _run_cli(build_command(cli, work, model), input=prompt, timeout=timeout, cwd=tmp, env=_env())
        except subprocess.TimeoutExpired as exc:
            raise OcrError("CLAUDE_CLI_TIMEOUT", f"Claude took longer than {timeout // 60} minutes on this page. "
                           "Try again, or use a smaller or clearer picture.") from exc
        except OSError as exc:
            raise OcrError("CLAUDE_CLI_ERROR", f"Claude Code could not be started ({exc}). Reinstall Claude Code "
                           "or restart the computer, then try again.") from exc
    data = parse_cli_output(proc.stdout, proc.stderr, proc.returncode)
    if stats is not None:
        stats.append({"seconds": round(time.monotonic() - began, 1), "output_tokens": _output_tokens(proc.stdout)})
    return data


def _output_tokens(stdout: str) -> int | None:
    try:
        tokens = json.loads(stdout)["usage"]["output_tokens"]
        return tokens if isinstance(tokens, int) else None
    except (ValueError, KeyError, TypeError):
        return None


# ----------------------------------------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read the table in a scan or photo with your signed-in Claude Code.")
    ap.add_argument("image", help="JPG or PNG file")
    ap.add_argument("-o", "--out", help="write the JSON here (UTF-8) instead of printing it")
    ap.add_argument("--model", help=f"Claude model name (default: {MODEL})")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="seconds before giving up (default 300)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    try:
        result = read_image(args.image, timeout=args.timeout, model=args.model)
    except OcrError as exc:
        print(f"[{exc.code}] {exc.message}", file=sys.stderr)
        return 1
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
