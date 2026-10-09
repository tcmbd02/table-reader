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
    return {"month": month, "normal_hours": 8, "day_types": types, "lists": default_lists(), "employees": []}


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
    "holiday": {"ph", "p.h", "p.h.", "p/h"},
    "off": {"off", "ro", "rd", "r/d", "rest"},
    "leave": {"al", "mc", "el", "cl", "ml", "hl", "upl", "npl", "ul"},
}
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


def worker_key(company: str, code: str, name: str, file_name: str) -> str:
    """Who a document belongs to, within a company: the printed code, else the printed name, else the file name."""
    who = f"code:{_key(code)}" if code else f"name:{_key(name)}" if name else f"file:{_key(file_name)}"
    return f"{_key(company)}|{who}"


def readable(page: dict) -> bool:
    """Can the payroll work out days from this page: a month grid, or a table with a daily hours column."""
    return bool(grid_columns(page["column_labels"]) or pick_columns(page["column_labels"], None)[1])


def auto_employees(plan: dict, candidates: list[dict], directory: dict,
                   new_id: Callable[[], str]) -> tuple[int, list[str], list[str]]:
    """Add an employee for every worker found in ``candidates`` ([{ref, name, company, pages}]: documents, one page of
    a multi-worker report, or one worker's row of a month grid) that no employee has yet, with their cards ticked.
    Employee No. and name come from ``directory`` (what the user typed in earlier months) when known; the Employee No.
    is never made up. Changes ``plan`` in place. Returns (employees added, names of documents left out because no days
    can be read from them, names of grid rows left out because the name in the row is unclear or empty)."""
    taken, whole, in_parts = set(), set(), set()
    for e in plan["employees"]:
        for ref in e["jobs"]:
            base, page = split_ref(ref)
            taken.add(ref)
            (whole if page is None else in_parts).add(base)
    by_key = {e.get("worker_key"): e for e in plan["employees"] if e.get("worker_key")}
    groups: dict[str, dict] = {}
    by_file: dict[str, set[str]] = {}       # company + name left in the file name -> the groups such files went to
    skipped, unnamed = [], []
    # cards with the worker printed on them first, so a card whose printed name is unclear can join its pair below
    order = sorted(range(len(candidates)), key=lambda i: not any(printed_worker(candidates[i]["pages"])))
    for i in order:
        c = candidates[i]
        base, page, row = split_part(c["ref"])
        if c["ref"] in taken or base in whole or (page is None and base in in_parts):
            continue                                              # already chosen for someone (whole or in part)
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
                                        "company": c["company"]})
        group["refs"].append(c["ref"])
        group["first"] = min(group["first"], i)
        if file_name:
            by_file.setdefault(file_id, set()).add(key)
    added = 0
    for key, g in sorted(groups.items(), key=lambda kv: kv[1]["first"]):    # employees in the files' order
        g["refs"].sort(key=[c["ref"] for c in candidates].index)
        if key in by_key:                                         # this worker is already an employee: add the cards
            by_key[key]["jobs"] += [r for r in g["refs"] if r not in by_key[key]["jobs"]]
            continue
        known = directory.get(key) or {}
        plan["employees"].append({"id": new_id(), "emp_no": known.get("emp_no", ""), "name": known.get("name") or g["name"],
                                  "jobs": g["refs"], "hours_column": None, "overrides": {}, "entries": {},
                                  "zakat": 0.0, "levy": 0.0, "message": "", "worker_key": key,
                                  "company": g["company"] or ""})
        added += 1
    return added, skipped, unnamed


def remember_employees(plan: dict, directory: dict) -> bool:
    """Keep each employee's Employee No. and name for next month (by worker_key). Returns True if anything changed."""
    changed = False
    for e in plan["employees"]:
        key = e.get("worker_key")
        if key and e["emp_no"]:
            entry = {"emp_no": e["emp_no"], "name": e["name"]}
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
        company = e.get("company") or ""
        if not isinstance(company, str) or len(company) > 80:
            raise bad
        employees.append({"id": e["id"], "emp_no": emp_no.strip(), "name": name.strip(), "jobs": list(jobs),
                          "hours_column": column or None, "overrides": overrides, "entries": entries,
                          "zakat": _figure(e.get("zakat", 0)), "levy": _figure(e.get("levy", 0)), "message": message,
                          "company": " ".join(company.split()), **({"worker_key": key} if key else {})})
    return {"month": month, "normal_hours": float(hours), "day_types": dict(types), "lists": lists, "employees": employees}


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
    """The day of the month in a Date cell ("16", "16/9"). Returns (day, problem). A date for another month is a problem."""
    text = (value or "").strip()
    m = _DATE_WITH_MONTH.match(text)
    if m:
        day, mon = int(m.group(1)), int(m.group(2))
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


