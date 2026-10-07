"""Payroll step: confirmed time-card cells -> the month-end figures Million Payroll asks for (Edit Payroll screen).

Table Reader reads and the user corrects; this module only *calculates* from those confirmed cells, with rules the user
can see and change (which days are working / rest / public holiday days, normal hours per day). It never guesses:
a day whose hours are still unclear, a day with no entry, or a conflict is reported as an issue, not filled in.

A "plan" is saved per month in <Documents>\\Table Reader\\payroll\\<yyyy-mm>.json:
    {"month": "2026-09", "normal_hours": 8, "day_types": {"1": "work", ... "6": "rest", "16": "holiday"},
     "lists": {"leave" | "allowance" | "deduction" | "bik": [{"name", "type"}]},
     "employees": [{"id", "emp_no", "name", "jobs": [job ids], "hours_column": null | "Total", "overrides": {field: number},
                    "entries": {list kind: {line name: number}}, "zakat", "levy", "message"}]}
The lists are the company's own lines on the Edit Payroll screen (leave types, allowances, deductions, benefits in kind);
a new month starts with the lists of the latest saved month.

How the figures are worked out, per employee, from the daily hours written on the card(s):
    Working Days            days marked "work"
    Days Worked             "work" days with hours > 0
    Overtime 1.5 Times      on each worked "work" day: hours above the normal hours
    OT 1 Time (Rest Day)    "rest" days with hours > 0, counted in days
    OT 2 Times (Holiday)    "holiday" days with hours > 0, counted in days
    Public Holiday          "holiday" days on which the employee did not work
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
                                  "SPORTS CLAIM", "SUPERVISIOR ALLOWANCE")]),
    "deduction": ("Deduction", "Special Type", [
        ("Absent Deduction Fine", ""), ("ADVANCE SALARY", ""), ("ALREADY PAID SALARY", ""), ("APPLY/RENEWAL", ""),
        ("EXTRA PAID SALARY", ""), ("Loan Deduction", "Loan"), ("MEAL DEDUCTION", ""), ("MERCHANTRADE CARD", ""),
        ("NON-COMPLETE HRS", "")]),
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
    employees, seen_ids, used_jobs = [], set(), {}
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
            if j in used_jobs:
                raise OcrError("BAD_PAYROLL", "A document can belong to one employee only. Untick it from the other employee first.")
            used_jobs[j] = e["id"]
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
        employees.append({"id": e["id"], "emp_no": emp_no.strip(), "name": name.strip(), "jobs": list(jobs),
                          "hours_column": column or None, "overrides": overrides, "entries": entries,
                          "zakat": _figure(e.get("zakat", 0)), "levy": _figure(e.get("levy", 0)), "message": message})
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
    candidates = [c for c in labels if _HOURS_LABEL.search(c) and c != date_col]
    return date_col, (candidates[-1] if candidates else None)


def read_days(docs: list[tuple[str, list[dict]]], n_days: int, month_number: int, hours_column: str | None):
    """Daily hours from an employee's documents. ``docs`` is [(document name, merged pages)].
    Returns (days, issues): days maps day -> {"hours": float | None, "status": "ok" | "unclear" | "conflict", "source": text}."""
    days: dict[int, dict] = {}
    issues: list[dict] = []
    for name, pages in docs:
        for page in pages:
            date_col, hours_col = pick_columns(page["column_labels"], hours_column)
            where = f"{name}" + (f", page {page['page']}" if len(pages) > 1 else "")
            if hours_col is None:
                issues.append({"kind": "column", "text": f"{where}: no column with the daily hours was found. "
                                                         "Choose it in the 'Hours column' list.", "job": name})
                continue
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
                if day in days:
                    old = days[day]
                    if old["status"] == "ok" and entry["status"] == "ok" and old["hours"] == entry["hours"]:
                        continue                                    # the same day written on two cards, same answer
                    days[day] = {"hours": None, "status": "conflict", "source": f"{old['source']} / {where}"}
                    issues.append({"kind": "conflict", "text": f"Day {day} appears more than once ({old['source']} and "
                                                               f"{where}). It was left out until you fix it.", "job": name})
                else:
                    days[day] = entry
    return days, issues


# --------------------------------------------------------------------------------------------------- calculation
def calculate(plan: dict, docs: list[tuple[str, list[dict]]], employee: dict) -> dict:
    """The month-end figures for one employee, the per-day working, and everything that needs the user's attention."""
    n_days = days_in(plan["month"])
    _, month_number = parse_month(plan["month"])
    normal = plan["normal_hours"]
    days, issues = read_days(docs, n_days, month_number, employee.get("hours_column"))
    values = {k: 0.0 for k in FIELD_KEYS}
    rows = []
    missing = []
    for d in range(1, n_days + 1):
        kind = plan["day_types"][str(d)]
        entry = days.get(d)
        hours = entry["hours"] if entry else None
        status = entry["status"] if entry else "missing"
        if kind == "work":
            values["working_days"] += 1
        if status == "ok":
            if hours > 0:
                if kind == "work":
                    values["days_worked"] += 1
                    values["ot_1_5"] += max(0.0, hours - normal)
                elif kind == "rest":
                    values["ot_rest_day"] += 1
                else:
                    values["ot_holiday"] += 1
            elif kind == "holiday":
                values["public_holiday"] += 1
        elif status == "missing" and kind != "rest":
            missing.append(d)
            if kind == "holiday":
                values["public_holiday"] += 1                       # no entry on a public holiday: not worked
        rows.append({"day": d, "type": kind, "hours": hours, "status": status})
    if missing and docs:
        issues.append({"kind": "missing", "text": "No entry found for day " + _ranges(missing) + " in the chosen "
                       "documents. These days were counted as not worked: add the other card if there is one.", "job": None})
    if not docs:
        issues.append({"kind": "nodocs", "text": "No document chosen for this employee yet.", "job": None})
    if not (employee.get("emp_no") or "").strip():
        issues.append({"kind": "empno", "text": "Employee No. is empty. Type it exactly as in Million Payroll.", "job": None})
    complete = not any(i["kind"] in ("unclear", "conflict", "column", "missing", "nodocs", "date") for i in issues)
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
        notes = [i["text"] for i in r["issues"] if i["kind"] != "nodocs"]
        if not r["complete"]:
            notes.insert(0, "INCOMPLETE - check before importing")
        entries = r.get("entries") or {}
        writer.writerow([_csv_safe(r["emp_no"]), _csv_safe(r["name"]), _month_title(plan["month"])]
                        + [_number(r["values"][k]["value"]) for k in FIELD_KEYS]
                        + [_number((entries.get(kind) or {}).get(name, 0.0)) for kind, name in lines]
                        + [_number(r.get("zakat", 0.0)), _number(r.get("levy", 0.0)), _csv_safe(r.get("message", "")),
                           _csv_safe("; ".join(notes))])
    return out.getvalue()


def _csv_safe(text: str) -> str:
    if text and (text[0] in "=@" or (text[0] in "+-" and len(text) > 1 and not (text[1].isdigit() or text[1] in " .,"))):
        return "'" + text
    return text


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
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(plan["month"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
