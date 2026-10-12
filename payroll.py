"""Payroll step: confirmed time-card cells -> the month-end figures Million Payroll asks for (Edit Payroll screen).

Table Reader reads and the user corrects; this module only *calculates* from those confirmed cells, with rules the user
can see and change (which days are working / rest / public holiday days, normal hours per day). It never guesses:
a day whose hours are still unclear, a day with no entry, or a conflict is reported as an issue, not filled in.

A "plan" is saved per month in <Documents>\\Table Reader\\payroll\\<yyyy-mm>.json:
    {"month": "2026-09", "normal_hours": 8, "day_types": {"1": "work", ... "6": "rest", "16": "holiday"},
     "lists": {"leave" | "allowance" | "deduction" | "bik": [{"name", "type"}]},
     "employees": [{"id", "emp_no", "name", "jobs": [job ids], "hours_column": null | "Total", "overrides": {field: number},
                    "entries": {list kind: {line name: number}}, "zakat", "levy", "message",
                    "worker_key": "<company>|code:… / name:… / file:…" (employees added from the documents),
                    "company": client company ("" = not set: then the company of the ticked documents counts)}]}
<root>\\payroll\\employees.json remembers, per worker_key, the Employee No. and name the user typed, for next months.
The lists are the company's own lines on the Edit Payroll screen (leave types, allowances, deductions, benefits in kind);
a new month starts with the lists of the latest saved month.

How the figures are worked out, per employee, from the daily hours written on the card(s):
    Working Days            days marked "work"
    Days Worked             "work" days with hours > 0
    Overtime 1.5 Times      on each worked "work" day: hours above the normal hours
    OT 1 Time (Rest Day)    "rest" days with hours > 0, counted in days
    OT 2 Times (Holiday)    "holiday" days with hours > 0, counted in days
    Public Holiday          "holiday" days on which the employee did not work
Clock-system reports (columns "Shift Details / Actual", "Late", "EarlyOut", "OverTime / 1.0 … 3.0") already print the
day's figures in decimal hours. On those pages the printed figures are added up as they are (Actual decides the days
worked; Late, EarlyOut and the OverTime columns go to Lateness, Early Departure and Overtime 1/1.5/2/3 Times) and the
normal-hours rule and the rest-day / holiday day counts are not applied, so nothing is paid twice. Each column's sum is
checked against the report's own printed total; a difference is reported. Flat overtime and allowances are left to the user.
Month grids ("Name | 1 | 2 | … | 31 | Remark", one row per worker) are chosen row by row, one row per employee. A tick
(✓ / P / 1) is a day worked with no hours (a normal day: no overtime); hours written in a day cell count as hours; 0, PH,
OFF and leave codes (AL, MC…) are days not worked. Any other mark is reported, never guessed. PH on a day the calendar
has as a working day, and a Remark/Total count that matches neither the days worked nor worked + PH, are reported.
IN/OUT time cards (no hours column, but "IN | OUT", "Time In | Time Out" or "MORNING / IN | MORNING / OUT | AFTERNOON /
IN | …") give the day's hours from the clock times: OUT minus IN. A day with one IN/OUT pair has the break taken off
(plan "break_hours", 1 hour unless the user changes it); a day with several pairs is their sum and no break is taken
off (the gap between the pairs is the break). A time that is unclear, a pair with only one time, or an OUT that is not
later than its IN (a night shift, or an afternoon time written without PM) is reported and the day left out.
Everything else on the Edit Payroll screen (lateness, leave taken, allowances, deductions…) is not on a time card: it
starts at 0 and the user types it in.
"""
from __future__ import annotations

import calendar
import csv
import io
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Callable

from ocr import OcrError

DAY_TYPES = ("work", "rest", "holiday")
PAY_BASES = ("monthly", "daily")

# key, column heading in the payroll file (the names on the Edit Payroll screen), unit shown in the page
FIELDS = [
    ("working_days", "Working Days", "days"),
    ("public_holiday", "Public Holiday", "days"),
    ("days_worked", "Days Worked", "days"),
    ("hours_worked", "Hours of Worked", "hours"),
    ("lateness", "Lateness (Hour)", "hours"),
    ("early_departure", "Early Departure (Hour)", "hours"),
    ("no_pay_hour", "No Pay Hour (Hour)", "hours"),
    ("encashing_leave", "Encashing Leave (Day)", "days"),
    ("ot_1", "Overtime 1 Time (Hour)", "hours"),
    ("ot_1_5", "Overtime 1.5 Times (Hour)", "hours"),
    ("ot_2", "Overtime 2 Times (Hour)", "hours"),
    ("ot_3", "Overtime 3 Times - Overtime on Holiday (Hour)", "hours"),
    ("ot_rest_day", "Overtime 1 Time - Work on Rest Day (Day)", "days"),
    ("ot_holiday", "Overtime 2 Times - Work on Holiday (Day)", "days"),
]
FIELD_KEYS = [k for k, _, _ in FIELDS]

# The lines of the Leave, Allowance, Deduction and Benefit In Kind tables, as set up in Million Payroll.
# kind: (title in the page and the payroll file, heading of the type column, default lines [(name, type)])
LISTS = {
    "leave": ("Leave", "Type", [
        ("Annual Leave", "Pay Leave"), ("Medical Leave", "Pay Leave"), ("Non-Pay Leave", "Non Pay Leave"),
        ("Maternity Leave", "Pay Leave"), ("Paternity Leave", "Pay Leave"), ("Marriage Leave", "Pay Leave"),
        ("Compassionate Leave", "Pay Leave"), ("Hospital Leave", "Pay Leave"), ("Line Shutdown Leave", "Non Pay Leave"),
        ("Examination Leave", "Pay Leave"), ("Absence", "Non Pay Leave"), ("Out of Bound", "Non Pay Leave")]),
    "allowance": ("Allowance", "Wages Type", [
        (n, "Ordinary") for n in ("ADHOC ALLOWANCE", "Attendance Allowance", "Food Allowance", "loan cleaner", "Overtime",
                                  "OVERTIME 1.5", "OVERTIME 2.0", "RECAB 2.O BLC PERMIT", "RECRUITMENT CLAIM",
                                  "SPORTS CLAIM", "SUPERVISIOR ALLOWANCE", "Transport Allowance", "use and claim")]),
    "deduction": ("Deduction", "Special Type", [
        ("Absent Deduction Fine", ""), ("ADVANCE SALARY", ""), ("ALREADY PAID SALARY", ""), ("APPLY/RENEWAL", ""),
        ("EXTRA PAID SALARY", ""), ("Loan Deduction", "Loan"), ("MEAL DEDUCTION", ""), ("MERCHANTRADE CARD", ""),
        ("NON-COMPLETE HRS", ""), ("PENALTY", ""), ("RENTAL CAR", ""), ("rental hostel", ""), ("ZAKAT", "Zakat")]),
    "bik": ("Benefit In Kind (BIK)", "Wages Type", []),
}
LIST_KINDS = list(LISTS)
MAX_FIGURE = 10_000_000


def default_lists() -> dict:
    return {kind: [{"name": n, "type": t} for n, t in lines] for kind, (_, _, lines) in LISTS.items()}

_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_DATE_WITH_MONTH = re.compile(r"^\D*(\d{1,2})\s*[/.\-]\s*(\d{1,2})(?:\s*[/.\-]\s*\d{2,4})?\s*$")
_DATE_YEAR_FIRST = re.compile(r"^\s*\d{4}\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*$")      # 2026-09-16 (door systems)
_FIRST_NUMBER = re.compile(r"^\D*(\d{1,2})\b")
_NOT_WORKED = re.compile(r"^[\s\-–—_./x]*$|^0+([.,]0+)?$", re.IGNORECASE)
_HOURS = re.compile(r"^\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:h|hr|hrs|hour|hours|jam)?\s*$", re.IGNORECASE)
_CLOCK = re.compile(r"^\s*(\d{1,2}):([0-5]\d)\s*$")
# Clock-system report columns (labels compared lower-case, spaces collapsed): printed daily figure -> field
REPORT_HOURS = "shift details / actual"
REPORT_COLUMNS = {"shift details / late": "lateness", "shift details / earlyout": "early_departure",
                  "overtime / 1.0": "ot_1", "overtime / 1.5": "ot_1_5", "overtime / 2.0": "ot_2", "overtime / 3.0": "ot_3"}
REPORT_FLAT = "overtime / flat"
# the report's printed totals (header fields) each column is checked against
REPORT_TOTALS = {"shift details / actual": "total actual", "shift details / late": "total late",
                 "shift details / earlyout": "total earlyout", "overtime / 1.5": "total ot 1.5",
                 "overtime / 2.0": "total ot 2.0"}
# IN/OUT time cards: the last part of a column label ("MORNING / IN" -> "in"), and a clock time as written on them
# (07:55, 7.55, 17:02:10, 5.30 PM). Anything else in an IN/OUT cell is reported, never guessed. A label may give the
# word in Malay and English ("Masuk In", "Masa Keluar / Time Out").
_IN_WORD = r"(?:(?:time|masa|clock)\s*)?(?:in|masuk)"
_OUT_WORD = r"(?:(?:time|masa|clock)\s*)?(?:out|keluar|balik)"
_IN_LABEL = re.compile(rf"^{_IN_WORD}(?:\s+{_IN_WORD})?$")
_OUT_LABEL = re.compile(rf"^{_OUT_WORD}(?:\s+{_OUT_WORD})?$")
_NO_STAMP = re.compile(r"^[\s\-–—_./x]*$", re.IGNORECASE)
_STAMP = re.compile(r"^(\d{1,2})\s*[:.,]\s*([0-5]\d)(?:\s*:\s*([0-5]\d))?\s*(?:([ap])\.?\s*m\.?)?$", re.IGNORECASE)
DEFAULT_BREAK = 1.0
_DATE_LABEL = re.compile(r"date|tarikh|day|hari", re.IGNORECASE)
_HOURS_LABEL = re.compile(r"total|jumlah|hours|jam|hrs", re.IGNORECASE)


# ----------------------------------------------------------------------------------------------------- the month
def parse_month(month: str) -> tuple[int, int]:
    m = _MONTH.match(month or "")
    if not m:
        raise OcrError("BAD_PAYROLL", "Choose a month and a year for the payroll.")
    return int(m.group(1)), int(m.group(2))


def days_in(month: str) -> int:
    year, mon = parse_month(month)
    return calendar.monthrange(year, mon)[1]


def default_plan(month: str) -> dict:
    """A new plan: Sundays are rest days, every other day is a working day, normal day = 8 hours."""
    year, mon = parse_month(month)
    types = {}
    for d in range(1, days_in(month) + 1):
        types[str(d)] = "rest" if date(year, mon, d).weekday() == 6 else "work"
    return {"month": month, "normal_hours": 8, "break_hours": DEFAULT_BREAK, "day_types": types,
            "lists": default_lists(), "employees": []}


