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


def _card_ids(employee: dict) -> list[str]:
    """The documents the employee's cards are in, in their order, each once."""
    cards: list[str] = []
    for ref in employee.get("jobs", []):
        base = payroll.split_ref(ref)[0]
        if base not in cards:
            cards.append(base)
    return cards


def _place(at: dict) -> tuple:
    return at["doc"], at["page"], at["row"], at["day"]


def issue_items(result: dict, employee: dict) -> list[dict]:
    """The calculation's problems for one employee as items, one per kind: {kind, employee, texts, places, cards}.
    A problem that says where it is on a card ("at", payroll.read_days) is one of the item's ``places`` (lines to
    look at in the one-look panel, each counted once); ``texts`` are the other problems' own sentences (each once, in
    their order); ``cards`` the documents the employee's cards are in, for the page to open."""
    cards = _card_ids(employee)
    found: dict[str, dict] = {}
    places: dict[str, set] = {}
    for issue in result["issues"]:
        kind = ITEM_OF_ISSUE.get(issue["kind"])
        if kind is None:
            continue
        item = found.setdefault(kind, {"kind": kind, "employee": result["id"], "texts": [], "places": 0, "cards": cards})
        if "at" in issue:
            places.setdefault(kind, set()).add(_place(issue["at"]))
            item["places"] = len(places[kind])
        elif issue["text"] not in item["texts"]:
            item["texts"].append(issue["text"])
    return [found[kind] for kind in _ITEM_ORDER if kind in found]


_CELL_KEYS = ("value", "raw_text", "needs_review", "unclear_reason", "edited")


def look_cards(result: dict, employee: dict, pages: dict[str, list[dict]], names: dict[str, str]) -> list[dict]:
    """The one-look panel of one employee: [{doc, name, lines}], one per card (document) that has a problem on a line,
    in the employee's card order. A line is [{page, row, day, texts, cells}]: one per place on the card (page, row,
    day), with the calculation's sentences about it and every cell the calculation read there, as it is now (``pages``:
    the documents' merged pages, jobs.merged_pages). A document missing from ``pages`` (it could not be opened) is
    left out."""
    lines: dict[tuple, dict] = {}
    for issue in result["issues"]:
        at = issue.get("at")
        if not at or at["doc"] not in pages:
            continue
        line = lines.setdefault(_place(at), {"page": at["page"], "row": at["row"], "day": at["day"], "texts": [],
                                             "columns": set()})
        line["columns"].update(at["columns"])
        if issue["text"] not in line["texts"]:
            line["texts"].append(issue["text"])
    cards = []
    for doc in _card_ids(employee):
        mine = sorted((key for key in lines if key[0] == doc), key=lambda k: (k[1], k[2], k[3] or 0))
        if not mine:
            continue
        by_page = {p["page"]: p for p in pages[doc]}
        out = []
        for key in mine:
            line = lines[key]
            page = by_page[line["page"]]
            row = page["rows"][line["row"]]["cells"]
            out.append({"page": line["page"], "row": line["row"], "day": line["day"], "texts": line["texts"],
                        "cells": [{"column": c, **{k: row[c][k] for k in _CELL_KEYS}}
                                  for c in page["column_labels"] if c in line["columns"]]})
        cards.append({"doc": doc, "name": names.get(doc, ""), "lines": out})
    return cards