def read_days(docs: list[tuple[str, list[dict]]], n_days: int, month_number: int, hours_column: str | None):
    """Daily hours from an employee's documents. ``docs`` is [(document name, merged pages)].
    Returns (days, issues): days maps day -> {"hours": float | None, "status": "ok" | "unclear" | "conflict",
    "source": text, "printed": {field: hours} | None (clock-system report figures for that day),
    "mark": None | "present" | "hours" | "absent" | "holiday" | "off" | "leave" (month grids), "code": what was written}.
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
            if hours_col is None:
                issues.append({"kind": "column", "text": f"{where}: no column with the daily hours was found. "
                                                         "Choose it in the 'Hours column' list.", "job": name})
                continue
            report = {c: REPORT_COLUMNS[_key(c)] for c in page["column_labels"] if _key(c) in REPORT_COLUMNS}
            if report:
                _check_report_totals(page, where, name, issues)
                flat = next((c for c in page["column_labels"] if _key(c) == REPORT_FLAT), None)
                if flat and any(parse_hours(row["cells"][flat]["value"]) or row["cells"][flat]["needs_review"]
                                for row in page["rows"]):
                    issues.append({"kind": "flat", "job": name, "text": f"{where}: the report has Flat overtime. "
                                   "Table Reader does not add it: type it in the right Million Payroll field yourself."})
            for r, row in enumerate(page["rows"], start=1):
                cells = row["cells"]
                dcell, hcell = cells[date_col], cells[hours_col]
                if dcell["needs_review"] or not (dcell["value"] or "").strip():
                    if hcell["value"] or hcell["needs_review"] or (hcell["raw_text"] or "").strip():
                        issues.append({"kind": "unclear", "text": f"{where}, row {r}: the date is unclear, so its hours "
                                                                  "were left out. Fix the date in the document.", "job": name})
                    continue
                day, problem = parse_day(dcell["value"], month_number)
                if day is None or not 1 <= day <= n_days:
                    if (hcell["value"] or "").strip() and parse_hours(hcell["value"]):
                        issues.append({"kind": "date", "text": f"{where}, row {r}: " + (problem or f"day {day} is not in this month")
                                       + ", so its hours were left out.", "job": name})
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
def calculate(plan: dict, docs: list[tuple[str, list[dict]]], employee: dict) -> dict:
    """The month-end figures for one employee, the per-day working, and everything that needs the user's attention."""
    n_days = days_in(plan["month"])
    _, month_number = parse_month(plan["month"])
    normal = plan["normal_hours"]
    days, issues = read_days(docs, n_days, month_number, employee.get("hours_column"))
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
                     "printed": {k: v for k, v in (printed or {}).items() if v} or None})
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
    return {"id": employee["id"], "emp_no": employee.get("emp_no", ""), "name": employee.get("name", ""), "values": final,
            "entries": employee.get("entries") or {}, "zakat": employee.get("zakat", 0.0), "levy": employee.get("levy", 0.0),
            "message": employee.get("message", ""), "days": rows, "issues": issues, "complete": complete}


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


def compute_all(plan: dict, load_pages: Callable[[str], tuple[str, list[dict]]]) -> list[dict]:
    results = []
    for e in plan["employees"]:
        docs, lost = [], []
        for job_id in e["jobs"]:
            try:
                docs.append(load_pages(job_id))
            except OcrError as exc:
                lost.append({"kind": "missing", "text": exc.message, "job": job_id})
        result = calculate(plan, docs, e)
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


def _line_key(name: str) -> str:
    """Line names compared without case or extra spaces, letter O = digit 0 ("RECAB 2.O" = "RECAB 2.0")."""
    return " ".join(name.split()).casefold().replace("o", "0")


def _is_figure(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and 0 <= value <= MAX_FIGURE


def build_xls(plan: dict, results: list[dict], *, allow_incomplete: bool = False,
              mapping: list[dict] | None = None) -> bytes:
    """The Million import file for the office: an Excel 97-2003 workbook, one sheet "Import", row 1 = headers, one row
    per employee in the columns of the office File Format Setting, and a Notes column after the last one (not imported).

    Refuses (OcrError, every problem listed) rather than write a file that would import wrong: an Employee No. that is
    empty, has spaces around it or is used twice; a figure that is not a number of 0 or more; a non-zero figure the
    office file has no column for (it would be lost silently). Employees marked INCOMPLETE are refused too, unless
    ``allow_incomplete``; their note is then in the Notes column."""
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
        for e in plan.get("employees", []):
            e.setdefault("entries", {kind: {} for kind in LIST_KINDS})
            e.setdefault("zakat", 0.0)
            e.setdefault("levy", 0.0)
            e.setdefault("message", "")
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

    # the Employee No. / name of each worker, as typed by the user (see remember_employees)
    def load_directory(self) -> dict:
        try:
            data = json.loads((self.root / "employees.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_directory(self, directory: dict) -> None:
        self._write(self.root / "employees.json", directory)