def _figure(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= MAX_FIGURE:
        raise OcrError("BAD_PAYROLL", "Figures must be numbers (0 or more).")
    return float(value)


def validate_lists(lists) -> dict:
    """The company's table lines. Missing (a plan saved before the lists existed) -> the defaults."""
    if lists is None:
        return default_lists()
    bad = OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")
    if not isinstance(lists, dict):
        raise bad
    clean = {}
    for kind in LIST_KINDS:
        lines = lists.get(kind, [])
        if not isinstance(lines, list) or len(lines) > 200:
            raise bad
        seen, out = set(), []
        for line in lines:
            if not isinstance(line, dict):
                raise bad
            name, line_type = line.get("name"), line.get("type", "")
            if not isinstance(name, str) or not isinstance(line_type, str) or len(line_type) > 60:
                raise bad
            name = name.strip()
            if not name or len(name) > 80:
                raise OcrError("BAD_PAYROLL", "Each line needs a name (up to 80 characters).")
            if name.lower() in seen:
                raise OcrError("BAD_PAYROLL", f"'{name}' is in the {LISTS[kind][0]} list twice. Use another name.")
            seen.add(name.lower())
            out.append({"name": name, "type": line_type.strip()})
        clean[kind] = out
    return clean


# A document whose pages belong to different workers (a clock-system report printed one worker per page) is chosen page
# by page: the plan then holds "<document id>#p<page>" instead of the document id. A month grid that lists several
# workers (one row each) is chosen row by row: "<document id>#p<page>r<row>" (row counted from 1).
PART = "#p"
_PART_REF = re.compile(r"^(.*)#p(\d+)(?:r(\d+))?$")
_WORKER_LABEL = re.compile(r"^(?:(?:cleaner|employee|worker|staff)\s+)?(?:name|nama)(?:\s*/\s*(?:name|nama))?$"
                           r"|^emp(?:loyee)?\.?\s*(?:code|no\.?|id)$|^no\.?\s*pekerja$|^staff\s*no\.?$", re.IGNORECASE)
_NAME_LABEL = re.compile(r"name|nama", re.IGNORECASE)
_MONTH_TOKEN = re.compile(r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\d{0,4}$", re.IGNORECASE)


def split_part(ref: str) -> tuple[str, int | None, int | None]:
    """"<id>#p3r2" -> (id, 3, 2); "<id>#p3" -> (id, 3, None); "<id>" -> (id, None, None)."""
    m = _PART_REF.match(ref)
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else None
    return ref, None, None


def split_ref(ref: str) -> tuple[str, int | None]:
    """"<id>#p3" (or "<id>#p3r2") -> (id, 3); "<id>" -> (id, None)."""
    base, page, _ = split_part(ref)
    return base, page


def part_suffix(page: int, row: int | None = None) -> str:
    return f"{PART}{page}" + (f"r{row}" if row else "")


def employee_company(employee: dict, company_of_doc: dict[str, str]) -> str:
    """The employee's company: the one set on the employee, else the one company all ticked documents share, else ""."""
    if employee.get("company"):
        return employee["company"]
    found = {company_of_doc.get(split_ref(ref)[0], "") for ref in employee.get("jobs", [])}
    return found.pop() if len(found) == 1 else ""


def worker_parts(pages: list[dict]) -> list[dict]:
    """[{page, label}] when the pages show different workers (Emp Code / Name printed at the top), else []."""
    keys = []
    for p in pages:
        found = [(f["label"], (f["cell"]["value"] or "").strip()) for f in p["header_fields"]
                 if _WORKER_LABEL.match(" ".join(f["label"].split())) and (f["cell"]["value"] or "").strip()]
        keys.append(found)
    if len(pages) < 2 or len({tuple(k) for k in keys if k}) < 2:
        return []
    return [{"page": p["page"], "label": " ".join(v for _, v in k)} for p, k in zip(pages, keys)]


# Month grids: one row per worker and one column per day of the month ("Name | 1 | 2 | … | 31 | Remark"). A day cell
# holds a mark, not hours. Only these marks are understood; anything else is reported, never guessed.
_DAY_LABEL = re.compile(r"^\s*(\d{1,2})\s*$")
_GRID_TOTAL_LABEL = re.compile(r"total|jumlah|remark|catatan", re.IGNORECASE)
GRID_MARKS = {
    "present": {"✓", "✔", "√", "/", "p", "1"},          # worked that day (a normal day, no overtime)
    "absent": {"0", "o"},
    "holiday": {"ph", "p.h", "p.h.", "p/h", "cuti am", "cuti umum"},
    "off": {"off", "ro", "rd", "r/d", "rest", "off day", "off days", "rest day", "ahad"},
    "leave": {"al", "mc", "el", "cl", "ml", "hl", "upl", "npl", "ul", "cuti"},
}
DAY_WORD_MARKS = ("holiday", "off", "leave")      # marks an IN/OUT card may carry instead of times (never "worked")
_MARK_OF = {code: mark for mark, codes in GRID_MARKS.items() for code in codes}


def grid_columns(labels: list[str]) -> dict | None:
    """{"days": {day: label}, "name": label, "total": label | None} when the table has a column for (nearly) every day
    of the month, else None."""
    days: dict[int, str] = {}
    for label in labels:
        m = _DAY_LABEL.match(label)
        if m and 1 <= int(m.group(1)) <= 31 and int(m.group(1)) not in days:
            days[int(m.group(1))] = label
    if len(days) < 28:
        return None
    others = [c for c in labels if c not in days.values()]
    name = next((c for c in others if _NAME_LABEL.search(c)), others[0] if others else None)
    total = next((c for c in others if c != name and _GRID_TOTAL_LABEL.search(c)), None)
    return {"days": days, "name": name, "total": total}


def grid_mark(text: str) -> tuple[str | None, float | None]:
    """A month-grid day cell -> (mark, hours): ("present", None) for a tick, ("hours", 8.0) for hours written, (mark, 0.0)
    for absent / holiday / off / leave, (None, None) for anything not understood."""
    code = " ".join(text.lower().split())
    if code in _MARK_OF:
        mark = _MARK_OF[code]
        return mark, None if mark == "present" else 0.0
    hours = parse_hours(text)
    if hours is None:
        return None, None
    return ("hours", hours) if hours > 0 else ("absent", 0.0)


def _plain(cell: dict | None) -> str:
    """A cell's confirmed text ("" while it is unclear)."""
    return "" if not cell or cell["needs_review"] else (cell["value"] or "").strip()


def document_parts(pages: list[dict]) -> list[dict]:
    """What the payroll can choose separately in one document: [{page, row, label}].
    Each worker's row of a month grid that lists several workers (row counted from 1, label = the name in the row),
    plus the other pages of that document; else each page when the pages show different workers (worker_parts).
    [] = the document is chosen as a whole."""
    rows, grid_pages = [], set()
    for p in pages:
        g = grid_columns(p["column_labels"])
        if g and len(p["rows"]) > 1:
            grid_pages.add(p["page"])
            rows += [{"page": p["page"], "row": r, "label": _plain(row["cells"].get(g["name"])) if g["name"] else ""}
                     for r, row in enumerate(p["rows"], start=1)]
    if not rows:
        return [{**w, "row": None} for w in worker_parts(pages)]
    return rows + [{"page": p["page"], "row": None, "label": " ".join(v for v in printed_worker([p]) if v)}
                   for p in pages if p["page"] not in grid_pages]


# ------------------------------------------------------------------------------- employees made from the documents
def printed_worker(pages: list[dict], row_only: bool = False) -> tuple[str, str]:
    """(code, name) printed for the worker ("" where not printed or still unclear). On a month grid with one row the
    name written in that row comes first. ``row_only``: one worker's row of a grid that lists several workers, so the
    name printed at the top (the first worker's) is not theirs."""
    code = name = ""
    for p in pages:
        g = grid_columns(p["column_labels"])
        if g and g["name"] and len(p["rows"]) == 1:
            name = name or _plain(p["rows"][0]["cells"].get(g["name"]))
    if row_only:
        return "", name
    for p in pages:
        for f in p["header_fields"]:
            label, value = " ".join(f["label"].split()), (f["cell"]["value"] or "").strip()
            if value and _WORKER_LABEL.match(label):
                if _NAME_LABEL.search(label):
                    name = name or value
                else:
                    code = code or value
    return code, name


def name_from_file(filename: str, company: str) -> str:
    """What is left of a file name without the company, month, year and copy numbers:
    "MAJU JAYA ALI SEPT 26 2.jpeg" -> "ALI", "ACME KLC 1 SEPT 2026 (ZURA) (2).jpeg" -> "KLC ZURA"."""
    stem = " ".join(Path(filename).stem.replace("_", " ").split())
    if company and _key(stem).startswith(_key(company)):
        stem = stem[len(" ".join(company.split())):]
    words = [w.strip("()") for w in stem.split()]
    return " ".join(w for w in words if w and not w.isdigit() and not _MONTH_TOKEN.match(w))


_MONTH_OF = {w: n for n, words in enumerate((
    "jan january januari", "feb february februari", "mar mac march", "apr april", "may mei", "jun june",
    "jul july julai", "aug august ogos", "sep sept september", "oct okt october oktober", "nov november",
    "dec dis december disember"), start=1) for w in words.split()}
# a month word, whole ("MARKET" is not March), with the year that may follow it: "SEPT 2026", "SEPT26", "Sep-26", "Sept. 2026"
_MONTH_YEAR = re.compile(r"(?<![a-z])(" + "|".join(sorted(_MONTH_OF, key=len, reverse=True)) + r")\.?"
                         r"(?:\s*[-/']?\s*(\d{4}|\d{2})(?!\d))?(?![a-z])", re.IGNORECASE)
_FULL_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})(?!\d)")
_MONTH_FIELD = re.compile(r"month|bulan|period|tempoh", re.IGNORECASE)
_YEAR_FIELD = re.compile(r"^(?:.*\b)?(?:year|tahun)\b", re.IGNORECASE)


def _year(text: str | None, today: date) -> int | None:
    """A year as written next to a month: 2026, or 26 for 2026. Only within a year of today (so "SEPT 15", the 15th,
    is not taken for 2015)."""
    if not text:
        return None
    year = int(text) + (2000 if len(text) == 2 else 0)
    return year if abs(year - today.year) <= 1 else None