def emp_no_items(plan: dict, million: list[dict] | None, offers: dict[str, dict]) -> dict[str, list[dict]]:
    """What is wrong with each employee's Employee No., as items ({employee id: items}, [] when nothing is):
    "offer" - none yet and Million's list has exactly one name that fits (``offers``, payroll.suggest_employee_nos);
    "empno" - empty, shared with another employee, or Million has another name for it;
    "million_new" - not in Million's imported list (the employee must be created there before the import).
    Without a list from Million (``million`` None) no number is checked against it."""
    names = {m["emp_no"].casefold(): m.get("name", "") for m in million} if million else None
    count: dict[str, int] = {}
    for e in plan["employees"]:
        key = e["emp_no"].strip().casefold()
        if key:
            count[key] = count.get(key, 0) + 1
    out: dict[str, list[dict]] = {}
    for e in plan["employees"]:
        no = e["emp_no"].strip()
        key = no.casefold()
        if not no:
            offer = offers.get(e["id"])
            item = {"kind": "offer", "emp_no": offer["emp_no"], "million_name": offer["name"]} if offer \
                else {"kind": "empno", "why": "empty"}
        elif count[key] > 1:
            item = {"kind": "empno", "why": "shared", "emp_no": no, "count": count[key]}
        elif names is not None and key not in names:
            item = {"kind": "million_new", "emp_no": no}
        elif names is not None and not payroll._same_person(e["name"], names[key]):
            item = {"kind": "empno", "why": "name", "emp_no": no, "million_name": names[key]}
        else:
            item = None
        out[e["id"]] = [{"kind": item["kind"], "employee": e["id"], **{k: v for k, v in item.items() if k != "kind"}}] \
            if item else []
    return out


def employee_status(items: list[dict]) -> str:
    """"ready" (nothing left), "million" (only waiting to be created in Million), or "needs" (the user has to act)."""
    if not items:
        return "ready"
    return "million" if all(i["kind"] == "million_new" for i in items) else "needs"


_NOT_IN_MILLION = "is not in the Million employee list"       # payroll.month_run's reason for an unknown Employee No.


def company_view(company: str, plan: dict, results: list[dict], company_of: list[str], million: list[dict] | None,
                 offers: dict[str, dict], held: dict[str, list[str]], file_items: list[dict],
                 settings: dict | None = None, layout_items: list[dict] | None = None) -> dict:
    """Everything the company screen shows for ``company`` ("" = employees with no company).
    ``company_of``: each employee's company, in the plan's order. ``held``: {employee id: reasons} for everyone the
    month file would hold back (payroll.month_run). An employee held back for a reason that no item names gets a
    "held" item with those reasons, so the screen never says Ready for someone the file would leave out.
    ``file_items``: the company's files that need the user ("unplaced", "month"), listed first. ``settings``: the
    company's settings as the screen shows them ({own, default_changed, ...}); own settings made before the month's
    default was changed are an item ("settings"), first of all, until the user has looked at them. ``layout_items``:
    the company's card layouts to confirm (unknown_layouts), listed with the files."""
    numbers = emp_no_items(plan, million, offers)
    items, employees, million_new = list(file_items) + list(layout_items or []), [], []
    if settings and settings.get("default_changed"):
        items.insert(0, {"kind": "settings", "company": company})
    for e, r, c in zip(plan["employees"], results, company_of):
        if c != company:
            continue
        own = issue_items(r, e) + numbers[e["id"]]
        if e["id"] in held and all(i["kind"] == "million_new" for i in own):
            # held back for something no item of theirs names (being new in Million is its own item, not a reason here)
            reasons = [text for text in held[e["id"]] if _NOT_IN_MILLION not in text]
            if reasons:
                own.append({"kind": "held", "employee": e["id"], "texts": reasons})
        items += [i for i in own if i["kind"] != "million_new"]
        if any(i["kind"] == "million_new" for i in own):
            million_new.append({"emp_no": e["emp_no"].strip(), "name": e["name"]})
        employees.append({"id": e["id"], "emp_no": e["emp_no"], "name": e["name"],
                          "days_worked": r["values"]["days_worked"]["value"], "ot_1_5": r["values"]["ot_1_5"]["value"],
                          "ot_rest_day": r["values"]["ot_rest_day"]["value"], "status": employee_status(own)})
    if not employees and not items:
        status = "none"
    elif items:
        status = "needs"
    else:
        status = "million" if million_new else "ready"
    return {"company": company, "status": status, "needs": len(items), "waiting": len(million_new), "items": items,
            "employees": employees, "million_new": million_new, **({"settings": settings} if settings else {})}


