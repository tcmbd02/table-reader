"""Payroll by company: what still needs the user ("Needs you"), for one company and for the month overview.

Pure functions over a plan and its calculated results. Nothing here reads a file, and nothing here does arithmetic:
the figures and the problems come from payroll.py, and this module only sorts them into what the user sees.
"""
from __future__ import annotations

import payroll

# A problem the calculation reports (payroll.calculate, "kind") -> the item the user sees.
#   look   = cells to check on the card            days   = days that do not add up
#   column = the days cannot be worked out         nocard = the employee has no card yet
# "leave" and "removed" are information, and an empty Employee No. ("empno") has its own item (emp_no_items).
ITEM_OF_ISSUE = {"unclear": "look", "conflict": "days", "missing": "days", "daytype": "days", "total": "days",
                 "date": "days", "column": "column", "flat": "column", "nodocs": "nocard"}
_ITEM_ORDER = ("look", "days", "column", "nocard")


def issue_items(result: dict, employee: dict) -> list[dict]:
    """The calculation's problems for one employee as items, one per kind: {kind, employee, texts, cards}.
    ``texts`` are the calculation's own sentences (each once, in its order); ``cards`` the documents the employee's
    cards are in, for the page to open."""
    cards: list[str] = []
    for ref in employee.get("jobs", []):
        base = payroll.split_ref(ref)[0]
        if base not in cards:
            cards.append(base)
    found: dict[str, dict] = {}
    for issue in result["issues"]:
        kind = ITEM_OF_ISSUE.get(issue["kind"])
        if kind is None:
            continue
        item = found.setdefault(kind, {"kind": kind, "employee": result["id"], "texts": [], "cards": cards})
        if issue["text"] not in item["texts"]:
            item["texts"].append(issue["text"])
    return [found[kind] for kind in _ITEM_ORDER if kind in found]