def document_month(file_name: str, pages: list[dict], today: date) -> tuple[str | None, str]:
    """The payroll month a document is for ("2026-09"), from what is printed: the card's Month / Bulan / Period field
    (with its Year / Tahun field) and the file name ("... SEPT 2026 (ALI).jpeg"). A file name counts only with a year
    next to the month, so a worker called Mei or Jun is not a month. A month with no year anywhere is the latest such
    month up to next month. Returns (month, "") or (None, why not): no month found, or two different months."""
    found: set[tuple[int | None, int]] = set()
    year_field = None
    for p in pages:
        for f in p["header_fields"]:
            label, cell = " ".join(f["label"].split()), f["cell"]
            value = "" if cell["needs_review"] else (cell["value"] or "").strip()
            if not value:
                continue
            if _MONTH_FIELD.search(label):
                dates = {(int(y), int(m)) for _, m, y in _FULL_DATE.findall(value) if 1 <= int(m) <= 12}
                found |= dates
                if not dates:
                    found |= {(_year(y, today), _MONTH_OF[w.lower()]) for w, y in _MONTH_YEAR.findall(value)}
            elif _YEAR_FIELD.match(label) and re.fullmatch(r"\d{2}|\d{4}", value):
                year_field = _year(value, today) or year_field
    stem = Path(file_name).stem.replace("_", " ")
    found |= {(_year(y, today), _MONTH_OF[w.lower()]) for w, y in _MONTH_YEAR.findall(stem) if _year(y, today)}
    next_month = (today.year + today.month // 12, today.month % 12 + 1)
    resolved = set()
    for y, m in found:
        if y is None:
            same = {yy for yy, mm in found if yy and mm == m}
            y = next(iter(same)) if len(same) == 1 else year_field or \
                max(yy for yy in (today.year + 1, today.year, today.year - 1) if (yy, m) <= next_month)
        resolved.add(f"{y}-{m:02d}")
    if len(resolved) == 1:
        return resolved.pop(), ""
    if not resolved:
        return None, "no month was found in the file name or on the card"
    return None, "the file name and the card give different months (" + ", ".join(sorted(resolved)) + ")"


def worker_key(company: str, code: str, name: str, file_name: str) -> str:
    """Who a document belongs to, within a company: the printed code, else the printed name, else the file name."""
    who = f"code:{_key(code)}" if code else f"name:{_key(name)}" if name else f"file:{_key(file_name)}"
    return f"{_key(company)}|{who}"


def readable(page: dict) -> bool:
    """Can the payroll work out days from this page: a month grid, a table with a daily hours column, or an IN/OUT
    time card."""
    labels = page["column_labels"]
    return bool(grid_columns(labels) or pick_columns(labels, None)[1] or clock_pairs(labels))


def auto_employees(plan: dict, candidates: list[dict], directory: dict, new_id: Callable[[], str],
                   addable: set[str] | None = None, million: list[dict] | None = None) -> tuple[int, list[str], list[str]]:
    """Add an employee for every worker found in ``candidates`` ([{ref, name, company, pages}]: documents, one page of
    a multi-worker report, or one worker's row of a month grid) that no employee has yet, with their cards ticked.
    Employee No. and name come from ``directory`` (what the user typed in earlier months) when known; the Employee No.
    is never made up: for a worker not known yet it is taken from ``million`` (Million's employee list) only when the
    name read on the card is one employee's whole name there (fill_employee_nos). ``addable``: only these refs may be added (the others only show, by their file names, whose
    cards are already chosen, so a card with no name printed joins its pair). Changes ``plan`` in place. Returns
    (employees added, names of documents left out because no days can be read from them, names of grid rows left out
    because the name in the row is unclear or empty)."""
    taken, whole, in_parts, owner = set(), set(), set(), {}
    for e in plan["employees"]:
        for ref in e["jobs"]:
            base, page = split_ref(ref)
            taken.add(ref)
            (whole if page is None else in_parts).add(base)
            if e.get("worker_key"):
                owner[ref] = e["worker_key"]
    by_key = {e.get("worker_key"): e for e in plan["employees"] if e.get("worker_key")}
    groups: dict[str, dict] = {}
    by_file: dict[str, set[str]] = {}       # company + name left in the file name -> the groups such files went to
    for c in candidates:                    # cards already chosen for an employee made from the files
        if c["ref"] in owner:
            name = name_from_file(c["name"], c["company"])
            if name:
                by_file.setdefault(f"{_key(c['company'])}|{_key(name)}", set()).add(owner[c["ref"]])
    skipped, unnamed = [], []
    # cards with the worker printed on them first, so a card whose printed name is unclear can join its pair below
    order = sorted(range(len(candidates)), key=lambda i: not any(printed_worker(candidates[i]["pages"])))
    for i in order:
        c = candidates[i]
        base, page, row = split_part(c["ref"])
        if c["ref"] in taken or base in whole or (page is None and base in in_parts):
            continue                                              # already chosen for someone (whole or in part)
        if addable is not None and c["ref"] not in addable:
            continue
        if not any(readable(p) for p in c["pages"] if p["rows"]):
            skipped.append(c["name"])
            continue
        code, name = printed_worker(c["pages"], row_only=row is not None)
        if row is not None and not name:
            unnamed.append(c["name"])                             # whose row is it? the user ticks it by hand
            continue
        file_name = name_from_file(c["name"], c["company"])
        file_id = f"{_key(c['company'])}|{_key(file_name)}"
        key = worker_key(c["company"], code, name, file_name)
        if not (code or name) and len(by_file.get(file_id, ())) == 1:
            key = next(iter(by_file[file_id]))           # nothing printed: the worker whose other card has this file name
        group = groups.setdefault(key, {"refs": [], "name": name or file_name, "code": code, "first": i,
                                        "company": c["company"], "on_card": bool(name)})
        group["refs"].append(c["ref"])
        group["first"] = min(group["first"], i)
        if file_name:
            by_file.setdefault(file_id, set()).add(key)
    added, named_on_card = 0, set()
    for key, g in sorted(groups.items(), key=lambda kv: kv[1]["first"]):    # employees in the files' order
        g["refs"].sort(key=[c["ref"] for c in candidates].index)
        if key in by_key:                                         # this worker is already an employee: add the cards
            by_key[key]["jobs"] += [r for r in g["refs"] if r not in by_key[key]["jobs"]]
            continue
        known = directory.get(key) or {}
        plan["employees"].append({"id": new_id(), "emp_no": known.get("emp_no", ""), "name": known.get("name") or g["name"],
                                  "jobs": g["refs"], "hours_column": None, "overrides": {}, "entries": {},
                                  "zakat": 0.0, "levy": 0.0, "message": "", "worker_key": key,
                                  "company": g["company"] or "", "pay_basis": known.get("pay_basis") or "monthly",
                                  "basic_rate": float(known.get("basic_rate") or 0.0)})
        if g["on_card"] and not known.get("name"):
            named_on_card.add(plan["employees"][-1]["id"])
        added += 1
    if million:
        fill_employee_nos(plan, million, named_on_card)
    return added, skipped, unnamed


def fill_employee_nos(plan: dict, million: list[dict], ids: set[str]) -> int:
    """Give the employees ``ids`` (just made from the files, named as read on their card) Million's Employee No. when
    the name on the card is the whole name of exactly one employee in Million's list (upper/lower case and spacing
    aside), nobody in the plan has that number, and no other employee in the plan has that name. Such a number is
    marked ``emp_no_million`` so the page can say where it came from. A name that only partly fits is offered, not
    filled in (suggest_employee_nos). Returns how many were filled in."""
    in_million: dict[str, list[str]] = {}
    for m in million:
        if _key(m.get("name", "")):
            in_million.setdefault(_key(m["name"]), []).append(m["emp_no"])
    taken = {e["emp_no"].strip().casefold() for e in plan["employees"] if e["emp_no"].strip()}
    in_plan: dict[str, int] = {}
    for e in plan["employees"]:
        in_plan[_key(e["name"])] = in_plan.get(_key(e["name"]), 0) + 1
    filled = 0
    for e in plan["employees"]:
        fits = in_million.get(_key(e["name"]), [])
        if e["id"] in ids and not e["emp_no"].strip() and len(fits) == 1 and in_plan[_key(e["name"])] == 1 \
                and fits[0].casefold() not in taken:
            e["emp_no"] = e["emp_no_million"] = fits[0]
            filled += 1
    return filled


NEW_NO_LETTERS = 7      # how much of the company name starts an Employee No. made by Table Reader


def company_prefix(company: str) -> str:
    """What a new Employee No. of this company starts with: the first 7 letters and digits of its name, in capitals,
    without spaces or signs ("MAJU JAYA" -> "MAJUJAY")."""
    return "".join(ch for ch in (company or "").upper() if ch.isalnum())[:NEW_NO_LETTERS]


def new_employee_nos(plan: dict, companies: dict[str, str], used: set[str]) -> dict[str, str]:
    """A new Employee No. for each employee in ``companies`` ({employee id: company}) who has none: the company's
    letters and the next free number, three digits ("MAJUJAY001", then "MAJUJAY002"). The next number is one more than
    the highest such number in the plan or in ``used`` (every number known elsewhere: other months, earlier months'
    workers, Million's list), so a number is never given twice. Nobody gets one without a company.
    Returns {employee id: Employee No.}; the plan is not changed."""
    taken = [no.strip() for no in used] + [e["emp_no"].strip() for e in plan["employees"]]
    last: dict[str, int] = {}
    out = {}
    for e in plan["employees"]:
        prefix = company_prefix(companies.get(e["id"], ""))
        if e["id"] not in companies or e["emp_no"].strip() or not prefix:
            continue
        if prefix not in last:
            numbers = [re.fullmatch(re.escape(prefix) + r"(\d+)", no, re.IGNORECASE) for no in taken]
            last[prefix] = max((int(m.group(1)) for m in numbers if m), default=0)
        last[prefix] += 1
        out[e["id"]] = f"{prefix}{last[prefix]:03d}"
    return out


def remember_employees(plan: dict, directory: dict) -> bool:
    """Keep each employee's Employee No., name, pay basis and basic rate for next month (by worker_key). Returns True
    if anything changed."""
    changed = False
    for e in plan["employees"]:
        key = e.get("worker_key")
        if key and e["emp_no"]:
            entry = {"emp_no": e["emp_no"], "name": e["name"]}
            if e.get("basic_rate"):
                entry.update(pay_basis=e.get("pay_basis") or "monthly", basic_rate=e["basic_rate"])
            if directory.get(key) != entry:
                directory[key] = entry
                changed = True
    return changed


def validate_plan(plan, known_jobs: set[str]) -> dict:
    """Clean copy of a plan from the page, or OcrError. Every document may belong to one employee only."""
    bad = OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")
    if not isinstance(plan, dict):
        raise bad
    month = plan.get("month")
    n_days = days_in(month if isinstance(month, str) else "")
    hours = plan.get("normal_hours")
    if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not 1 <= hours <= 24:
        raise OcrError("BAD_PAYROLL", "Normal hours per day must be a number from 1 to 24.")
    break_hours = plan.get("break_hours", DEFAULT_BREAK)            # a plan saved before IN/OUT cards: 1 hour
    if isinstance(break_hours, bool) or not isinstance(break_hours, (int, float)) or not 0 <= break_hours <= 5:
        raise OcrError("BAD_PAYROLL", "The break must be a number of hours from 0 to 5.")
    types = plan.get("day_types")
    if not isinstance(types, dict) or set(types) != {str(d) for d in range(1, n_days + 1)} \
            or any(v not in DAY_TYPES for v in types.values()):
        raise bad
    lists = validate_lists(plan.get("lists"))
    employees, seen_ids, used_jobs, whole, in_parts = [], set(), {}, set(), set()
    whole_pages, row_pages = set(), set()           # (document, page) chosen as a page / through one of its rows
    for e in plan.get("employees") or []:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not _ID.match(e["id"]) or e["id"] in seen_ids:
            raise bad
        seen_ids.add(e["id"])
        emp_no, name = e.get("emp_no", ""), e.get("name", "")
        if not isinstance(emp_no, str) or not isinstance(name, str) or len(emp_no) > 100 or len(name) > 100:
            raise bad
        jobs = e.get("jobs") or []
        if not isinstance(jobs, list) or any(not isinstance(j, str) for j in jobs):
            raise bad
        for j in jobs:
            if j not in known_jobs:
                raise OcrError("JOB_NOT_FOUND", "One of the chosen documents was not found. It may have been moved or deleted.")
            base, page, row = split_part(j)
            # a page or row can be chosen once; a whole document cannot be chosen together with any of its pages or
            # rows, nor a whole page together with one of its rows
            if j in used_jobs or (page is None and base in in_parts) or (page is not None and base in whole) \
                    or (row is None and (base, page) in row_pages) or (row is not None and (base, page) in whole_pages):
                raise OcrError("BAD_PAYROLL", "A document can belong to one employee only. Untick it from the other employee first.")
            used_jobs[j] = e["id"]
            (whole if page is None else in_parts).add(base)
            if page is not None:
                (whole_pages if row is None else row_pages).add((base, page))
        column = e.get("hours_column")
        if column is not None and (not isinstance(column, str) or len(column) > 200):
            raise bad
        overrides = {}
        for key, value in (e.get("overrides") or {}).items():
            if key not in FIELD_KEYS or isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 100000:
                raise OcrError("BAD_PAYROLL", "Figures must be numbers (0 or more).")
            overrides[key] = float(value)
        entries_in = e.get("entries") or {}
        if not isinstance(entries_in, dict) or any(not isinstance(v, dict) for v in entries_in.values()):
            raise bad
        entries = {}
        for kind in LIST_KINDS:
            names = {line["name"] for line in lists[kind]}
            # a figure for a line that was removed from the list is dropped; zeros are not stored
            entries[kind] = {n: _figure(v) for n, v in (entries_in.get(kind) or {}).items() if n in names and _figure(v)}
        message = e.get("message", "")
        if not isinstance(message, str) or len(message) > 2000:
            raise OcrError("BAD_PAYROLL", "The message is too long (2000 characters at most).")
        key = e.get("worker_key")
        if key is not None and (not isinstance(key, str) or len(key) > 300):
            raise bad
        basis = e.get("pay_basis") or "monthly"                     # how the Basic Rate is meant: per month or per day
        if basis not in PAY_BASES:
            raise bad
        company = e.get("company") or ""
        if not isinstance(company, str) or len(company) > 80:
            raise bad
        employees.append({"id": e["id"], "emp_no": emp_no.strip(), "name": name.strip(), "jobs": list(jobs),
                          "hours_column": column or None, "overrides": overrides, "entries": entries,
                          "zakat": _figure(e.get("zakat", 0)), "levy": _figure(e.get("levy", 0)), "message": message,
                          "pay_basis": basis, "basic_rate": _figure(e.get("basic_rate") or 0),
                          "company": " ".join(company.split()), **({"worker_key": key} if key else {}),
                          # filled in from Million's list (fill_employee_nos): kept until the number is changed
                          **({"emp_no_million": emp_no.strip()} if emp_no.strip() and e.get("emp_no_million") == emp_no.strip() else {}),
                          # made by Table Reader (new_employee_nos): the same
                          **({"emp_no_new": emp_no.strip()} if emp_no.strip() and e.get("emp_no_new") == emp_no.strip() else {})})
    return {"month": month, "normal_hours": float(hours), "break_hours": float(break_hours), "day_types": dict(types),
            "lists": lists, "employees": employees}


# ---------------------------------------------------------------------------------------- reading days from tables
def parse_hours(value: str | None) -> float | None:
    """Hours written for a day: 0 for a dash/blank/0, a number for 9 / 8.5 / 9h / 8:30, None if it cannot be read as hours."""
    text = (value or "").strip()
    if _NOT_WORKED.match(text):
        return 0.0
    m = _CLOCK.match(text)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60
    m = _HOURS.match(text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def parse_day(value: str | None, month_number: int) -> tuple[int | None, str | None]:
    """The day of the month in a Date cell ("16", "16/9", "2026-09-16"). Returns (day, problem). A date for another
    month is a problem."""
    text = (value or "").strip()
    iso = _DATE_YEAR_FIRST.match(text)
    m = _DATE_WITH_MONTH.match(text)
    if iso or m:
        day, mon = (int(iso.group(2)), int(iso.group(1))) if iso else (int(m.group(1)), int(m.group(2)))
        if mon != month_number:
            return None, f"the date {text} is not in the chosen month"
        return day, None
    m = _FIRST_NUMBER.match(text)
    if m:
        return int(m.group(1)), None
    return None, "the date could not be read"


def pick_columns(labels: list[str], hours_column: str | None) -> tuple[str | None, str | None]:
    date_col = next((c for c in labels if _DATE_LABEL.search(c)), labels[0] if labels else None)
    if hours_column and hours_column in labels:
        return date_col, hours_column
    actual = next((c for c in labels if _key(c) == REPORT_HOURS), None)
    if actual:                                                      # clock-system report: the hours actually worked
        return date_col, actual
    candidates = [c for c in labels if _HOURS_LABEL.search(c) and c != date_col]
    return date_col, (candidates[-1] if candidates else None)


def _key(label: str) -> str:
    return " ".join((label or "").split()).casefold()


def clock_pairs(labels: list[str]) -> list[tuple[str, str]]:
    """The (IN column, OUT column) pairs of an IN/OUT time card, in the card's order: "IN | OUT", "Time In | … | Time
    Out", or one pair per group ("MORNING / IN | MORNING / OUT | AFTERNOON / IN | AFTERNOON / OUT"). The word may be
    given twice ("Masuk In", "Masa Masuk / Time In")."""
    pairs, waiting = [], {}
    for label in labels:
        parts, side = _key(label).split(" / "), set()
        while parts and (_IN_LABEL.match(parts[-1]) or _OUT_LABEL.match(parts[-1])):
            side.add("in" if _IN_LABEL.match(parts.pop()) else "out")
        group = " / ".join(parts)
        if side == {"in"}:
            waiting[group] = label
        elif side == {"out"} and group in waiting:
            pairs.append((waiting.pop(group), label))
    return pairs


def parse_clock(value: str | None) -> float | None:
    """A clock time written on a card -> minutes after midnight: 07:55, 7.55, 17:02:10, 5.30 PM. None if it is not one."""
    m = _STAMP.match((value or "").strip())
    if not m:
        return None
    hour, half = int(m.group(1)), (m.group(4) or "").lower()
    if half:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if half == "p" else 0)
    elif hour > 23:
        return None
    return hour * 60 + int(m.group(2)) + int(m.group(3) or 0) / 60


def _clock_day(cells: dict, pairs: list[tuple[str, str]], break_hours: float, where: str, day: int, name: str,
               issues: list[dict]) -> dict:
    """One day of an IN/OUT time card: the hours between each IN and its OUT, added up. One pair: the break is taken
    off. Several pairs: no break (the gap between them is the break). Only one IN and one OUT in a later pair (morning
    IN, overtime OUT: the worker clocked twice): one span, the break taken off. A day word instead of times (OFF, PH,
    CUTI, MC: see DAY_WORD_MARKS) marks the day as on a month grid. Anything unclear leaves the day out."""
    def unclear(text: str) -> dict:
        issues.append({"kind": "unclear", "job": name, "text": f"{where}, day {day}: {text}"})
        return {"hours": None, "status": "unclear", "source": where, "printed": None}

    if any(cells[c]["needs_review"] for pair in pairs for c in pair):
        return unclear("an IN or OUT time is still unclear. Check the yellow cell in the document.")
    stamps = [((cells[i]["value"] or "").strip(), (cells[o]["value"] or "").strip()) for i, o in pairs]
    filled = [(k, side) for k, pair in enumerate(stamps) for side, text in zip(("in", "out"), pair)
              if not _NO_STAMP.match(text)]
    texts = [stamps[k][side == "out"] for k, side in filled]
    if texts and all(parse_clock(t) is None for t in texts):
        for words in (" ".join(texts), "".join(texts)):                   # "OFF" | "DAY", or "O" | "F" | "F"
            mark, _ = grid_mark(words)
            if mark in DAY_WORD_MARKS:
                return {"hours": 0.0, "status": "ok", "source": where, "printed": None, "mark": mark,
                        "code": " ".join(texts)}
    if len(filled) == 2 and filled[0][1] == "in" and filled[1][1] == "out" and filled[0][0] < filled[1][0]:
        stamps = [(stamps[filled[0][0]][0], stamps[filled[1][0]][1])]   # clocked IN once and OUT once: one span

    spans, written = [], []
    for tin, tout in stamps:
        has_in, has_out = not _NO_STAMP.match(tin), not _NO_STAMP.match(tout)
        if not has_in and not has_out:
            continue
        if not has_out:
            return unclear(f"there is an IN time ({tin}) but no OUT time, so the hours cannot be worked out. "
                           "Complete it in the document.")
        if not has_in:
            return unclear(f"there is an OUT time ({tout}) but no IN time, so the hours cannot be worked out. "
                           "Complete it in the document.")
        start, end = parse_clock(tin), parse_clock(tout)
        if start is None or end is None:
            return unclear(f"'{tin if start is None else tout}' is not a clock time (such as 07:55 or 5.30 PM). "
                           "Correct it in the document.")
        if end <= start:
            return unclear(f"OUT {tout} is not later than IN {tin}. If it is an afternoon time, write it as 17.00 or "
                           "5.00 PM in the document. A shift that ends the next day cannot be worked out: type the "
                           "figures yourself.")
        spans.append((end - start) / 60)
        written.append(f"{tin} - {tout}")
    if not spans:
        return {"hours": 0.0, "status": "ok", "source": where, "printed": None}        # no times: not worked
    taken = break_hours if len(spans) == 1 and spans[0] > break_hours else 0.0      # a day shorter than the break keeps its hours
    hours = round(sum(spans) - taken, 2)
    return {"hours": hours, "status": "ok", "source": where, "printed": None, "code": ", ".join(written),
            "clock": {"hours": hours, "break": taken, "pairs": len(spans)}}


def _check_report_totals(page: dict, where: str, name: str, issues: list[dict]) -> None:
    """Each printed-figure column, added up, must equal the total printed on the report. Unclear cells are already
    reported, so a column with one is not checked; an unreadable printed total is not used."""
    totals = {_key(f["label"]): f["cell"] for f in page["header_fields"]}
    for label in page["column_labels"]:
        total_cell = totals.get(REPORT_TOTALS.get(_key(label), "\0"))
        if total_cell is None or total_cell["needs_review"]:
            continue
        printed = parse_hours(total_cell["value"]) if (total_cell["value"] or "").strip() else None
        if printed is None and (total_cell["value"] or "").strip():
            printed = _number_or_none(total_cell["value"])
        cells = [row["cells"][label] for row in page["rows"]]
        if printed is None or any(c["needs_review"] for c in cells):
            continue
        values = [parse_hours(c["value"]) for c in cells]
        if any(v is None for v in values):
            continue
        if abs(sum(values) - printed) > 0.005:
            issues.append({"kind": "total", "job": name, "text": f"{where}: the {label} column adds up to "
                           f"{sum(values):.2f} but the report's printed total is {printed:.2f}. Check that column in the "
                           "document."})


def _number_or_none(text: str) -> float | None:
    m = re.fullmatch(r"\s*(\d{1,6}(?:[.,]\d{1,2})?)\s*", text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def read_days(docs: list[tuple[str, list[dict]]], n_days: int, month_number: int, hours_column: str | None,
              break_hours: float = DEFAULT_BREAK):
    """Daily hours from an employee's documents. ``docs`` is [(document name, merged pages)].
    Returns (days, issues): days maps day -> {"hours": float | None, "status": "ok" | "unclear" | "conflict",
    "source": text, "printed": {field: hours} | None (clock-system report figures for that day),
    "mark": None | "present" | "hours" | "absent" | "holiday" | "off" | "leave" (month grids), "code": what was written,
    "clock": {"hours", "break", "pairs"} on an IN/OUT time card (how the hours were worked out)}.
    A month-grid tick is a day worked with no hours ("present", hours None)."""
    days: dict[int, dict] = {}
    issues: list[dict] = []
    for name, pages in docs:
        for page in pages:
            where = f"{name}" + (f", page {page['page']}" if len(pages) > 1 else "")
            grid = grid_columns(page["column_labels"])
            if grid:                                                # month grid: rows = workers, columns = days
                _read_grid(page, grid, where, name, n_days, days, issues)
                continue
            date_col, hours_col = pick_columns(page["column_labels"], hours_column)
            report = {c: REPORT_COLUMNS[_key(c)] for c in page["column_labels"] if _key(c) in REPORT_COLUMNS}
            # IN/OUT time card; on a card that also has a Total column, the times count on days the Total is left empty
            pairs = [] if report and hours_col else clock_pairs(page["column_labels"])
            if hours_col is None and not pairs:
                issues.append({"kind": "column", "text": f"{where}: no column with the daily hours was found. "
                                                         "Choose it in the 'Hours column' list.", "job": name})
                continue
            others = [c for c in page["column_labels"] if c not in (date_col, hours_col)] if hours_col and not pairs \
                and not report else []
            if report:
                _check_report_totals(page, where, name, issues)
                flat = next((c for c in page["column_labels"] if _key(c) == REPORT_FLAT), None)
                if flat and any(parse_hours(row["cells"][flat]["value"]) or row["cells"][flat]["needs_review"]
                                for row in page["rows"]):
                    issues.append({"kind": "flat", "job": name, "text": f"{where}: the report has Flat overtime. "
                                   "Table Reader does not add it: type it in the right Million Payroll field yourself."})
            for r, row in enumerate(page["rows"], start=1):
                cells = row["cells"]
                dcell = cells[date_col]
                hcell = cells[hours_col] if hours_col else None
                stamps = [cells[c] for pair in pairs for c in pair]
                timed = ([hcell] if hcell else []) + stamps
                if dcell["needs_review"] or not (dcell["value"] or "").strip():
                    if any(c["value"] or c["needs_review"] or (c["raw_text"] or "").strip() for c in timed):
                        issues.append({"kind": "unclear", "text": f"{where}, row {r}: the date is unclear, so its hours "
                                                                  "were left out. Fix the date in the document.", "job": name})
                    continue
                day, problem = parse_day(dcell["value"], month_number)
                if day is None or not 1 <= day <= n_days:
                    if any(not _NO_STAMP.match((c["value"] or "").strip()) for c in stamps) or \
                            hcell and (hcell["value"] or "").strip() and parse_hours(hcell["value"]):
                        issues.append({"kind": "date", "text": f"{where}, row {r}: " + (problem or f"day {day} is not in this month")
                                       + ", so its hours were left out.", "job": name})
                    continue
                written = hcell is not None and (hcell["needs_review"] or bool((hcell["value"] or "").strip()))
                if pairs and not written:                       # no Total written that day: the IN/OUT times
                    _put_day(days, day, _clock_day(cells, pairs, break_hours, where, day, name, issues), name, issues)
                    continue
                if not written and any(cells[c]["needs_review"] or parse_clock(cells[c]["value"]) is not None
                                       for c in others):
                    # the Total is empty but the row holds times (or yellow cells) in columns not known as IN/OUT:
                    # empty does not mean "not worked" here
                    issues.append({"kind": "unclear", "job": name, "text": f"{where}, day {day}: the {hours_col} column "
                                   "is empty but other columns of the row have times or yellow cells. Type the hours in the "
                                   f"{hours_col} column of the document."})
                    _put_day(days, day, {"hours": None, "status": "unclear", "source": where, "printed": None}, name, issues)
                    continue
                if hcell["needs_review"]:
                    entry = {"hours": None, "status": "unclear", "source": where}
                else:
                    hours = parse_hours(hcell["value"])
                    entry = {"hours": hours, "status": "ok" if hours is not None else "unclear", "source": where}
                    if hours is None:
                        issues.append({"kind": "unclear", "text": f"{where}, day {day}: '{hcell['value']}' is not a number "
                                                                  "of hours. Correct it in the document.", "job": name})
                if entry["status"] == "unclear" and hcell["needs_review"]:
                    issues.append({"kind": "unclear", "text": f"{where}, day {day}: the hours are still unclear. Check the "
                                                              "yellow cell in the document.", "job": name})
                entry["printed"] = None
                if report:
                    printed = {}
                    for col, field in report.items():
                        c = cells[col]
                        value = None if c["needs_review"] else parse_hours(c["value"])
                        if value is None:
                            entry["status"] = "unclear"
                            issues.append({"kind": "unclear", "job": name, "text": f"{where}, day {day}: the {col} "
                                           "figure is unclear or not a number of hours. Check it in the document."})
                        else:
                            printed[field] = printed.get(field, 0.0) + value
                    entry["printed"] = printed
                _put_day(days, day, entry, name, issues)
    return days, issues


def _put_day(days: dict, day: int, entry: dict, name: str, issues: list[dict]) -> None:
    """Record a day. The same day on two cards with the same answer counts once; different answers are a conflict."""
    entry.setdefault("mark", None)
    entry.setdefault("code", None)
    entry.setdefault("printed", None)
    if day not in days:
        days[day] = entry
        return
    old = days[day]
    if old["status"] == "ok" and entry["status"] == "ok" and old["hours"] == entry["hours"] \
            and old["printed"] == entry["printed"] and old["mark"] == entry["mark"]:
        return
    days[day] = {"hours": None, "status": "conflict", "source": f"{old['source']} / {entry['source']}", "printed": None,
                 "mark": None, "code": None}
    issues.append({"kind": "conflict", "text": f"Day {day} appears more than once ({old['source']} and "
                                               f"{entry['source']}). It was left out until you fix it.", "job": name})


def _read_grid(page: dict, g: dict, where: str, name: str, n_days: int, days: dict, issues: list[dict]) -> None:
    """One worker's row of a month grid: each day column holds a mark (see GRID_MARKS) or hours."""
    if len(page["rows"]) != 1:
        issues.append({"kind": "column", "job": name, "text": f"{where}: this sheet lists {len(page['rows'])} workers. "
                                                              "Tick each worker's own row instead of the whole file."})
        return
    cells = page["rows"][0]["cells"]
    worked = holidays = 0
    unclear = False
    for day, label in sorted(g["days"].items()):
        cell = cells[label]
        text = (cell["value"] or "").strip()
        if day > n_days:
            if cell["needs_review"] or text:
                issues.append({"kind": "date", "job": name, "text": f"{where}: day {day} is not in this month, so its "
                                                                    "mark was left out."})
            continue
        if cell["needs_review"]:
            unclear = True
            issues.append({"kind": "unclear", "job": name, "text": f"{where}, day {day}: the mark is still unclear. "
                                                                   "Check the yellow cell in the document."})
            _put_day(days, day, {"hours": None, "status": "unclear", "source": where, "printed": None}, name, issues)
            continue
        if not text:
            continue                                                # no entry: counted (and reported) as missing
        mark, hours = grid_mark(text)
        if mark is None:
            unclear = True
            issues.append({"kind": "unclear", "job": name, "text": f"{where}, day {day}: '{text}' is not a mark Table "
                           "Reader knows (✓, 0, PH, OFF, AL, MC or hours). Correct it in the document."})
            _put_day(days, day, {"hours": None, "status": "unclear", "source": where, "printed": None}, name, issues)
            continue
        worked += mark == "present" or (mark == "hours" and hours > 0)
        holidays += mark == "holiday"
        _put_day(days, day, {"hours": hours, "status": "ok", "source": where, "printed": None, "mark": mark,
                             "code": text}, name, issues)
    # the sheet's own count of days (Remark / Total), when it is a plain number: a check, never a source of figures.
    # Some sheets count public holidays as days, so either count is accepted.
    total = _plain(cells.get(g["total"])) if g["total"] else ""
    if not unclear and re.fullmatch(r"\d{1,2}", total) and int(total) not in (worked, worked + holidays):
        issues.append({"kind": "total", "job": name, "text": f"{where}: {worked} days are marked as worked "
                       f"({worked + holidays} with public holidays), but the sheet's {g['total']} column says {total}. "
                       "Check the marks in the document."})


# --------------------------------------------------------------------------------------------------- calculation
def calculate(plan: dict, docs: list[tuple[str, list[dict]]], employee: dict, million: dict | None = None) -> dict:
    """The month-end figures for one employee, the per-day working, and everything that needs the user's attention."""
    n_days = days_in(plan["month"])
    _, month_number = parse_month(plan["month"])
    normal = plan["normal_hours"]
    days, issues = read_days(docs, n_days, month_number, employee.get("hours_column"),
                             plan.get("break_hours", DEFAULT_BREAK))
    values = {k: 0.0 for k in FIELD_KEYS}
    rows = []
    missing, ph_on_workday, leave = [], [], []
    for d in range(1, n_days + 1):
        kind = plan["day_types"][str(d)]
        entry = days.get(d)
        hours = entry["hours"] if entry else None
        status = entry["status"] if entry else "missing"
        printed = entry.get("printed") if entry else None
        mark = entry.get("mark") if entry else None
        if kind == "work":
            values["working_days"] += 1
        if status == "ok" and printed is not None:
            # clock-system report: the overtime is already split into its rates by the clock system
            for field, value in printed.items():
                values[field] += value
            if hours > 0 and kind == "work":
                values["days_worked"] += 1
            elif hours == 0 and kind == "holiday":
                values["public_holiday"] += 1
        elif status == "ok":
            # a month-grid tick is a day worked with no hours written: a normal day, no overtime
            if (hours is not None and hours > 0) or mark == "present":
                if kind == "work":
                    values["days_worked"] += 1
                    if hours is not None:
                        values["ot_1_5"] += max(0.0, hours - normal)
                elif kind == "rest":
                    values["ot_rest_day"] += 1
                else:
                    values["ot_holiday"] += 1
            elif kind == "holiday":
                values["public_holiday"] += 1
            if mark == "holiday" and kind == "work":
                ph_on_workday.append(d)
            elif mark == "leave":
                leave.append(f"{d} ({entry['code']})")
        elif status == "missing" and kind != "rest":
            missing.append(d)
            if kind == "holiday":
                values["public_holiday"] += 1                       # no entry on a public holiday: not worked
        rows.append({"day": d, "type": kind, "hours": hours, "status": status, "code": entry.get("code") if entry else None,
                     "printed": {k: v for k, v in (printed or {}).items() if v} or None,
                     "clock": entry.get("clock") if entry else None})
    if missing and docs:
        issues.append({"kind": "missing", "text": "No entry found for day " + _ranges(missing) + " in the chosen "
                       "documents. These days were counted as not worked: add the other card if there is one.", "job": None})
    if ph_on_workday:
        issues.append({"kind": "daytype", "job": None, "text": "The card marks day " + _ranges(ph_on_workday) + " as a "
                       "public holiday (PH), but the calendar above has it as a working day. If it is a public holiday, "
                       "click it in the calendar until it is yellow."})
    if leave:
        issues.append({"kind": "leave", "job": None, "text": "The card marks leave on day " + ", ".join(leave) + ". "
                       "Type the leave in the Leave table if Million Payroll should count it."})
    if not docs:
        issues.append({"kind": "nodocs", "text": "No document chosen for this employee yet.", "job": None})
    if not (employee.get("emp_no") or "").strip():
        issues.append({"kind": "empno", "text": "Employee No. is empty. Type it exactly as in Million Payroll.", "job": None})
    complete = not any(i["kind"] in ("unclear", "conflict", "column", "missing", "nodocs", "date", "total", "flat",
                                     "daytype") for i in issues)
    final = {}
    for key in FIELD_KEYS:
        edited = key in employee.get("overrides", {})
        final[key] = {"value": employee["overrides"][key] if edited else values[key], "computed": values[key], "edited": edited}
    basis, rate, source = pay_terms(employee, million)
    known = {k: million[k] for k in ("pay_basis", "basic_rate", "branch") if million and million.get(k)} or None
    return {"id": employee["id"], "emp_no": employee.get("emp_no", ""), "name": employee.get("name", ""), "values": final,
            "entries": employee.get("entries") or {}, "zakat": employee.get("zakat", 0.0), "levy": employee.get("levy", 0.0),
            "message": employee.get("message", ""), "days": rows, "issues": issues, "complete": complete,
            "pay_basis": basis, "basic_rate": rate, "rate_source": source, "million": known,
            "pay": pay_preview(basis, rate, {k: v["value"] for k, v in final.items()}, employee.get("entries") or {})}


# Million Payroll's own overtime tables ("Overtime Table for Monthly Pay" / "for Daily Pay"), as set up in Million:
# what one hour or one day of each overtime line is worth, from the Basic Rate. A month has 26 work days of 8 hours
# there (its Work Table). If the office changes those tables in Million, these must follow.
MONTH_DAYS, DAY_HOURS = 26, 8
OT_LINES = [("ot_1", "Overtime 1.0", "hour", 1.0), ("ot_1_5", "Overtime 1.5", "hour", 1.5), ("ot_2", "Overtime 2.0", "hour", 2.0),
            ("ot_3", "Overtime 3.0", "hour", 3.0), ("ot_rest_day", "Rest Day", "day", 2.0), ("ot_holiday", "Holiday Day", "day", 3.0)]


def pay_terms(employee: dict, million: dict | None) -> tuple[str, float, str | None]:
    """(pay basis, Basic Rate, where they come from). What the user typed for the employee counts; while no rate is
    typed, the Pay Basis and Basic Rate of the employee in Million's imported list are used ("million")."""
    rate = float(employee.get("basic_rate") or 0.0)
    if rate:
        return employee.get("pay_basis") or "monthly", rate, "typed"
    if million and million.get("basic_rate") and million.get("pay_basis") in PAY_BASES:
        return million["pay_basis"], float(million["basic_rate"]), "million"
    return employee.get("pay_basis") or "monthly", 0.0, None


def pay_preview(basis: str, rate: float, values: dict, entries: dict) -> dict | None:
    """What Million Payroll should pay before EPF, SOCSO and tax, worked out the way Million's own tables do it; None
    while there is no Basic Rate.
    Basic pay: Daily = rate x Days Worked; Monthly = the rate (absence, lateness and unpaid leave are not taken off).
    Overtime: per hour, a day's pay / 8 x 1, 1.5, 2 or 3; per Rest Day worked, a day's pay x 2; per Holiday Day worked,
    a day's pay x 3. A day's pay = the daily rate, or the monthly rate / 26.
    Allowances and deductions are the amounts typed in their tables."""
    if not rate:
        return None
    day = rate if basis == "daily" else rate / MONTH_DAYS
    basic = round(rate * values["days_worked"], 2) if basis == "daily" else round(rate, 2)
    lines = []
    for key, label, unit, times in OT_LINES:
        if values.get(key):
            each = (day / DAY_HOURS if unit == "hour" else day) * times
            lines.append({"key": key, "label": label, "unit": unit, "quantity": values[key], "each": round(each, 4),
                          "amount": round(each * values[key], 2)})
    overtime = round(sum(line["amount"] for line in lines), 2)
    allowances = round(sum((entries.get("allowance") or {}).values()), 2)
    deductions = round(sum((entries.get("deduction") or {}).values()), 2)
    return {"basic": basic, "lines": lines, "overtime": overtime, "allowances": allowances, "deductions": deductions,
            "total": round(basic + overtime + allowances - deductions, 2)}


DAILY_COUNTS = [("days_worked", "Days Worked"), ("working_days", "Working Days"), ("public_holiday", "Public Holiday not worked (days)"),
                ("ot_rest_day", "Rest day worked (days)"), ("ot_holiday", "Public holiday worked (days)"),
                ("ot_1", "Overtime 1.0 (hours)"), ("ot_1_5", "Overtime 1.5 (hours)"), ("ot_2", "Overtime 2.0 (hours)"),
                ("ot_3", "Overtime 3.0 (hours)")]


def build_basic_pay_csv(results: list[dict], companies: list[str]) -> str:
    """The pay table: one row per employee with the pay basis and Basic Rate in force (typed, or from Million), the
    counts from the time cards, and the pay preview (basic pay, each overtime line, allowances, deductions, total;
    empty while there is no rate). ``companies`` in the order of ``results``. UTF-8 text (the caller adds the BOM)."""
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(["Company", "Employee No.", "Name", "Pay basis", "Basic Rate (RM)", "Rate from", "Days Worked", "Basic pay (RM)"]
                    + [f"{label} pay (RM)" for _, label, _, _ in OT_LINES]
                    + ["Overtime pay (RM)", "Allowances (RM)", "Deductions (RM)", "Estimated pay before EPF, SOCSO and tax (RM)"]
                    + [label for key, label in DAILY_COUNTS if key != "days_worked"] + ["Notes"])
    total = 0.0
    for r, company in zip(results, companies):
        pay = r.get("pay")
        total += pay["total"] if pay else 0.0
        by_key = {line["key"]: line["amount"] for line in pay["lines"]} if pay else {}
        writer.writerow([_csv_safe(company), _csv_safe(r["emp_no"]), _csv_safe(r["name"]),
                         r["pay_basis"].capitalize() if pay else "", _number(r["basic_rate"]) if pay else "",
                         {"typed": "Table Reader", "million": "Million"}.get(r.get("rate_source"), ""),
                         _number(r["values"]["days_worked"]["value"]), _number(pay["basic"]) if pay else ""]
                        + [(_number(by_key.get(key, 0.0)) if pay else "") for key, _, _, _ in OT_LINES]
                        + [(_number(pay[k]) if pay else "") for k in ("overtime", "allowances", "deductions", "total")]
                        + [_number(r["values"][key]["value"]) for key, _ in DAILY_COUNTS if key != "days_worked"]
                        + [_csv_safe("; ".join(_notes(r)))])
    writer.writerow(["", "", "Total"] + [""] * (8 + len(OT_LINES)) + [_number(total)])
    return out.getvalue()


def _ranges(days: list[int]) -> str:
    """[1,2,3,7] -> "1-3, 7"."""
    out, start, prev = [], None, None
    for d in days + [None]:
        if start is None:
            start = prev = d
        elif d is not None and d == prev + 1:
            prev = d
        else:
            out.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = d
    return ", ".join(out)


def compute_all(plan: dict, load_pages: Callable[[str], tuple[str, list[dict]]],
                million: dict[str, dict] | None = None) -> list[dict]:
    """``million``: the employees of Million's imported list by Employee No. in lower case (their Pay Basis and Basic
    Rate are used while none is typed)."""
    results = []
    for e in plan["employees"]:
        docs, lost = [], []
        for job_id in e["jobs"]:
            try:
                docs.append(load_pages(job_id))
            except OcrError as exc:
                lost.append({"kind": "missing", "text": exc.message, "job": job_id})
        result = calculate(plan, docs, e, (million or {}).get(e["emp_no"].strip().casefold()))
        if lost:
            result["issues"] = lost + result["issues"]
            result["complete"] = False
        results.append(result)
    return results


# --------------------------------------------------------------------------------------------------------- the file
def _number(value: float) -> str:
    return f"{value:.2f}"


def _month_title(month: str) -> str:
    year, mon = parse_month(month)
    return f"{calendar.month_name[mon]}, {year}"


def build_csv(plan: dict, results: list[dict]) -> str:
    """The payroll file: one row per employee, the columns named as on the Edit Payroll screen. UTF-8 text (the caller
    adds the BOM). Anything unfinished is spelled out in the Notes column, never hidden."""
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    lists = plan.get("lists") or default_lists()
    lines = [(kind, line["name"]) for kind in LIST_KINDS for line in lists.get(kind, [])]
    line_heads = [_csv_safe(f"{LISTS[kind][0]}: {name}" + (" (Day)" if kind == "leave" else "")) for kind, name in lines]
    writer.writerow(["Employee No.", "Name", "Month End Pay"] + [label for _, label, _ in FIELDS] + line_heads
                    + ["Zakat paid by individual", "Levy paid by individual", "Message", "Notes"])
    for r in results:
        notes = _notes(r)
        entries = r.get("entries") or {}
        writer.writerow([_csv_safe(r["emp_no"]), _csv_safe(r["name"]), _month_title(plan["month"])]
                        + [_number(r["values"][k]["value"]) for k in FIELD_KEYS]
                        + [_number((entries.get(kind) or {}).get(name, 0.0)) for kind, name in lines]
                        + [_number(r.get("zakat", 0.0)), _number(r.get("levy", 0.0)), _csv_safe(r.get("message", "")),
                           _csv_safe("; ".join(notes))])
    return out.getvalue()


def _notes(result: dict) -> list[str]:
    """What the Notes column says about an employee: INCOMPLETE first when anything is unfinished, then every issue."""
    notes = [i["text"] for i in result["issues"] if i["kind"] != "nodocs"]
    if not result["complete"]:
        notes.insert(0, "INCOMPLETE - check before importing")
    return notes


def _csv_safe(text: str) -> str:
    if text and (text[0] in "=@" or (text[0] in "+-" and len(text) > 1 and not (text[1].isdigit() or text[1] in " .,"))):
        return "'" + text
    return text


# ---------------------------------------------------------------------------------- Million import file (.xls, office)
# Million Payroll imports an Excel 97-2003 (.xls) file. Its File Format Setting says which Excel column ("xls #1",
# A = 1) holds each field; office-mapping.csv (learn-million\million-import-tools) is that setting as a table. Million
# reads the first sheet only: row 1 = headers, then one row per employee. An empty or text cell in a mapped column
# imports as 0 and REPLACES the value in Million, so every number is written, 0 included. An Employee No. that does not
# match Million exactly is skipped without a warning. Million's CSV import ignores the mapping: never use it.
MAPPING_FILE = "office-mapping.csv"
# Used when office-mapping.csv cannot be found: (Field, Type, Column, Header) exactly as in that file.
OFFICE_MAPPING = [
    ("Employee No.", "Key", 1, "Employee No."), ("Name", "Info", 2, "Name (not imported)"),
    ("Public Holiday", "Number", 3, "Public Holiday (days)"), ("Working Day", "Number", 4, "Working Day (days)"),
    ("Days Worked", "Number", 5, "Days Worked (days)"), ("Hours of Worked", "Number", 6, "Hours of Worked (hours)"),
    ("Lateness", "Number", 7, "Lateness (hours)"), ("Early Departure", "Number", 8, "Early Departure (hours)"),
    ("No Pay Hour", "Number", 9, "No Pay Hour (hours)"),
    ("Overtime # 1", "Number", 10, "Overtime # 1 (1.0x hours)"), ("Overtime # 2", "Number", 11, "Overtime # 2 (1.5x hours)"),
    ("Overtime # 3", "Number", 12, "Overtime # 3 (2.0x hours)"), ("Overtime # 4", "Number", 13, "Overtime # 4 (3.0x hours)"),
    ("Overtime # 5", "Number", 14, "Overtime # 5 (Rest Day days)"),
    ("Overtime # 6", "Number", 15, "Overtime # 6 (Holiday days)"),
    ("Absence", "Number", 16, "Absence (days)"), ("Annual Leave", "Number", 17, "Annual Leave (days)"),
    ("Compassionate Leave", "Number", 18, "Compassionate Leave (days)"),
    ("Examination Leave", "Number", 19, "Examination Leave (days)"), ("Hospital Leave", "Number", 20, "Hospital Leave (days)"),
    ("Line Shutdown Leave", "Number", 21, "Line Shutdown Leave (days)"), ("Medical Leave", "Number", 22, "Medical Leave (days)"),
    ("Marriage Leave", "Number", 23, "Marriage Leave (days)"), ("Non-Pay Leave", "Number", 24, "Non-Pay Leave (days)"),
    ("Out of Bound", "Number", 25, "Out of Bound (days)"), ("Paternity Leave", "Number", 26, "Paternity Leave (days)"),
    ("ADHOC ALLOWANCE", "Number", 27, "ADHOC ALLOWANCE (RM)"), ("Attendance Allowance", "Number", 28, "Attendance Allowance (RM)"),
    ("RECAB 2.0 BLC PERMIT", "Number", 29, "RECAB 2.0 BLC PERMIT (RM)"), ("Food Allowance", "Number", 30, "Food Allowance (RM)"),
    ("Overtime", "Number", 31, "Overtime allowance (RM)"), ("OVERTIME 1.5", "Number", 32, "OVERTIME 1.5 allowance (RM)"),
    ("OVERTIME 2.0", "Number", 33, "OVERTIME 2.0 allowance (RM)"), ("RECRUITMENT CLAIM", "Number", 34, "RECRUITMENT CLAIM (RM)"),
    ("SPORTS CLAIM", "Number", 35, "SPORTS CLAIM (RM)"), ("SUPERVISIOR ALLOWANCE", "Number", 36, "SUPERVISIOR ALLOWANCE (RM)"),
    ("Transport Allowance", "Number", 37, "Transport Allowance (RM)"), ("use and claim", "Number", 38, "use and claim (RM)"),
    ("Absent Deduction Fine", "Number", 39, "Absent Deduction Fine (RM)"), ("ADVANCE SALARY", "Number", 40, "ADVANCE SALARY (RM)"),
    ("EXTRA PAID SALARY", "Number", 41, "EXTRA PAID SALARY (RM)"), ("Loan Deduction", "Number", 42, "Loan Deduction (RM)"),
    ("MEAL DEDUCTION", "Number", 43, "MEAL DEDUCTION (RM)"), ("MERCHANTRADE CARD", "Number", 44, "MERCHANTRADE CARD (RM)"),
    ("NON-COMPLETE HRS", "Number", 45, "NON-COMPLETE HRS (RM)"), ("ALREADY PAID SALARY", "Number", 46, "ALREADY PAID SALARY (RM)"),
    ("PENALTY", "Number", 47, "PENALTY (RM)"), ("APPLY/RENEWAL", "Number", 48, "APPLY/RENEWAL (RM)"),
    ("RENTAL CAR", "Number", 49, "RENTAL CAR (RM)"), ("rental hostel", "Number", 50, "rental hostel (RM)"),
    ("ZAKAT", "Number", 51, "ZAKAT (RM)"),
]
# Million rows that are Table Reader's figures; every other Number row is a Leave / Allowance / Deduction line by name.
MILLION_FIELDS = {"Public Holiday": "public_holiday", "Working Day": "working_days", "Days Worked": "days_worked",
                  "Hours of Worked": "hours_worked", "Lateness": "lateness", "Early Departure": "early_departure",
                  "No Pay Hour": "no_pay_hour", "Overtime # 1": "ot_1", "Overtime # 2": "ot_1_5", "Overtime # 3": "ot_2",
                  "Overtime # 4": "ot_3", "Overtime # 5": "ot_rest_day", "Overtime # 6": "ot_holiday"}
NOTES_HEADER = "Notes (not imported)"


def mapping_paths() -> list[Path]:
    """Where office-mapping.csv is looked for: TABLE_READER_MILLION_MAPPING, the learn-million tools folder in the
    user's Documents, then the copy that comes with the app."""
    import sys

    from jobs import documents_dir

    paths = [Path(os.environ["TABLE_READER_MILLION_MAPPING"])] if os.environ.get("TABLE_READER_MILLION_MAPPING") else []
    paths.append(documents_dir() / "learn-million" / "million-import-tools" / MAPPING_FILE)
    paths.append(Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "million" / MAPPING_FILE)
    return paths


def load_office_mapping(path: Path | None = None) -> list[dict]:
    """The office File Format Setting: [{field, type, column, header}] for every column with a number (Key = Employee
    No., Info = written but not imported, Number = imported). From ``path``, else the first file of mapping_paths(),
    else OFFICE_MAPPING."""
    for p in [path] if path else mapping_paths():
        if p.is_file():
            return _parse_mapping(p)
    if path:
        raise OcrError("MILLION_MAPPING", f"The Million column table {path.name} was not found.")
    return [{"field": f, "type": t, "column": c, "header": h} for f, t, c, h in OFFICE_MAPPING]


def _parse_mapping(path: Path) -> list[dict]:
    def bad(problem: str) -> OcrError:
        return OcrError("MILLION_MAPPING", f"The Million column table ({path}) could not be used: {problem}. "
                                           "Fix it to match Million's File Format Setting, then try again.")
    try:
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise bad(f"the file cannot be read ({exc})") from exc
    out, used = [], {}
    for n, row in enumerate(rows, start=2):
        field, kind = (row.get("Field") or "").strip(), (row.get("Type") or "").strip()
        try:
            column = int((row.get("Column") or "0").strip() or 0)
        except ValueError:
            raise bad(f"line {n} has a column that is not a whole number")
        if not field or kind not in ("Key", "Info", "Number") or column < 0:
            raise bad(f"line {n} needs a Field, a Type (Key, Info or Number) and a column number")
        if column == 0:
            continue                                                # 0 = not imported: nothing to write
        if column in used:
            raise bad(f"column {column} is used for both {used[column]} and {field}")
        used[column] = field
        out.append({"field": field, "type": kind, "column": column, "header": (row.get("Header") or field).strip()})
    keys = [m for m in out if m["type"] == "Key"]
    if len(keys) != 1:
        raise bad("it needs exactly one Key row (Employee No.) with a column number")
    return sorted(out, key=lambda m: m["column"])


EMPLOYEES_FILE = "employees.txt"


def million_employees_path() -> Path:
    """The list of Employee Nos. that exist in Million (one per line, kept by the user next to the import checker):
    TABLE_READER_MILLION_EMPLOYEES, else employees.txt in the learn-million tools folder in the user's Documents."""
    from jobs import documents_dir

    if os.environ.get("TABLE_READER_MILLION_EMPLOYEES"):
        return Path(os.environ["TABLE_READER_MILLION_EMPLOYEES"])
    return documents_dir() / "learn-million" / "million-import-tools" / EMPLOYEES_FILE


def load_million_employees(path: Path | None = None) -> set[str] | None:
    """The Employee Nos. of employees.txt, as the import checker reads it: one per line, lines starting with # ignored,
    upper/lower case does not matter, spaces and brackets do. None = no list (no file, unreadable or no codes in it),
    so nothing can be checked."""
    try:
        lines = (path or million_employees_path()).read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    return {line.strip().casefold() for line in lines if line.strip() and not line.lstrip().startswith("#")} or None


MILLION_LIST_FILE = "million-employees.json"
_TOTAL_EMPLOYEES = re.compile(r"total employees?\s*:\s*(\d+)", re.IGNORECASE)
_CODE_HEADS = ("emp no.", "emp no", "employee no.", "employee no")
_MILLION_EXTRA = {"branch": "branch", "pay basis": "pay_basis", "basic rate": "basic_rate"}


def parse_million_employees(data: bytes) -> list[dict]:
    """Million Payroll's own employee list -> [{"emp_no", "name"}]. The file is Million's "Employment Listing" saved as
    Excel (Employee > Print > Employment Listing > Print > Excel > File): a printed-report layout with the heading row
    ("Emp no." … "Name" …) repeated on every page and "Total Employees : n" at the end. The Employee No. and the name
    are taken, and from the "Payroll Information" report also "branch", "pay_basis" ("monthly", "daily"…) and
    "basic_rate" where they are filled in. Refused (OcrError) when it is not that report, or when the number of employees read differs from
    the report's own total: a list with someone missing would raise false alarms."""
    import xlrd

    bad = OcrError("MILLION_LIST", "This is not Million Payroll's employee list. In Million Payroll choose Employee > "
                   "Print > Employment Listing > Print > Excel > File, then choose the file rptempepmlist.xls here.")
    try:
        sheets = xlrd.open_workbook(file_contents=data).sheets()
    except Exception as exc:                                         # not an .xls file at all
        raise bad from exc

    def text(cell) -> str:
        value = cell.value
        if cell.ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
            value = int(value)                                       # an Employee No. such as 100 kept as a number
        return " ".join(str(value).split())

    found, total, code_col, name_col, others, extra = {}, None, None, None, [], {}
    for sheet in sheets:
        for r in range(sheet.nrows):
            row = [text(c) for c in sheet.row(r)]
            keys = [_key(v) for v in row]
            for v in row:
                m = _TOTAL_EMPLOYEES.search(v)
                if m:
                    total = int(m.group(1))
            if "name" in keys and any(k in _CODE_HEADS for k in keys):
                code_col = next(i for i, k in enumerate(keys) if k in _CODE_HEADS)
                name_col = keys.index("name")                        # the heading row (again on every page)
                others = [i for i, k in enumerate(keys) if k and i != code_col]
                extra = {field: keys.index(head) for head, field in _MILLION_EXTRA.items() if head in keys}
            elif code_col is not None and code_col < len(row) and row[code_col] \
                    and any(i < len(row) and row[i] for i in others):
                # an employee's row has something under another heading too (name, gender, basic rate…); the report
                # title, the company name and the total line can sit in the Employee No. column, alone
                if row[code_col] not in found:
                    person = {"emp_no": row[code_col], "name": row[name_col] if name_col < len(row) else ""}
                    for field, i in extra.items():
                        value = row[i] if i < len(row) else ""
                        if field == "basic_rate":
                            number = _number_or_none(value.replace(",", ""))
                            if number is not None:
                                person[field] = number
                        elif value:
                            person[field] = value.casefold() if field == "pay_basis" else value
                    found[row[code_col]] = person
    if code_col is None or not found:
        raise bad
    if total is not None and total != len(found):
        raise OcrError("MILLION_LIST", f"The employee list says Total Employees : {total}, but {len(found)} could be "
                       "read. Nothing was imported. Make the file again in Million Payroll and import it again.")
    return list(found.values())


def _same_person(a: str, b: str) -> bool:
    """Two names for one Employee No. count as the same person when one has all the words of the other ("ALI" and
    "MAJU JAYA ALI", upper/lower case ignored). An empty name cannot be compared, so it is not called different."""
    wa, wb = set(_key(a).split()), set(_key(b).split())
    return not wa or not wb or wa <= wb or wb <= wa


def _line_key(name: str) -> str:
    """Line names compared without case or extra spaces, letter O = digit 0 ("RECAB 2.O" = "RECAB 2.0")."""
    return " ".join(name.split()).casefold().replace("o", "0")


def _is_figure(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and 0 <= value <= MAX_FIGURE


def build_xls(plan: dict, results: list[dict], *, allow_incomplete: bool = False,
              mapping: list[dict] | None = None, known: set[str] | None = None, allow_unknown: bool = False,
              names: dict[str, str] | None = None, allow_names: bool = False) -> bytes:
    """The Million import file for the office: an Excel 97-2003 workbook, one sheet "Import", row 1 = headers, one row
    per employee in the columns of the office File Format Setting, and a Notes column after the last one (not imported).

    Refuses (OcrError, every problem listed) rather than write a file that would import wrong: an Employee No. that is
    empty, has spaces around it or is used twice; a figure that is not a number of 0 or more; a non-zero figure the
    office file has no column for (it would be lost silently). Employees marked INCOMPLETE are refused too, unless
    ``allow_incomplete``; their note is then in the Notes column. With ``known`` (load_million_employees), an Employee
    No. that is not in that list is refused as well, unless ``allow_unknown``: Million would skip the row silently.
    With ``names`` ({Employee No. in lower case: name in Million}), an employee whose name is another one in Million
    is refused unless ``allow_names``: Million goes by the Employee No. only."""
    import xlwt

    mapping = mapping if mapping is not None else load_office_mapping()
    numbers = [m for m in mapping if m["type"] == "Number"]
    carried = {MILLION_FIELDS[m["field"]] for m in numbers if m["field"] in MILLION_FIELDS}
    line_columns = {_line_key(m["field"]) for m in numbers if m["field"] not in MILLION_FIELDS}
    lists = plan.get("lists") or default_lists()
    labels = {k: label for k, label, _ in FIELDS}

    problems, incomplete, seen, line_values = [], [], {}, []
    for r in results:
        emp, name = r.get("emp_no") or "", r.get("name") or ""
        who = " ".join(x for x in (emp.strip(), name) if x) or "An employee"
        if not emp.strip():
            problems.append(f"{name or 'An employee'}: Employee No. is empty. Type it exactly as in Million Payroll.")
        elif emp != emp.strip():
            problems.append(f"{who}: Employee No. '{emp}' has a space before or after it. Delete the space.")
        elif emp in seen:
            problems.append(f"Employee No. {emp} is used for two employees ({seen[emp]} and {name or '?'}). "
                            "Each employee needs their own.")
        else:
            seen[emp] = name or "?"
        for key in FIELD_KEYS:
            value = r["values"][key]["value"]
            if not _is_figure(value):
                problems.append(f"{who}: {labels[key]} is not a number of 0 or more.")
            elif value and key not in carried:
                problems.append(f"{who}: {labels[key]} is {value:.2f}, but the office Million file has no column for "
                                "it. Make it 0, or type it in Million by hand after the import.")
        values: dict[str, float] = {}
        entries = r.get("entries") or {}
        for kind in LIST_KINDS:
            for line in lists.get(kind, []):
                value = (entries.get(kind) or {}).get(line["name"], 0.0)
                title = LISTS[kind][0]
                if not _is_figure(value):
                    problems.append(f"{who}: {title} '{line['name']}' is not a number of 0 or more.")
                    continue
                if not value:
                    continue
                key = _line_key(line["name"])
                if key not in line_columns:
                    problems.append(f"{who}: {title} '{line['name']}' is {value:.2f}, but the office Million file has "
                                    "no column for it. Make it 0, or type it in Million by hand after the import.")
                elif key in values:
                    problems.append(f"{who}: '{line['name']}' has a figure in two lists. Keep it in one list only.")
                else:
                    values[key] = float(value)
        for key, label in (("zakat", "Zakat paid by individual"), ("levy", "Levy paid by individual")):
            value = r.get(key, 0.0)
            if not _is_figure(value):
                problems.append(f"{who}: {label} is not a number of 0 or more.")
            elif value:
                problems.append(f"{who}: {label} is {value:.2f}, but the office Million file has no column for it "
                                "(the ZAKAT column is the Deduction line ZAKAT). Make it 0, or type it in Million by "
                                "hand after the import.")
        if not r["complete"]:
            incomplete.append(who)
        line_values.append(values)
    if problems:
        if incomplete:
            problems.append("Also marked INCOMPLETE: " + ", ".join(incomplete) + ".")
        raise OcrError("MILLION_REFUSED", "The Million file was not made. Fix these first, then download again:\n"
                       + "\n".join(f"- {p}" for p in problems))
    unknown = [" ".join(x for x in (r["emp_no"], r.get("name") or "") if x) for r in results
               if known and r["emp_no"].casefold() not in known]
    if unknown and not allow_unknown:
        raise OcrError("MILLION_UNKNOWN", (f"{len(unknown)} Employee Nos. are" if len(unknown) > 1 else
                                           "1 Employee No. is") + " not in the Million employee list: "
                       + ", ".join(unknown) + ". Million skips an Employee No. it does not know and gives no warning. "
                       "Check it in Million Payroll (Employee > Employee). If it is right there, import the employee "
                       "list from Million again, or make the file anyway.")
    other = [f"{r['emp_no']} {r['name']} (in Million: {names[r['emp_no'].casefold()]})" for r in results
             if names and not _same_person(r.get("name") or "", names.get(r["emp_no"].casefold(), ""))]
    if other and not allow_names:
        raise OcrError("MILLION_NAME", (f"{len(other)} employees have" if len(other) > 1 else "1 employee has")
                       + " another name in Million Payroll: " + ", ".join(other) + ". Million goes by the Employee No. "
                       "only, so the figures go to the person named in Million. Check the Employee No., or make the "
                       "file anyway.")
    if incomplete and not allow_incomplete:
        raise OcrError("MILLION_INCOMPLETE", (f"{len(incomplete)} employees are" if len(incomplete) > 1 else
                                              "1 employee is") + " marked INCOMPLETE: " + ", ".join(incomplete) + ". "
                       "Check them first, or make the file anyway: the reason is then written in its Notes column.")

    book = xlwt.Workbook(encoding="utf-8")
    sheet = book.add_sheet("Import")
    bold, text, number = xlwt.easyxf("font: bold on"), xlwt.easyxf(num_format_str="@"), xlwt.easyxf(num_format_str="0.00")
    notes_col = max(m["column"] for m in mapping)                  # the column after the last one (0-based index)
    for m in mapping:
        sheet.write(0, m["column"] - 1, m["header"], bold)
    sheet.write(0, notes_col, NOTES_HEADER, bold)
    for row, (r, values) in enumerate(zip(results, line_values), start=1):
        for m in mapping:
            col = m["column"] - 1
            if m["type"] == "Key":
                sheet.write(row, col, r["emp_no"], text)              # text, so a code such as 007 keeps its zeros
            elif m["type"] == "Info":
                if m["field"] == "Name":
                    sheet.write(row, col, r["name"], text)
            else:
                key = MILLION_FIELDS.get(m["field"])
                value = r["values"][key]["value"] if key else values.get(_line_key(m["field"]), 0.0)
                sheet.write(row, col, round(float(value), 2), number)
        notes = "; ".join(_notes(r))
        if notes:
            sheet.write(row, notes_col, notes[:32000], text)
    buf = io.BytesIO()
    book.save(buf)
    return buf.getvalue()


def month_run(plan: dict, results: list[dict], companies: list[str], *, mapping: list[dict] | None = None,
              known: set[str] | None = None, names: dict[str, str] | None = None) -> dict:
    """One Million file for the whole month, so the office imports once instead of once per company.

    Every employee who would go into a company's file without a question goes in. Everyone else is held back, with the
    reason: something that would import wrong, an Employee No. Million does not know or that belongs to another name
    there, an Employee No. used twice, or an employee still marked INCOMPLETE. Nobody is put in "anyway" here; that
    stays a decision per company (the company's own Download button).
    ``companies`` = each employee's company, in the order of ``results``. Returns {"file": bytes | None,
    "ready": [{"emp_no", "name", "company"}], "held": [{"emp_no", "name", "company", "reasons": [text]}]}."""
    mapping = mapping if mapping is not None else load_office_mapping()
    count: dict[str, int] = {}
    for r in results:
        code = (r.get("emp_no") or "").strip()
        if code:
            count[code] = count.get(code, 0) + 1
    ready, held, chosen = [], [], []
    for r, company in zip(results, companies):
        who = {"id": r["id"], "emp_no": r.get("emp_no") or "", "name": r.get("name") or "", "company": company}
        reasons = []
        if count.get(who["emp_no"].strip(), 0) > 1:
            reasons.append(f"Employee No. {who['emp_no']} is used for {count[who['emp_no'].strip()]} employees. "
                           "Each employee needs their own.")
        else:
            try:
                build_xls(plan, [r], mapping=mapping, known=known, names=names)
            except OcrError as exc:
                if exc.code == "MILLION_REFUSED":
                    reasons = [line[2:].split(": ", 1)[-1] for line in exc.message.split("\n")[1:]
                               if line.startswith("- ") and not line.startswith("- Also marked INCOMPLETE")]
                elif exc.code == "MILLION_UNKNOWN":
                    reasons = [f"Employee No. {who['emp_no']} is not in the Million employee list."]
                elif exc.code == "MILLION_NAME":
                    reasons = [f"In Million Payroll, Employee No. {who['emp_no']} is "
                               f"{names[who['emp_no'].casefold()]}."]
                elif exc.code == "MILLION_INCOMPLETE":
                    blocking = [i["text"] for i in r["issues"] if i["kind"] not in ("empno", "removed", "leave")]
                    reasons = ["Marked INCOMPLETE: " + (blocking[0] if blocking else "check this employee.")
                               + (f" (and {len(blocking) - 1} more)" if len(blocking) > 1 else "")]
                else:
                    raise
        if reasons:
            held.append({**who, "reasons": reasons})
        else:
            ready.append(who)
            chosen.append(r)
    data = build_xls(plan, chosen, mapping=mapping, known=known, names=names) if chosen else None
    return {"file": data, "ready": ready, "held": held}


def suggest_employee_nos(plan: dict, million: list[dict]) -> dict[str, dict]:
    """For employees with no Employee No. yet: the one employee of Million's list with their name ({employee id:
    {"emp_no", "name"}}). Offered to the user, not filled in (only a whole-name match is, when the employee is made
    from the files: fill_employee_nos): a suggestion is only made when exactly one name in
    Million fits (one name has all the words of the other) and nobody in the plan has that Employee No. already."""
    taken = {e["emp_no"].strip().casefold() for e in plan["employees"] if e["emp_no"].strip()}
    out = {}
    for e in plan["employees"]:
        if e["emp_no"].strip() or not e["name"].strip():
            continue
        fits = [m for m in million if m.get("name", "").strip() and _same_person(e["name"], m["name"])]
        if len(fits) == 1 and fits[0]["emp_no"].casefold() not in taken:
            out[e["id"]] = {"emp_no": fits[0]["emp_no"], "name": fits[0]["name"]}
    # two employees who fit the same person in Million: not clear who is who, so neither gets the suggestion
    twice = {s["emp_no"] for s in out.values() if sum(o["emp_no"] == s["emp_no"] for o in out.values()) > 1}
    return {k: s for k, s in out.items() if s["emp_no"] not in twice}


# ------------------------------------------------------------------------------------------------------- the store
class PayrollStore:
    """One JSON file per month under <root>/payroll."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, month: str) -> Path:
        parse_month(month)
        return self.root / f"{month}.json"

    def _read(self, path: Path, month: str) -> dict | None:
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return plan if isinstance(plan, dict) and plan.get("month") == month else None

    def load(self, month: str) -> dict:
        plan = self._read(self._path(month), month)
        if plan is None:
            plan = default_plan(month)
            plan["lists"] = self._latest_lists(month) or plan["lists"]
        if "lists" not in plan:                                     # saved before the lists existed
            plan["lists"] = default_lists()
        plan.setdefault("break_hours", DEFAULT_BREAK)               # saved before IN/OUT time cards
        for e in plan.get("employees", []):
            e.setdefault("entries", {kind: {} for kind in LIST_KINDS})
            e.setdefault("zakat", 0.0)
            e.setdefault("levy", 0.0)
            e.setdefault("message", "")
            e.setdefault("pay_basis", "monthly")
            e.setdefault("basic_rate", 0.0)
        return plan

    def _latest_lists(self, month: str) -> dict | None:
        """The table lines of the latest saved month before this one (else after it), so a new month keeps them."""
        if not self.root.is_dir():
            return None
        months = sorted(p.stem for p in self.root.glob("*.json") if _MONTH.match(p.stem) and p.stem != month)
        for other in [m for m in reversed(months) if m < month] + [m for m in months if m > month]:
            plan = self._read(self.root / f"{other}.json", other)
            if plan and isinstance(plan.get("lists"), dict):
                return plan["lists"]
        return None

    def save(self, plan: dict) -> None:
        self._write(self._path(plan["month"]), plan)

    def _write(self, path: Path, data) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)

    # Million's own employee list, imported by the user (parse_million_employees): Employee No. and name only
    def load_million(self) -> dict | None:
        """{"imported": "yyyy-mm-dd", "source": file name, "employees": [{"emp_no", "name"}]}, or None."""
        try:
            data = json.loads((self.root / MILLION_LIST_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and isinstance(data.get("employees"), list) and data["employees"] else None

    def save_million(self, employees: list[dict], source: str) -> dict:
        data = {"imported": date.today().isoformat(), "source": source, "employees": employees}
        self._write(self.root / MILLION_LIST_FILE, data)
        return data

    # the Employee No. / name of each worker, as typed by the user (see remember_employees)
    def load_directory(self) -> dict:
        try:
            data = json.loads((self.root / "employees.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_directory(self, directory: dict) -> None:
        self._write(self.root / "employees.json", directory)

    def used_employee_nos(self) -> set[str]:
        """Every Employee No. in any saved month and in the remembered workers (so a new one is never one of these)."""
        used = {str(w.get("emp_no") or "") for w in self.load_directory().values() if isinstance(w, dict)}
        for path in self.root.glob("*.json"):
            plan = self._read(path, path.stem) if _MONTH.match(path.stem) else None
            for e in (plan or {}).get("employees") or []:
                if isinstance(e, dict):
                    used.add(str(e.get("emp_no") or ""))
        return used - {""}