_STATUS_ORDER = {"needs": 0, "ready": 1, "million": 1, "none": 2}


def overview(views: list[dict], known: list[str]) -> dict:
    """The month overview: one row per company view, plus the companies in ``known`` that have nothing this month
    ("none"). Companies that need the user come first, then the ready ones, then the empty ones; by name inside each
    group, with "no company" last in its group."""
    rows = [{"company": v["company"], "employees": len(v["employees"]), "status": v["status"], "needs": v["needs"],
             "waiting": v["waiting"], "own": bool((v.get("settings") or {}).get("own"))} for v in views]
    seen = {r["company"].casefold() for r in rows}
    rows += [{"company": c, "employees": 0, "status": "none", "needs": 0, "waiting": 0, "own": False}
             for c in known if c and c.casefold() not in seen]
    rows.sort(key=lambda r: (_STATUS_ORDER[r["status"]], r["company"] == "", r["company"].casefold()))
    return {"companies": rows,
            "ready_companies": sum(1 for r in rows if r["status"] in ("ready", "million")),
            "ready_employees": sum(1 for v in views for e in v["employees"] if e["status"] == "ready")}


LAYOUT_FIGURE_ROWS = 3          # a column the payroll does not read is asked about once this many rows hold figures


def unknown_layouts(cards: list[dict], layouts: dict) -> list[dict]:
    """"A card layout Table Reader does not know" items: one per layout (signature) of these cards ([{doc, name, page,
    hours_column}]) that the user has not confirmed, when a column the calculation does not read holds numbers or clock
    times in LAYOUT_FIGURE_ROWS rows or more (so a figure for Million may be being left out). Row numbers and codes
    ("No.", "Emp. No.") do not count; month grids and the clock report are read by their own rules and never asked.
    A layout the user confirmed comes back ("confirmed": True, no columns) while its map cannot work out the days.
    "hours_column": the card's employee's chosen hours column, kept by "It is right as it is"."""
    out, seen = [], set()
    for c in cards:
        labels = c["page"]["column_labels"]
        signature = payroll.layout_signature(labels)
        if signature in seen or payroll.built_in_layout(labels):
            continue
        if signature in layouts:
            if not payroll.layout_reads_days(labels, layouts):     # saved, but the days cannot be worked out with it
                seen.add(signature)
                out.append({"kind": "layout", "signature": signature, "doc": c["doc"], "page": c["page"]["page"],
                            "name": c["name"], "columns": [], "confirmed": True, "hours_column": c["hours_column"]})
            continue
        read = payroll.columns_read(labels, c["hours_column"], layouts)
        figures = [label for label in labels if label not in read and not payroll.is_row_number(label)
                   and sum(payroll.is_figure_text(row["cells"][label]["value"]) for row in c["page"]["rows"])
                   >= LAYOUT_FIGURE_ROWS]
        if figures:
            seen.add(signature)
            out.append({"kind": "layout", "signature": signature, "doc": c["doc"], "page": c["page"]["page"],
                        "name": c["name"], "columns": figures, "confirmed": False, "hours_column": c["hours_column"]})
    return out


def unplaced(plan: dict, candidates: list[dict]) -> list[dict]:
    """The candidates ([{ref, name, company, pages}]: documents, pages or grid rows) that are on no employee.
    A whole document counts as placed when any of its parts is chosen, and a part when its document or its page is."""
    taken, whole, in_parts, pages, row_pages = set(), set(), set(), set(), set()
    for e in plan["employees"]:
        for ref in e["jobs"]:
            base, page, row = payroll.split_part(ref)
            taken.add(ref)
            if page is None:
                whole.add(base)
            else:
                in_parts.add(base)
                (pages if row is None else row_pages).add((base, page))
    out = []
    for c in candidates:
        base, page, row = payroll.split_part(c["ref"])
        placed = c["ref"] in taken or base in whole or (page is None and base in in_parts) \
            or (row is not None and (base, page) in pages) or (page is not None and row is None and (base, page) in row_pages)
        if not placed:
            out.append(c)
    return out
