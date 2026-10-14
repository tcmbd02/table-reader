"""Claude's suggestion of what a card layout's columns mean (a layout map, see payroll.valid_layout_map).

Claude sees text only: the column headings and a few rows with every value reduced to its shape (digits as 9, letters
as A, apart from marks and time words such as PH, OFF, am, OT), so no name, date or figure of the card is sent. Its
answer is a suggestion: it is checked here exactly as the user's own map is, and used only after the user confirms it.
Claude never calculates; the figures are worked out by payroll.read_days.
"""
from __future__ import annotations

import json
import re
from typing import Callable

import ocr
import payroll

# words kept as written in a shape: the marks a card uses and the words around clock times (all other letters -> A)
_KEEP = {code for codes in payroll.GRID_MARKS.values() for code in codes if code.isalpha()} | {
    "am", "pm", "ot", "in", "out", "h", "hr", "hrs", "jam", "min", "mins", "x", "sa", "su", "sat", "sun"}

ROLE_WORDS = {
    "date": "the day of the month (a date or a day number)",
    "hours": "the hours worked that day (as one figure)",
    "in": "a clock time the worker came in (paired with the next 'out' column)",
    "out": "a clock time the worker went out",
    "stamps": "several clock times in one cell (in, out, in, out ...)",
    "lateness": "time the worker was late that day",
    "early_departure": "time the worker left early that day",
    "ot_1": "overtime paid at 1.0 times that day",
    "ot_1_5": "overtime paid at 1.5 times that day (normal overtime)",
    "ot_2": "overtime paid at 2.0 times that day",
    "ot_3": "overtime paid at 3.0 times that day",
    "ignore": "anything else, or when you are not sure",
}

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {"columns": {"type": "array", "items": {
        "type": "object",
        "properties": {"label": {"type": "string"}, "role": {"type": "string", "enum": list(payroll.LAYOUT_ROLES)},
                       "unit": {"type": "string", "enum": list(payroll.LAYOUT_UNITS)}},
        "required": ["label", "role", "unit"], "additionalProperties": False}}},
    "required": ["columns"], "additionalProperties": False}


def _shape(text: str) -> str:
    text = re.sub(r"\d", "9", text)
    return re.sub(r"[^\W\d_]+", lambda m: m.group(0) if m.group(0).casefold() in _KEEP else "A" * len(m.group(0)), text)


def shapes(page: dict, rows: int = 5) -> list[dict]:
    """Up to ``rows`` rows of the page as {heading: shape}: what Claude is shown of the values. A yellow cell is shaped
    from what Claude saw (its raw marks)."""
    out = []
    for row in page["rows"][:rows]:
        out.append({label: _shape((c["raw_text"] if c["needs_review"] else c["value"]) or "")
                    for label, c in ((label, row["cells"][label]) for label in page["column_labels"])})
    return out


def _prompt(page: dict) -> str:
    roles = "\n".join(f"- {role}: {ROLE_WORDS[role]}" for role in payroll.LAYOUT_ROLES)
    return ("A time card's table has these column headings, in order, and these first rows. In the rows every digit "
            "is shown as 9 and every letter as A, except marks such as PH, OFF, MC and the words am, pm, OT.\n\n"
            f"Headings: {json.dumps(page['column_labels'], ensure_ascii=False)}\n"
            f"Rows: {json.dumps(shapes(page), ensure_ascii=False)}\n\n"
            "For every heading, say which one of these it is:\n"
            f"{roles}\n\n"
            "Give each figure (hours, lateness, early_departure, ot_*) a unit: 'hours' when it is written as hours "
            "(8, 8.5 or 8:30), 'minutes' when it counts minutes. Every other role has the unit 'none'. At most one "
            "column is the date. Never guess: when you are not sure what a column holds, say 'ignore'. Answer every "
            "heading exactly as written, once each.")


def suggest(page: dict, ask: Callable[..., dict] | None = None) -> dict:
    """Claude's suggested map for this page's layout, checked (payroll.valid_layout_map): {heading: {"role", "unit"}}.
    An answer that does not fit (a heading twice or missing, a role or unit not on the list) raises BAD_LAYOUT."""
    answer = (ask or ocr.ask_text)(_prompt(page), SUGGEST_SCHEMA)
    bad = ocr.OcrError("BAD_LAYOUT", "What the columns mean could not be understood. Open the card layout again.")
    items = answer.get("columns") if isinstance(answer, dict) else None
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise bad
    columns = {i.get("label"): {"role": i.get("role"), "unit": i.get("unit")} for i in items}
    if len(columns) != len(items):
        raise bad                                            # a heading answered twice
    return payroll.valid_layout_map(list(page["column_labels"]), columns)
