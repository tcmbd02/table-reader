# Company-first payroll, stage 1: month overview and company screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the long Payroll page as the entry point with a month overview (one row per company) and a company screen whose "Needs you" list is the only work the user has to do.

**Architecture:** A new pure module `companies.py` turns the existing calculation results into "Needs you" items and company statuses; it does no arithmetic and reads no files. `app.py` gets read endpoints for the overview and one company, and three small actions (place a card, set a file's month, set an Employee No.). A new page script `static/companies.js` draws the two screens; the old Payroll page stays reachable at `#/payroll/<month>/old` and is used for employee detail until later stages.

**Tech Stack:** Python 3.14, FastAPI, pytest; plain HTML/JS/CSS with no build step; PowerShell 5.1 on Windows.

**Spec:** `docs/superpowers/specs/2026-10-12-company-first-payroll-design.md` (sections 3, 4, 9.3 stage 1, 10, 11). Stages 2 to 4 (one-look panel, company settings, "New in Million" screen, removing the old page) are separate plans.

**Left to later stages on purpose** (reached through the "Old payroll page" link until then): the employee detail view, the pay preview tab, month settings and company settings, the "own settings" mark, the summary before the month file, and a separate "New in Million" screen (stage 1 lists those employees in one line under the company's table). Items that the one-look panel will handle open the document page or the old page for now.

## Global Constraints

- **Never guess.** No task may fill, infer or default a cell value, a day, or an Employee No. beyond what the existing code already does. `result.json` is never written.
- **The calculation does not change.** No edit to `payroll.calculate`, `compute_all`, `build_xls` or `month_run`'s rules. Task 8 proves every September figure is unchanged.
- **Personal data.** The repo is public. Tests, comments, commit messages and chat use only made-up names (MAJU JAYA, BINA, ACME, ALI, SITI, ZUL, AMIN). Real-data checks print counts only.
- **Before every commit:** `.venv\Scripts\python -m pytest -q` passes; `.venv\Scripts\python tools\check_i18n.py` shows `missing Malay: 0`; `.venv\Scripts\python tools\check_patterns.py` shows `0 not translated`; the real-name scan of the diff is clean.
- **Every new text shown to the user** goes through `t()` / `tn()` / `tm()` and has a Malay entry in `static/i18n.js`.
- **Environment:** Windows, PowerShell 5.1 (no `&&`; chain with `;`), no Node/npm, no build step. `python -c "..."` loses quotes: write scratch scripts to files outside the repo.
- **Commits are local**, on branch `company-first` made from `pdf-text`. Pushing, rebuilding the packaged app and touching the `download` branch need the user's explicit OK and are not part of any task.
- **Plain-language messages** that say what happened and what to do next. No settings screens, no accounts.
- **Follow the surrounding code's style:** comment density, naming, 120-column lines, docstrings that say what and why.

## Review Focus

1. A company name with characters that break a URL or a path (`A & B (M) SDN. BHD.`, a `/`, a `#`): the company screen must open and its actions must work. Pinned in Task 4 (query parameter, test with such a name) and Task 6 (`encodeURIComponent`).
2. A card already on one employee is placed on another (two browser tabs, or a stale screen): the action must refuse with a plain message and change nothing. Pinned in Task 4.
3. A file with no company, and an employee with no company: they must not vanish. Both appear under the "(no company)" row. Pinned in Tasks 2 and 4.
4. A month's plan that `validate_plan` refuses as stored (old data): the overview must still open and show its companies, not fail. Pinned in Task 4.
5. A document that is still being read, or whose result cannot be loaded: it is not an item and must not break the overview. Pinned in Task 4.

---

## File Structure

| File | Responsibility |
|---|---|
| `companies.py` (new) | Pure functions: items for an employee, Employee No. items, cards on no employee, one company's view, the month overview rows. |
| `payroll.py` (modify) | `new_employee` helper (shared by `auto_employees` and the new `place_card`); `place_card`; `month_run` adds the employee `id` to each entry; `PayrollStore` loads/saves the months the user chose for files. |
| `app.py` (modify) | `open_month` (what opening a month does, shared); `month_of`; overview and company endpoints; place / file-month / Employee No. actions. |
| `static/companies.js` (new) | Month overview and company screen. |
| `static/index.html`, `static/app.js`, `static/payroll.js`, `static/app.css`, `static/i18n.js` (modify) | Two new `<main>` blocks, routing, the old page under `/old`, styles, Malay. |
| `tools/check_i18n.py` (modify) | Also scan `companies.js`. |
| `tests/test_companies.py` (new), `tests/test_payroll.py`, `tests/test_app.py` (modify) | Tests. |

---

### Task 1: Items from the calculation's issues

**Files:**
- Create: `companies.py`
- Test: `tests/test_companies.py`

**Interfaces:**
- Consumes: a result as `payroll.calculate` returns it: `{"id", "issues": [{"kind", "text", "job"}], ...}`; an employee `{"id", "jobs": [ref, ...]}`; `payroll.split_ref(ref) -> (document id, page | None)`.
- Produces: `companies.ITEM_OF_ISSUE: dict[str, str]`; `companies.issue_items(result: dict, employee: dict) -> list[dict]`, each item `{"kind": "look" | "days" | "column" | "nocard", "employee": str, "texts": list[str], "cards": list[str]}` where `cards` are the document ids of the employee's cards, in order, without repeats.

- [ ] **Step 1: Make the branch**

```powershell
git -C "C:\Users\TENGA CEKAP\Documents\table-reader" checkout -b company-first pdf-text
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_companies.py`:

```python
import companies


def result(issues, id="e1"):
    return {"id": id, "issues": [{"kind": k, "text": text, "job": None} for k, text in issues]}


def worker(id="e1", jobs=("d1",), **kw):
    return {"id": id, "emp_no": "MJ(1)", "name": "ALI", "jobs": list(jobs), **kw}


def test_issues_become_one_item_per_kind_in_a_fixed_order():
    r = result([("missing", "No entry found for day 4."), ("unclear", "Day 3 is unclear."),
                ("conflict", "Day 9 is written twice."), ("unclear", "Day 7 is unclear."),
                ("column", "No hours column.")])
    items = companies.issue_items(r, worker(jobs=("d1", "d2#p2", "d1#p1")))
    assert [i["kind"] for i in items] == ["look", "days", "column"]
    assert items[0] == {"kind": "look", "employee": "e1", "cards": ["d1", "d2"],
                        "texts": ["Day 3 is unclear.", "Day 7 is unclear."]}
    assert items[1]["texts"] == ["No entry found for day 4.", "Day 9 is written twice."]


def test_information_and_the_empty_employee_no_are_not_items_here():
    r = result([("leave", "The card marks leave on day 5."), ("removed", "1 time-card file was taken off."),
                ("empno", "Employee No. is empty.")])
    assert companies.issue_items(r, worker()) == []


def test_an_employee_with_no_card_and_a_text_said_twice():
    r = result([("nodocs", "No document chosen for this employee yet."), ("total", "Total differs."),
                ("total", "Total differs.")])
    items = companies.issue_items(r, worker(jobs=()))
    assert [(i["kind"], i["texts"], i["cards"]) for i in items] == [
        ("days", ["Total differs."], []), ("nocard", ["No document chosen for this employee yet."], [])]


def test_every_issue_that_makes_an_employee_incomplete_is_an_item():
    # the kinds payroll.calculate treats as "not complete" (see `complete =` there) must all map to an item
    blocking = ("unclear", "conflict", "column", "missing", "nodocs", "date", "total", "flat", "daytype")
    assert all(k in companies.ITEM_OF_ISSUE for k in blocking)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `.venv\Scripts\python -m pytest tests\test_companies.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'companies'`.

- [ ] **Step 4: Write the module**

Create `companies.py`:

```python
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
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `.venv\Scripts\python -m pytest tests\test_companies.py -q`
Expected: `4 passed`.

- [ ] **Step 6: Commit**

```powershell
git add companies.py tests/test_companies.py
git commit -m "Companies: items from the calculation's problems"
```

---

### Task 2: Employee No. items, employee status, one company's view, the month overview

**Files:**
- Modify: `companies.py`
- Modify: `payroll.py` (`month_run`: add the employee id to each `ready` / `held` entry)
- Test: `tests/test_companies.py`, `tests/test_payroll.py`

**Interfaces:**
- Consumes: `companies.issue_items` (Task 1); `payroll._same_person(a, b) -> bool`; `payroll.suggest_employee_nos(plan, million) -> {employee id: {"emp_no", "name"}}`; a result's `values[key]["value"]` for `days_worked`, `ot_1_5`, `ot_rest_day`.
- Produces:
  - `payroll.month_run(...)`: each entry of `ready` and `held` now also has `"id"`.
  - `companies.emp_no_items(plan: dict, million: list[dict] | None, offers: dict[str, dict]) -> dict[str, list[dict]]` — `{employee id: items}`; item kinds `"offer"` (`emp_no`, `million_name`), `"empno"` (`why`: `"empty"` | `"shared"` | `"name"`, plus `emp_no`, `count` or `million_name`), `"million_new"` (`emp_no`).
  - `companies.employee_status(items: list[dict]) -> str` — `"ready"`, `"million"` or `"needs"`.
  - `companies.company_view(company: str, plan: dict, results: list[dict], company_of: list[str], million: list[dict] | None, offers: dict[str, dict], held: dict[str, list[str]], file_items: list[dict]) -> dict` — `{"company", "status", "needs", "waiting", "items", "employees", "million_new"}`.
  - `companies.overview(views: list[dict], known: list[str]) -> dict` — `{"companies": [{"company", "employees", "status", "needs", "waiting"}], "ready_companies", "ready_employees"}`.

- [ ] **Step 1: Write the failing test for `month_run`**

In `tests/test_payroll.py`, in `test_the_month_run_puts_everyone_who_is_ready_into_one_file_and_says_why_for_the_rest`, replace

```python
    assert run["ready"] == [{"emp_no": "MJ(1)", "name": "WORKER 1", "company": "ACME"}]
```

with

```python
    assert run["ready"] == [{"id": results[0]["id"], "emp_no": "MJ(1)", "name": "WORKER 1", "company": "ACME"}]
    assert [h["id"] for h in run["held"]] == [r["id"] for r in results[1:]]
```

- [ ] **Step 2: Run it to see it fail**

Run: `.venv\Scripts\python -m pytest tests\test_payroll.py -q -k month_run_puts_everyone`
Expected: FAIL, the `ready` entry has no `"id"`.

- [ ] **Step 3: Add the id in `month_run`**

In `payroll.py`, in `month_run`, change

```python
        who = {"emp_no": r.get("emp_no") or "", "name": r.get("name") or "", "company": company}
```

to

```python
        who = {"id": r["id"], "emp_no": r.get("emp_no") or "", "name": r.get("name") or "", "company": company}
```

- [ ] **Step 4: Run all payroll and app tests**

Run: `.venv\Scripts\python -m pytest tests\test_payroll.py tests\test_app.py -q`
Expected: all pass. (`app.py`'s `/run` endpoint copies `emp_no`, `name` and `reasons` by name, so the extra key does not reach the page.)

- [ ] **Step 5: Write the failing tests for the company functions**

Append to `tests/test_companies.py`:

```python
import payroll


def figures(days=26, ot=0.0, rest=0):
    return {"days_worked": {"value": days}, "ot_1_5": {"value": ot}, "ot_rest_day": {"value": rest}}


def calc(id, issues=(), **kw):
    return {**result(issues, id=id), "values": figures(**kw)}


def plan_of(*people):
    p = payroll.default_plan("2026-09")
    p["employees"] = list(people)
    return p


LISTED = [{"emp_no": "MJ(1)", "name": "ALI BIN ABU"}, {"emp_no": "MJ(2)", "name": "SITI"}]


def test_employee_no_items():
    p = plan_of(worker("e1", emp_no="MJ(1)", name="ALI"),            # in Million under a name that fits
                worker("e2", emp_no="mj(2)", name="ZUL"),            # Million has another name for it
                worker("e3", emp_no="MJ(9)", name="AMIN"),           # not in Million's list
                worker("e4", emp_no="", name="SITI"),                # Million offers a number
                worker("e5", emp_no="", name="TAN"),                 # nothing known
                worker("e6", emp_no="X1", name="LIM"), worker("e7", emp_no="x1", name="OMAR"))   # one number, two people
    offers = {"e4": {"emp_no": "MJ(2)", "name": "SITI"}}
    items = companies.emp_no_items(p, LISTED, offers)
    assert items["e1"] == []
    assert items["e2"] == [{"kind": "empno", "employee": "e2", "why": "name", "emp_no": "mj(2)", "million_name": "SITI"}]
    assert items["e3"] == [{"kind": "million_new", "employee": "e3", "emp_no": "MJ(9)"}]
    assert items["e4"] == [{"kind": "offer", "employee": "e4", "emp_no": "MJ(2)", "million_name": "SITI"}]
    assert items["e5"] == [{"kind": "empno", "employee": "e5", "why": "empty"}]
    assert items["e6"] == [{"kind": "empno", "employee": "e6", "why": "shared", "emp_no": "X1", "count": 2}]
    assert items["e7"] == [{"kind": "empno", "employee": "e7", "why": "shared", "emp_no": "x1", "count": 2}]


def test_without_millions_list_no_number_is_checked_against_it():
    p = plan_of(worker("e1", emp_no="MJ(9)", name="AMIN"))
    assert companies.emp_no_items(p, None, {}) == {"e1": []}


def test_employee_status():
    assert companies.employee_status([]) == "ready"
    assert companies.employee_status([{"kind": "million_new"}]) == "million"
    assert companies.employee_status([{"kind": "million_new"}, {"kind": "look"}]) == "needs"


def test_a_companys_view_lists_its_items_and_only_its_employees():
    p = plan_of(worker("e1", name="ALI"), worker("e2", emp_no="MJ(9)", name="AMIN"), worker("e3", emp_no="B1", name="ZUL"))
    results = [calc("e1", [("unclear", "Day 3 is unclear.")], days=24, ot=12.0, rest=1), calc("e2"), calc("e3")]
    files = [{"kind": "unplaced", "ref": "d9", "name": "MAJU JAYA SEPT 26 (3).jpeg", "readable": True}]
    view = companies.company_view("MAJU JAYA", p, results, ["MAJU JAYA", "MAJU JAYA", "BINA"], LISTED, {}, {}, files)
    assert view["company"] == "MAJU JAYA" and view["status"] == "needs" and view["needs"] == 2 and view["waiting"] == 1
    assert [i["kind"] for i in view["items"]] == ["unplaced", "look"]          # files first, then employees in order
    assert view["employees"] == [
        {"id": "e1", "emp_no": "MJ(1)", "name": "ALI", "days_worked": 24, "ot_1_5": 12.0, "ot_rest_day": 1, "status": "needs"},
        {"id": "e2", "emp_no": "MJ(9)", "name": "AMIN", "days_worked": 26, "ot_1_5": 0.0, "ot_rest_day": 0, "status": "million"}]
    assert view["million_new"] == [{"emp_no": "MJ(9)", "name": "AMIN"}]


def test_company_status_and_the_catch_all_for_an_employee_the_month_file_holds_back():
    p = plan_of(worker("e1", name="ALI"), worker("e2", emp_no="MJ(9)", name="AMIN"))
    results = [calc("e1"), calc("e2")]
    view = companies.company_view("MAJU JAYA", p, results, ["MAJU JAYA", "MAJU JAYA"], LISTED, {}, {}, [])
    assert view["status"] == "million" and view["needs"] == 0 and view["waiting"] == 1
    view = companies.company_view("MAJU JAYA", p, results, ["MAJU JAYA", "MAJU JAYA"], None, {}, {}, [])
    assert view["status"] == "ready"                                    # no list from Million: nothing to wait for
    # the month file would hold e1 back for a reason no item names: it is shown, never silently "Ready"
    held = {"e1": ["Annual Leave is not a line of the office file."], "e2": ["Employee No. MJ(9) is not in the Million employee list."]}
    view = companies.company_view("MAJU JAYA", p, [calc("e1"), calc("e2")], ["MAJU JAYA", "MAJU JAYA"], LISTED, {}, held, [])
    assert [(i["kind"], i["employee"]) for i in view["items"]] == [("held", "e1")]        # e2's reason is its own item
    assert view["items"][0]["texts"] == ["Annual Leave is not a line of the office file."]
    assert companies.company_view("SURIA", p, [calc("e1"), calc("e2")], ["MAJU JAYA", "MAJU JAYA"], None, {}, {}, [])["status"] == "none"


def test_the_overview_puts_companies_that_need_the_user_first_and_keeps_the_ones_without_a_company():
    def view(company, status, needs=0, waiting=0, employees=1):
        return {"company": company, "status": status, "needs": needs, "waiting": waiting,
                "employees": [{"status": "ready"}] * employees}

    out = companies.overview([view("MAJU JAYA", "ready", employees=6), view("acme", "needs", needs=5, employees=9),
                              view("", "needs", needs=1, employees=0), view("TEGUH", "million", waiting=1, employees=4),
                              view("BINA", "needs", needs=2, employees=3)], ["SURIA", "MAJU JAYA"])
    assert [(c["company"], c["status"]) for c in out["companies"]] == [
        ("acme", "needs"), ("BINA", "needs"), ("", "needs"), ("MAJU JAYA", "ready"), ("TEGUH", "million"), ("SURIA", "none")]
    assert out["companies"][0] == {"company": "acme", "employees": 9, "status": "needs", "needs": 5, "waiting": 0}
    # every employee in these made-up views is "ready" (an employee can be ready in a company that still needs the user)
    assert out["ready_companies"] == 2 and out["ready_employees"] == 6 + 9 + 0 + 4 + 3
```

- [ ] **Step 6: Run them to see them fail**

Run: `.venv\Scripts\python -m pytest tests\test_companies.py -q`
Expected: FAIL with `AttributeError: module 'companies' has no attribute 'emp_no_items'`.

- [ ] **Step 7: Write the functions**

Append to `companies.py`:

```python
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


def company_view(company: str, plan: dict, results: list[dict], company_of: list[str], million: list[dict] | None,
                 offers: dict[str, dict], held: dict[str, list[str]], file_items: list[dict]) -> dict:
    """Everything the company screen shows for ``company`` ("" = employees with no company).
    ``company_of``: each employee's company, in the plan's order. ``held``: {employee id: reasons} for everyone the
    month file would hold back (payroll.month_run). An employee held back for a reason that no item names gets a
    "held" item with those reasons, so the screen never says Ready for someone the file would leave out.
    ``file_items``: the company's files that need the user ("unplaced", "month"), listed first."""
    numbers = emp_no_items(plan, million, offers)
    items, employees, million_new = list(file_items), [], []
    for e, r, c in zip(plan["employees"], results, company_of):
        if c != company:
            continue
        own = issue_items(r, e) + numbers[e["id"]]
        if e["id"] in held and not own:
            own = [{"kind": "held", "employee": e["id"], "texts": list(held[e["id"]])}]
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
            "employees": employees, "million_new": million_new}


_STATUS_ORDER = {"needs": 0, "ready": 1, "million": 1, "none": 2}


def overview(views: list[dict], known: list[str]) -> dict:
    """The month overview: one row per company view, plus the companies in ``known`` that have nothing this month
    ("none"). Companies that need the user come first, then the ready ones, then the empty ones; by name inside each
    group, with "no company" last in its group."""
    rows = [{"company": v["company"], "employees": len(v["employees"]), "status": v["status"], "needs": v["needs"],
             "waiting": v["waiting"]} for v in views]
    seen = {r["company"].casefold() for r in rows}
    rows += [{"company": c, "employees": 0, "status": "none", "needs": 0, "waiting": 0}
             for c in known if c and c.casefold() not in seen]
    rows.sort(key=lambda r: (_STATUS_ORDER[r["status"]], r["company"] == "", r["company"].casefold()))
    return {"companies": rows,
            "ready_companies": sum(1 for r in rows if r["status"] in ("ready", "million")),
            "ready_employees": sum(1 for v in views for e in v["employees"] if e["status"] == "ready")}
```

- [ ] **Step 8: Run the tests to see them pass**

Run: `.venv\Scripts\python -m pytest tests\test_companies.py -q`
Expected: `10 passed`.

- [ ] **Step 9: Commit**

```powershell
git add companies.py payroll.py tests/test_companies.py tests/test_payroll.py
git commit -m "Companies: Employee No. items, company view, month overview"
```

---

### Task 3: Cards on no employee, placing a card, and the month chosen for a file

**Files:**
- Modify: `companies.py`, `payroll.py`
- Test: `tests/test_companies.py`, `tests/test_payroll.py`

**Interfaces:**
- Consumes: candidates as `app.py`'s `candidates_of` builds them: `{"ref", "name", "company", "pages"}`; `payroll.split_part(ref) -> (id, page | None, row | None)`; `payroll.printed_worker`, `name_from_file`, `worker_key`, `readable`.
- Produces:
  - `companies.unplaced(plan: dict, candidates: list[dict]) -> list[dict]` — the candidates that are on no employee.
  - `payroll.new_employee(new_id: str, name: str, refs: list[str], company: str, key: str | None, known: dict) -> dict`.
  - `payroll.place_card(plan: dict, candidate: dict, employee_id: str | None, new_id: Callable[[], str], directory: dict) -> dict` — returns the employee; raises `OcrError("BAD_PAYROLL", ...)` when the employee is gone.
  - `PayrollStore.load_file_months() -> dict[str, str]` and `PayrollStore.save_file_months(months: dict[str, str]) -> None` — `{document id: "YYYY-MM" | "none"}` in `payroll/file-months.json`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_companies.py`:

```python
def card(ref, name="MAJU JAYA SEPT 26.jpeg"):
    return {"ref": ref, "name": name, "company": "MAJU JAYA", "pages": []}


def test_cards_on_no_employee():
    p = plan_of(worker("e1", jobs=("d1", "d2#p1", "d3#p1r2")))
    cands = [card("d1"), card("d2#p1"), card("d2#p2"), card("d2"), card("d3#p1r1"), card("d3#p1r2"), card("d3#p1"),
             card("d4"), card("d5#p1")]
    # d2 as a whole and d3's page 1 as a whole are covered by the parts already chosen
    assert [c["ref"] for c in companies.unplaced(p, cands)] == ["d2#p2", "d3#p1r1", "d4", "d5#p1"]
    p = plan_of(worker("e1", jobs=("d5",)), worker("e2", jobs=("d3#p1",)))
    assert [c["ref"] for c in companies.unplaced(p, cands)] == ["d1", "d2#p1", "d2#p2", "d2", "d4"]
```

Append to `tests/test_payroll.py`, after `test_a_card_added_later_joins_its_pair_and_only_addable_cards_are_added`:

```python
def test_a_card_is_placed_on_an_employee_or_on_a_new_one():
    p = plan_for()
    payroll.auto_employees(p, [candidate("j1", "MAJU JAYA ALI SEPT 26.jpeg")], {}, lambda: "a")
    other = candidate("j2", "MAJU JAYA SEPT 26 (9).jpeg")
    assert payroll.place_card(p, other, "a", lambda: "b", {})["jobs"] == ["j1", "j2"]
    assert payroll.place_card(p, other, "a", lambda: "b", {})["jobs"] == ["j1", "j2"]          # not twice
    named = candidate("j3", "MAJU JAYA SEPT 26 (7).jpeg", header=[("Name", good("ZUL BIN OMAR"))])
    directory = {"maju jaya|name:zul bin omar": {"emp_no": "MJ(7)", "name": "ZUL BIN OMAR"}}
    new = payroll.place_card(p, named, None, lambda: "b", directory)
    assert (new["id"], new["name"], new["emp_no"], new["jobs"], new["company"]) == ("b", "ZUL BIN OMAR", "MJ(7)", ["j3"], "MAJU JAYA")
    assert new["worker_key"] == "maju jaya|name:zul bin omar"
    # a second new employee for a worker who already is one: made, but not under the same remembered worker
    twin = payroll.place_card(p, candidate("j4", "MAJU JAYA SEPT 26 (8).jpeg", header=[("Name", good("ZUL BIN OMAR"))]),
                              None, lambda: "c", directory)
    assert twin["id"] == "c" and "worker_key" not in twin and twin["emp_no"] == ""
    assert len(payroll.validate_plan(p, {"j1", "j2", "j3", "j4"})["employees"]) == 3
    with pytest.raises(OcrError) as exc:
        payroll.place_card(p, other, "gone", lambda: "d", {})
    assert exc.value.code == "BAD_PAYROLL"


def test_the_month_chosen_for_a_file_is_kept(tmp_path):
    store = payroll.PayrollStore(tmp_path)
    assert store.load_file_months() == {}
    store.save_file_months({"d1": "2026-09", "d2": "none"})
    assert store.load_file_months() == {"d1": "2026-09", "d2": "none"}
    (tmp_path / "file-months.json").write_text("not json", encoding="utf-8")
    assert store.load_file_months() == {}                       # a damaged file is no answer, never a crash
    assert store.used_employee_nos() == set()                   # and it is not taken for a month's payroll
```

If `pytest` or `OcrError` is not imported at the top of `tests/test_payroll.py`, add `import pytest` and `from ocr import OcrError` there (check the existing imports first; `OcrError` is the class `payroll.py` raises).

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python -m pytest tests\test_companies.py tests\test_payroll.py -q -k "no_employee or placed_on or chosen_for_a_file"`
Expected: 3 failures (`unplaced`, `place_card`, `load_file_months` do not exist).

- [ ] **Step 3: Write `unplaced`**

Append to `companies.py`:

```python
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
```

- [ ] **Step 4: Write `new_employee` and `place_card`, and use `new_employee` in `auto_employees`**

In `payroll.py`, directly above `def auto_employees`, add:

```python
def new_employee(new_id: str, name: str, refs: list[str], company: str, key: str | None, known: dict) -> dict:
    """An employee made from files: ``known`` is what the user typed for this worker in an earlier month
    (Employee No., name, pay basis, rate), {} for a worker seen for the first time."""
    return {"id": new_id, "emp_no": known.get("emp_no", ""), "name": known.get("name") or name, "jobs": refs,
            "hours_column": None, "overrides": {}, "entries": {}, "zakat": 0.0, "levy": 0.0, "message": "",
            **({"worker_key": key} if key else {}), "company": company or "",
            "pay_basis": known.get("pay_basis") or "monthly", "basic_rate": float(known.get("basic_rate") or 0.0)}
```

In `auto_employees`, replace the `plan["employees"].append({"id": new_id(), ... "basic_rate": float(known.get("basic_rate") or 0.0)})` statement (the dict literal spanning five lines) with:

```python
        plan["employees"].append(new_employee(new_id(), g["name"], g["refs"], g["company"], key, known))
```

Directly below `fill_employee_nos` (before `NEW_NO_LETTERS`), add:

```python
def place_card(plan: dict, candidate: dict, employee_id: str | None, new_id: Callable[[], str], directory: dict) -> dict:
    """Put one card (``candidate``: {ref, name, company, pages}) on the employee ``employee_id``, or on a new
    employee when it is None: named as printed on the card, else from the file name, with the Employee No. typed in
    an earlier month when the worker is known (``directory``). A new employee for a worker who already is one in this
    plan is made without the worker's key, so the two are not remembered as one. Changes ``plan`` in place and
    returns the employee."""
    if employee_id is not None:
        employee = next((e for e in plan["employees"] if e["id"] == employee_id), None)
        if employee is None:
            raise OcrError("BAD_PAYROLL", "That employee is not in this month's payroll any more. Reload the page.")
        if candidate["ref"] not in employee["jobs"]:
            employee["jobs"].append(candidate["ref"])
        return employee
    _, _, row = split_part(candidate["ref"])
    code, name = printed_worker(candidate["pages"], row_only=row is not None)
    file_name = name_from_file(candidate["name"], candidate["company"])
    key = worker_key(candidate["company"], code, name, file_name)
    if any(e.get("worker_key") == key for e in plan["employees"]):
        key = None
    employee = new_employee(new_id(), name or file_name, [candidate["ref"]], candidate["company"], key,
                            directory.get(key) or {} if key else {})
    plan["employees"].append(employee)
    return employee
```

- [ ] **Step 5: Write the store methods**

In `payroll.py`, in `class PayrollStore`, below `save_directory`, add:

```python
    # the month the user chose for a file that prints none ("none" = not a time card), by document id
    def load_file_months(self) -> dict[str, str]:
        try:
            data = json.loads((self.root / "file-months.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}

    def save_file_months(self, months: dict[str, str]) -> None:
        self._write(self.root / "file-months.json", months)
```

- [ ] **Step 6: Run the whole suite**

Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass (the 402 from before, plus the tests added so far). `auto_employees`' existing tests prove the `new_employee` change kept its behaviour.

- [ ] **Step 7: Commit**

```powershell
git add companies.py payroll.py tests/test_companies.py tests/test_payroll.py
git commit -m "Payroll: place a card on an employee, cards on nobody, the month chosen for a file"
```

---

### Task 4: The server's overview, company view and actions

**Files:**
- Modify: `app.py` (inside `create_app`, around `get_payroll`)
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: everything from Tasks 1 to 3; in `app.py`: `plans`, `store`, `auto_lock`, `finished_documents()`, `known_refs(docs)`, `drop_gone_documents`, `payroll_view(plan, docs, gone)`, `candidates_of(d)`, `read_auto_index()`, `add_new_documents`, `number_new_employees(plan, docs, before)`, `merged_pages`.
- Produces (HTTP, all JSON):
  - `GET /api/payroll/{month}/companies` -> `{"month", "companies": [{"company", "employees", "status", "needs", "waiting"}], "ready_companies", "ready_employees", "checked_with_million": bool, "added_by_themselves", "numbered"}`
  - `GET /api/payroll/{month}/company?name=<company>` -> `companies.company_view(...)` plus `"month"`; in items, `"cards"` become `[{"id", "name"}]`; `"unplaced"` items are `{"kind", "ref", "name", "doc", "readable"}`; `"month"` items are `{"kind", "doc", "name", "why"}`; for `name=""` also `"files": [{"id", "name"}]` (finished files with no company).
  - `POST /api/payroll/{month}/place` body `{"ref": str, "employee": str | null}` -> `{"ok": true, "employee": id}`
  - `POST /api/payroll/file-month` body `{"id": str, "month": "YYYY-MM" | "none"}` -> `{"ok": true}`
  - `PUT /api/payroll/{month}/employees/{employee_id}` body `{"emp_no": str}` -> `{"ok": true}`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app.py`:

```python
# ------------------------------------------------------------------------------------ payroll by company
def company_client(tmp_path, reader):
    store = Jobs(tmp_path / "jobs", reader=reader)
    return store, TestClient(app_module.create_app(store), base_url="http://localhost")


def set_company(c, starts, company):
    for j in c.get("/api/jobs").json():
        if j["name"].startswith(starts):
            c.put(f"/api/jobs/{j['id']}/company", json={"company": company})


def month_card(image):
    return record([{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)], labels=("Date", "Total"))


def import_million(c, *people):
    """Million's employee list with these (Employee No., name): the numbers Table Reader makes are then known."""
    from tests.helpers import million_listing

    listing = million_listing(list(people))
    assert c.post("/api/million/employees",
                  files={"file": ("rptempepmlist.xls", listing, "application/vnd.ms-excel")}).status_code == 200


def test_the_overview_and_a_company_screen(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        import_million(c, ("ABM001", "ALI"), ("BINA001", "SITI"))
        for name in (f"A & B (M) ALI SEPT {YEAR}.png", f"BINA SITI SEPT {YEAR}.png", "BINA ZUL.png", "LOOSE.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        set_company(c, "A & B", "A & B (M)")
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        over = c.get(f"/api/payroll/{month}/companies").json()
        rows = {r["company"]: r for r in over["companies"]}
        assert set(rows) == {"A & B (M)", "BINA", ""}
        assert rows["A & B (M)"]["employees"] == 1 and rows["A & B (M)"]["status"] == "ready"
        assert rows["BINA"]["employees"] == 1 and rows["BINA"]["status"] == "needs"     # a file of BINA has no month
        assert rows[""]["status"] == "needs" and rows[""]["employees"] == 0     # a file with no company is not lost
        assert over["checked_with_million"] is True
        # a company name with signs opens through the query string
        view = c.get(f"/api/payroll/{month}/company", params={"name": "A & B (M)"}).json()
        assert view["company"] == "A & B (M)" and view["month"] == month
        assert [(e["name"], e["emp_no"], e["status"]) for e in view["employees"]] == [("ALI", "ABM001", "ready")]
        assert view["items"] == [] and isinstance(view["employees"][0]["days_worked"], (int, float))
        bina = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert [i["kind"] for i in bina["items"]] == ["month"]
        assert bina["items"][0]["name"] == "BINA ZUL.png" and "why" in bina["items"][0]
        loose = c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()
        assert [f["name"] for f in loose["files"]] == ["LOOSE.png"]


def test_a_file_gets_its_month_and_its_card_is_placed(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        import_million(c, ("BINA001", "SITI"), ("BINA002", "ZUL"))
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        upload(c, tmp_path, name="BINA ZUL.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        item = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"][0]
        assert c.post("/api/payroll/file-month", json={"id": item["doc"], "month": "2026-13"}).status_code == 400
        assert c.post("/api/payroll/file-month", json={"id": "nope", "month": month}).status_code in (400, 404)
        assert c.post("/api/payroll/file-month", json={"id": item["doc"], "month": month}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        # read after the app started and now of this month: it joined by itself, as its own employee
        assert sorted(e["name"] for e in view["employees"]) == ["SITI", "ZUL"] and view["items"] == []
        # "not a time card": never asked about again, in any month
        upload(c, tmp_path, name="BINA NOTICE.png")
        store.wait_idle()
        set_company(c, "BINA NOTICE", "BINA")
        item = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"][0]
        assert item["kind"] == "month" and item["name"] == "BINA NOTICE.png"
        c.post("/api/payroll/file-month", json={"id": item["doc"], "month": "none"})
        assert c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"] == []
        assert c.get(f"/api/payroll/{YEAR}-10/company", params={"name": "BINA"}).json()["items"] == []


def test_placing_a_card_and_refusing_one_that_is_taken(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        siti = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["employees"][0]
        plan = c.get(f"/api/payroll/{month}").json()["plan"]
        ref = plan["employees"][0]["jobs"][0]
        plan["employees"][0]["jobs"] = []                                # the user takes the card off
        c.put(f"/api/payroll/{month}", json=plan)
        items = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"]
        assert [(i["kind"], i.get("ref")) for i in items if i["kind"] == "unplaced"] == [("unplaced", ref)]
        assert c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": None}).json()["ok"] is True
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert len(view["employees"]) == 2 and not [i for i in view["items"] if i["kind"] == "unplaced"]
        # placed on the new employee already: putting it on SITI as well is refused and changes nothing
        r = c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti["id"]})
        assert r.status_code == 400 and "one employee only" in r.json()["message"]
        assert c.get(f"/api/payroll/{month}").json()["plan"]["employees"][0]["jobs"] == []
        assert c.post(f"/api/payroll/{month}/place", json={"ref": "nope", "employee": None}).status_code in (400, 404)
        assert c.post(f"/api/payroll/{month}/place", json={"ref": ref}).status_code == 400          # no "employee" key


def test_an_offered_employee_no_is_set_with_one_call(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        import_million(c, ("MJ(1)", "ALI"), ("MJ(2)", "SITI"))
        upload(c, tmp_path, name=f"MAJU JAYA ALI SEPT {YEAR}.png")
        store.wait_idle()
        month = f"{YEAR}-09"                                             # no company: no new number is made
        view = c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()
        offer = [i for i in view["items"] if i["kind"] == "offer"][0]
        assert offer["emp_no"] == "MJ(1)" and offer["million_name"] == "ALI"
        url = f"/api/payroll/{month}/employees/{offer['employee']}"
        assert c.put(url, json={"emp_no": 5}).status_code == 400
        assert c.put(f"/api/payroll/{month}/employees/nobody", json={"emp_no": "MJ(1)"}).status_code == 400
        assert c.put(url, json={"emp_no": "MJ(1)"}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()
        assert view["employees"][0]["emp_no"] == "MJ(1)" and view["employees"][0]["status"] == "ready"
        assert c.get(f"/api/payroll/{month}/companies").json()["checked_with_million"] is True


def test_the_overview_opens_when_a_file_is_being_read_or_its_reading_is_gone(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        upload(c, tmp_path, name=f"BINA ZUL SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        assert c.get(f"/api/payroll/{month}/companies").json()["companies"][0]["employees"] == 2
        gone = [j for j in c.get("/api/jobs").json() if "ZUL" in j["name"]][0]
        (store.root / gone["id"] / "result.json").unlink()               # the reading cannot be loaded any more
        over = c.get(f"/api/payroll/{month}/companies")
        assert over.status_code == 200 and over.json()["companies"][0]["company"] == "BINA"
        assert c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).status_code == 200


def test_the_overview_opens_on_a_month_whose_stored_plan_cannot_be_saved_as_it_is(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        c.get(f"/api/payroll/{month}/companies")
        path = tmp_path / "payroll" / f"{month}.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["employees"].append(dict(plan["employees"][0], id="twin1"))    # one card on two employees: old, bad data
        path.write_text(json.dumps(plan), encoding="utf-8")
        over = c.get(f"/api/payroll/{month}/companies")
        assert over.status_code == 200 and over.json()["companies"][0]["employees"] == 2
```

Before relying on `store.root / gone["id"] / "result.json"`: open `jobs.py` and confirm that is where a job's reading is stored (search for `result.json`); if the file sits elsewhere, use that path in the test.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv\Scripts\python -m pytest tests\test_app.py -q -k "overview or company_screen or gets_its_month or placing_a_card or offered_employee_no"`
Expected: 6 failures, each a 404 or 405 from the missing endpoints.

- [ ] **Step 3: Share what opening a month does**

In `app.py`, replace the whole `get_payroll` function (from `@app.get("/api/payroll/{month}")` to its `return view`) with:

```python
    def open_month(month: str) -> tuple[dict, list[dict], dict, dict | None, int]:
        """What opening a month does, once, under the lock: cards that are gone are taken off, newly read files of
        the month join it, and everyone still without an Employee No. gets a new one. Returns (plan, documents,
        cards taken off per employee, what joined by itself, how many numbers were made)."""
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            gone = drop_gone_documents(plan, known_refs(docs))
            if gone:
                plans.save(payroll.validate_plan(plan, known_refs(docs)))
            added = add_new_documents(plan, docs)
            # everyone still without an Employee No. gets a new one here too (the user's rule: no number, make one),
            # also employees who were in the payroll before; like the files above, only when the page is opened
            numbered = 0
            try:
                payroll.validate_plan(plan, known_refs(docs))
                numbered = number_new_employees(plan, docs, set())
                if numbered:
                    plans.save(payroll.validate_plan(plan, known_refs(docs)))
            except OcrError:
                pass                                    # a plan that cannot be saved as it is: left alone
        return plan, docs, gone, added, numbered

    @app.get("/api/payroll/{month}")
    def get_payroll(month: str):
        plan, docs, gone, added, numbered = open_month(month)
        view = payroll_view(plan, docs, gone)
        view["added_by_themselves"] = added
        view["numbered"] = numbered
        return view
```

- [ ] **Step 4: Let a chosen month count when files are added by themselves**

In `app.py`, directly above `def add_new_documents`, add:

```python
    def month_of(d: dict, pages: list[dict], chosen: dict[str, str]) -> tuple[str | None, str]:
        """The payroll month of a finished document: the one the user chose for it, else what it prints
        (payroll.document_month). (None, why) when there is none; "none" chosen = not a time card."""
        if chosen.get(d["id"]) == "none":
            return None, "not a time card"
        if chosen.get(d["id"]):
            return chosen[d["id"]], ""
        return payroll.document_month(d["name"], pages, date.fromisoformat(d["created"][:10]))
```

In `add_new_documents`, add as its first line after `index = read_auto_index()` / the `if index is None: return None` pair:

```python
        chosen = plans.load_file_months()
```

and replace

```python
                month, why = payroll.document_month(d["name"], pages, date.fromisoformat(d["created"][:10]))
```

with

```python
                month, why = month_of(d, pages, chosen)
```

and, so that a file marked "not a time card" is not reported as having no month, replace

```python
            elif month is None:
                no_month.append({"name": d["name"], "why": why})
```

with

```python
            elif month is None and chosen.get(d["id"]) != "none":
                no_month.append({"name": d["name"], "why": why})
```

- [ ] **Step 5: Add the overview, the company view and the actions**

At the top of `app.py`, add `import companies` next to `import payroll` (keep the imports in the file's existing order).

In `app.py`, directly below `get_payroll`, add:

```python
    # ------------------------------------------------------------------------------------- payroll by company
    def month_state(month: str) -> dict:
        """The month opened (open_month) and worked out once, for the overview and the company screen."""
        plan, docs, gone, added, numbered = open_month(month)
        results = payroll_view(plan, docs, gone)["results"]
        company_of_doc = {d["id"]: d["company"] for d in docs}
        company_of = [payroll.employee_company(e, company_of_doc) for e in plan["employees"]]
        listed = plans.load_million()
        names = {e["emp_no"].casefold(): e["name"] for e in listed["employees"]} if listed else None
        held = {}
        if plan["employees"]:
            run = payroll.month_run(plan, results, company_of, names=names,
                                    known=set(names) if names else payroll.load_million_employees())
            held = {who["id"]: who["reasons"] for who in run["held"]}
        million = listed["employees"] if listed else None
        return {"plan": plan, "docs": docs, "results": results, "company_of": company_of, "million": million,
                "offers": payroll.suggest_employee_nos(plan, million) if million else {}, "held": held,
                "added": added, "numbered": numbered, "files": file_items(plan, docs, month)}

    def file_items(plan: dict, docs: list[dict], month: str) -> dict[str, list[dict]]:
        """{company: items} for the finished files that need the user in ``month``: a card of the month that is on no
        employee ("unplaced"), and a file with no month that is on no employee in any month ("month")."""
        chosen, index = plans.load_file_months(), read_auto_index() or {}
        out: dict[str, list[dict]] = {}
        for d in docs:
            if not d["company"]:
                continue                                            # first it needs a company (asked on its own)
            try:
                pages = merged_pages(store.load_result(d["id"]), store.load_edits(d["id"]))
                found, why = month_of(d, pages, chosen)
                cards = companies.unplaced(plan, candidates_of(d))
            except (OcrError, OSError, ValueError):
                continue                                            # a reading that cannot be loaded is not an item
            if found is None and index.get(d["id"]) not in (None, "before"):
                continue                                            # ticked by hand for some month: answered already
            if found == month:
                out.setdefault(d["company"], []).extend(
                    {"kind": "unplaced", "ref": c["ref"], "name": c["name"], "doc": d["id"],
                     "readable": any(payroll.readable(p) for p in c["pages"] if p["rows"])} for c in cards)
            elif found is None and chosen.get(d["id"]) != "none" and cards:
                out.setdefault(d["company"], []).append({"kind": "month", "doc": d["id"], "name": d["name"], "why": why})
        return out

    def view_of(state: dict, company: str) -> dict:
        return companies.company_view(company, state["plan"], state["results"], state["company_of"], state["million"],
                                      state["offers"], state["held"], state["files"].get(company, []))

    @app.get("/api/payroll/{month}/companies")
    def payroll_companies(month: str):
        """The month overview: one row per company with what still needs the user."""
        state = month_state(month)
        loose = [d for d in state["docs"] if not d["company"]]
        names = {c for c in state["company_of"]} | set(state["files"]) | ({""} if loose else set())
        views = [view_of(state, c) for c in names]
        for v in views:
            if v["company"] == "" and loose:
                v["status"], v["needs"] = "needs", v["needs"] + len(loose)      # files waiting for a company
        known = sorted({j["company"] for j in store.list_jobs() if j.get("company")})
        return {"month": month, **companies.overview(views, known), "checked_with_million": state["million"] is not None,
                "added_by_themselves": state["added"], "numbered": state["numbered"]}

    @app.get("/api/payroll/{month}/company")
    def payroll_company(month: str, name: str = ""):
        """One company's screen: its "Needs you" items, its employees with their main figures. ``name`` "" = the
        employees and finished files that have no company yet."""
        state = month_state(month)
        view = view_of(state, name)
        doc_names = {d["id"]: d["name"] for d in state["docs"]}
        for item in view["items"]:
            if "cards" in item:
                item["cards"] = [{"id": c, "name": doc_names.get(c, "")} for c in item["cards"]]
        view["month"] = month
        if name == "":
            view["files"] = [{"id": d["id"], "name": d["name"]} for d in state["docs"] if not d["company"]]
        return view

    @app.post("/api/payroll/{month}/place")
    async def place_card(month: str, request: Request):
        """Put a card on an employee of the month, or on a new employee ("employee": null)."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        bad = OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")
        if not isinstance(body, dict) or not isinstance(body.get("ref"), str) or "employee" not in body \
                or not (body["employee"] is None or isinstance(body["employee"], str)):
            raise bad
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            drop_gone_documents(plan, known_refs(docs))
            candidate = next((c for d in docs for c in candidates_of(d) if c["ref"] == body["ref"]), None)
            if candidate is None:
                raise OcrError("JOB_NOT_FOUND", "That card was not found. It may have been moved or deleted.")
            before = {e["id"] for e in plan["employees"]}
            employee = payroll.place_card(plan, candidate, body["employee"], lambda: "e" + uuid.uuid4().hex[:12],
                                          plans.load_directory())
            checked = payroll.validate_plan(plan, known_refs(docs))      # refuses a card that is on someone else
            if body["employee"] is None:
                number_new_employees(plan, docs, before)
                checked = payroll.validate_plan(plan, known_refs(docs))
            plans.save(checked)
        return {"ok": True, "employee": employee["id"]}

    @app.post("/api/payroll/file-month")
    async def set_file_month(request: Request):
        """The month a file is for, chosen by the user because the file prints none; "none" = not a time card."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("id"), str) or not isinstance(body.get("month"), str):
            raise OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")
        if body["month"] != "none":
            payroll.parse_month(body["month"])                           # OcrError when it is not a month
        if body["id"] not in {d["id"] for d in finished_documents()}:
            raise OcrError("JOB_NOT_FOUND", "That file was not found. It may have been moved or deleted.")
        with auto_lock:
            months = plans.load_file_months()
            months[body["id"]] = body["month"]
            plans.save_file_months(months)
        return {"ok": True}

    @app.put("/api/payroll/{month}/employees/{employee_id}")
    async def set_employee_no(month: str, employee_id: str, request: Request):
        """Set one employee's Employee No. (the number Million's list offers, accepted with one click)."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("emp_no"), str) or len(body["emp_no"]) > 100:
            raise OcrError("BAD_PAYROLL", "The Employee No. could not be understood. Reload the page and try again.")
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            drop_gone_documents(plan, known_refs(docs))
            employee = next((e for e in plan["employees"] if e["id"] == employee_id), None)
            if employee is None:
                raise OcrError("BAD_PAYROLL", "That employee is not in this month's payroll any more. Reload the page.")
            employee["emp_no"] = body["emp_no"].strip()
            plan = payroll.validate_plan(plan, known_refs(docs))
            plans.save(plan)
            directory = plans.load_directory()
            if payroll.remember_employees(plan, directory):
                plans.save_directory(directory)
        return {"ok": True}
```

Check, while writing: `payroll.parse_month` raises `OcrError` for a bad month (read its body at `payroll.py:135`); if it raises another error type, wrap the call so the endpoint answers 400 with "That is not a month.".

- [ ] **Step 6: Make the overview survive a plan that cannot be saved**

`month_state` calls `payroll_view`, which works on the plan as loaded and does not validate it, and `payroll.month_run`. Run the test `test_the_overview_opens_on_a_month_whose_stored_plan_cannot_be_saved_as_it_is`. If it fails because `month_run` or `place_card` raises on the bad plan, wrap only the `payroll.month_run(...)` call in `month_state`:

```python
            try:
                run = payroll.month_run(plan, results, company_of, names=names,
                                        known=set(names) if names else payroll.load_million_employees())
                held = {who["id"]: who["reasons"] for who in run["held"]}
            except OcrError:
                held = {}                                           # shown as it is; the old page says what blocks it
```

- [ ] **Step 6b: Make the overview survive a reading that cannot be loaded**

Run `test_the_overview_opens_when_a_file_is_being_read_or_its_reading_is_gone`. `payroll.compute_all` already turns an `OcrError` from `load_pages` into a "missing" problem on that employee. If the test fails with a 500 because `store.load_result` raises `OSError` or `ValueError` instead, make `payroll_view`'s `load_pages` (in `app.py`) raise the error `compute_all` expects. Replace its line

```python
                pages = merged_pages(store.load_result(job_id), store.load_edits(job_id))
```

with

```python
                try:
                    pages = merged_pages(store.load_result(job_id), store.load_edits(job_id))
                except (OSError, ValueError) as exc:
                    raise OcrError("JOB_NOT_FOUND", f"{meta['name']} could not be opened. Read the file again, or take "
                                                    "it off this employee.") from exc
```

Then run `tools\check_patterns.py`; if it reports this sentence as not translated, add it to `MS_PATTERNS` in `static/i18n.js` in the form of the neighbouring entries, with the Malay "{name} tidak dapat dibuka. Baca fail itu semula, atau keluarkannya daripada pekerja ini."

- [ ] **Step 7: Run the whole suite**

Run: `.venv\Scripts\python -m pytest -q`
Expected: all pass. If `test_a_file_gets_its_month_and_its_card_is_placed` fails on the employee names, print `view["employees"]` in the test, compare with `payroll.name_from_file` for those file names, and correct the expected names in the test (the behaviour to keep: two employees, no items).

- [ ] **Step 8: Commit**

```powershell
git add app.py tests/test_app.py
git commit -m "Payroll by company: overview, company view, place a card, a file's month, an offered Employee No."
```

---

### Task 5: The month overview page and the routes

**Files:**
- Create: `static/companies.js`
- Modify: `static/index.html`, `static/app.js`, `static/payroll.js`, `static/app.css`, `static/i18n.js`, `tools/check_i18n.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `GET /api/payroll/{month}/companies` (Task 4); from `app.js`: `$`, `el`, `api`, `route`, `showHome`; from `i18n.js`: `t`, `tn`, `tm`; from `payroll.js`: `MONTH_NAMES`, `defaultPayrollMonth`, `showPayroll`, `showMonthRun`, `addedByThemselves`, `newNumbersText`.
- Produces: routes `#/payroll` and `#/payroll/YYYY-MM` (overview), `#/payroll/YYYY-MM/c/<encodeURIComponent(company)>` (company screen, Task 6), `#/payroll/YYYY-MM/old` (the old page); `showMonth(month)`, `showCompany(month, company)` (a stub until Task 6), `hideScreens()`; `window.prOpenEmployee` (an employee id the old page shows first).

- [ ] **Step 1: Write the failing test**

In `tests/test_app.py`, in `test_browser_must_not_keep_an_old_script_after_an_update`, add `"/companies.js"` to the tuple of paths. Add below it:

```python
def test_the_page_has_the_company_first_screens(client):
    html = client.get("/").text
    assert 'id="month"' in html and 'id="company"' in html and "companies.js?v=" in html
    assert html.index("payroll.js") < html.index("companies.js")        # it uses the old page's helpers
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv\Scripts\python -m pytest tests\test_app.py -q -k "old_script or company_first_screens"`
Expected: 2 failures (404 for `/companies.js`; ids missing).

- [ ] **Step 3: Add the two screens to `index.html`**

In `static/index.html`, directly above `<main id="payroll" hidden>`, add:

```html
<main id="month" hidden>
  <div class="doc-bar">
    <button id="mo-back" class="link" data-t>&larr; All files</button>
    <h2 id="mo-title"></h2>
    <div class="doc-actions">
      <button id="mo-prev" type="button" aria-label="Month before" data-t-aria>&lt;</button>
      <button id="mo-next" type="button" aria-label="Month after" data-t-aria>&gt;</button>
      <a id="mo-old" class="navlink" href="#/payroll" data-t>Old payroll page</a>
      <button id="mo-million-import" type="button" data-t>Import employee list from Million</button>
      <input id="mo-million-file" type="file" accept=".xls" hidden>
      <button id="mo-run" class="primary" data-t>Make the month's Million file (all companies)</button>
    </div>
  </div>
  <div id="mo-error" class="banner error" hidden></div>
  <div id="mo-info" class="banner info" hidden></div>
  <div id="mo-run-result" class="banner info" hidden></div>
  <section class="card"><div id="mo-companies"></div><p id="mo-total" class="legend"></p></section>
</main>

<main id="company" hidden>
  <div class="doc-bar">
    <button id="co-back" class="link" data-t>&larr; All companies</button>
    <h2 id="co-title"></h2>
    <div class="doc-actions"><span id="co-status" class="muted" aria-live="polite"></span></div>
  </div>
  <div id="co-error" class="banner error" hidden></div>
  <section class="card"><h3 data-t>Needs you</h3><div id="co-items"></div></section>
  <section class="card"><h3 data-t>Employees</h3><div id="co-employees"></div></section>
</main>
```

and after `<script src="payroll.js"></script>` add:

```html
<script src="companies.js"></script>
```

- [ ] **Step 4: Route to the new screens**

In `static/app.js`, replace `showHome` and `route` with:

```js
// Only one screen shows at a time: the start page, a document, the month overview, a company, or the old payroll page.
function hideScreens() {
  for (const id of ["home", "doc", "month", "company", "payroll"]) $(id).hidden = true;
}

function showHome() {
  currentId = null; currentDoc = null; clearTimeout(docTimer);
  hideScreens(); $("home").hidden = false;
  loadRecent();
}

function route() {
  refreshCompanies();                                          // the Company chooser is on every screen
  const m = location.hash.match(/^#\/doc\/(.+)$/);
  const pm = location.hash.match(/^#\/payroll(?:\/(\d{4}-\d{2}))?(?:\/(old)|\/c\/(.*))?$/);
  if (m) openDoc(decodeURIComponent(m[1]));
  else if (pm && pm[2] && typeof showPayroll === "function") showPayroll(pm[1]);
  else if (pm && pm[3] !== undefined && typeof showCompany === "function") showCompany(pm[1], decodeURIComponent(pm[3]));
  else if (pm && typeof showMonth === "function") showMonth(pm[1]);
  else if (!pm) showHome();
}
```

Still in `static/app.js`, in `openDoc` (or `showDoc`, whichever sets `$("home").hidden = true`), replace the lines that hide the other screens one by one with `hideScreens();` followed by `$("doc").hidden = false;`. Search the file for `.hidden = true` to find every place a screen is hidden by hand and use `hideScreens()` there.

In `static/payroll.js`:

- In `showPayroll`, replace `$("home").hidden = true; $("doc").hidden = true; $("payroll").hidden = false;` with `hideScreens(); $("payroll").hidden = false;`.
- In `showPayroll`, after `renderPayroll();`, add:

```js
    // opened from a company screen for one employee: show that employee in the results window
    if (window.prOpenEmployee) {
      const at = pr.plan.employees.findIndex((e) => e.id === window.prOpenEmployee);
      window.prOpenEmployee = null;
      if (at >= 0) { prIndex = at; renderResults(); }
    }
```

- In `renderMonth`, change the address the month chooser goes to from ``location.hash = `#/payroll/${yy}-${String(monthSel.value).padStart(2, "0")}`;`` to ``location.hash = `#/payroll/${yy}-${String(monthSel.value).padStart(2, "0")}/old`;``. Search `payroll.js` for every other `#/payroll/` that is built from a month and add `/old` in the same way.
- Change `$("pr-back")`'s handler so it returns to the month overview: ``$("pr-back").addEventListener("click", async () => { await savePayroll(); location.hash = `#/payroll/${prMonth}`; });`` and, in `static/index.html`, change that button's text from `&larr; All files` to `&larr; All companies`.
- Give `showMonthRun` the box to draw in: change its signature to `function showMonthRun(run, box = $("pr-run-result"))` and delete its first line `const box = $("pr-run-result");`.

- [ ] **Step 5: Write the overview script**

Create `static/companies.js`:

```js
"use strict";
// Payroll by company: the month overview (one row per company) and a company's screen ("Needs you" + employees).
// Loaded after app.js and payroll.js and uses their helpers. The old payroll page stays at #/payroll/<month>/old.

let moMonth = null;        // the month the overview / company screen shows ("2026-09")

function monthTitle(month) {
  const [y, m] = month.split("-").map(Number);
  return `${t(MONTH_NAMES[m - 1])} ${y}`;
}

function shiftMonth(month, by) {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + by, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function companyHash(month, company) { return `#/payroll/${month}/c/${encodeURIComponent(company)}`; }

function statusText(row) {
  if (row.status === "none") return t("No files yet");
  if (row.status === "needs") return tn(row.needs, "Needs you: {n} thing", "Needs you: {n} things");
  if (row.status === "million") return tn(row.waiting, "Ready, {n} waiting for Million", "Ready, {n} waiting for Million");
  return t("Ready");
}

function moError(message) { $("mo-error").hidden = !message; $("mo-error").textContent = message || ""; }

async function showMonth(month) {
  clearTimeout(docTimer); currentId = null; currentDoc = null;
  hideScreens(); $("month").hidden = false;
  moMonth = month || defaultPayrollMonth();
  $("mo-title").textContent = t("Payroll {month}", { month: monthTitle(moMonth) });
  $("mo-old").href = `#/payroll/${moMonth}/old`;
  $("mo-run-result").hidden = true;
  moError("");
  try { drawMonth(await api("GET", `/api/payroll/${moMonth}/companies`)); }
  catch (e) { moError(e.message); }
}

function drawMonth(over) {
  const info = [addedByThemselves(over.added_by_themselves), over.numbered ? newNumbersText(over.numbered) : ""].filter(Boolean).join(" ");
  $("mo-info").hidden = !info; $("mo-info").textContent = info;
  const rows = over.companies.map((c) => {
    const open = () => { location.hash = companyHash(moMonth, c.company); };
    return el("tr", { class: `company-row ${c.status}`, tabindex: "0", onclick: open,
      onkeydown: (e) => { if (e.key === "Enter") open(); } },
    el("td", { text: c.company || t("(no company)") }), el("td", { text: String(c.employees) }), el("td", { text: statusText(c) }));
  });
  $("mo-companies").replaceChildren(rows.length
    ? el("table", { class: "daytable companies" },
      el("tr", {}, el("th", { text: t("Company") }), el("th", { text: t("Employees") }), el("th", { text: t("Status") })), ...rows)
    : el("p", { class: "muted", text: t("No files for this month yet. Add time cards on the start page or in the Inbox folder.") }));
  const total = over.companies.filter((c) => c.status !== "none").length;
  $("mo-total").textContent = [
    t("{a} of {b} companies ready.", { a: over.ready_companies, b: total }),
    tn(over.ready_employees, "{n} employee would be in the file now.", "{n} employees would be in the file now."),
    over.checked_with_million ? "" : t("The Employee Nos. are not being checked against Million: import Million's employee list."),
  ].filter(Boolean).join(" ");
}

$("mo-back").addEventListener("click", () => { location.hash = ""; });
$("mo-prev").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, -1)}`; });
$("mo-next").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, 1)}`; });

$("mo-run").addEventListener("click", async () => {
  const btn = $("mo-run");
  btn.disabled = true;
  try { showMonthRun(await api("POST", `/api/payroll/${moMonth}/run`), $("mo-run-result")); moError(""); }
  catch (e) { moError(e.message); }
  finally { btn.disabled = false; }
});

$("mo-million-import").addEventListener("click", () => $("mo-million-file").click());
$("mo-million-file").addEventListener("change", async () => {
  const file = $("mo-million-file").files[0];
  $("mo-million-file").value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  try { await api("POST", "/api/million/employees", form); showMonth(moMonth); }
  catch (e) { moError(e.message); }
});

// Task 6 replaces this with the company screen.
function showCompany(month, company) { showMonth(month); }

if (location.hash.startsWith("#/payroll")) route();      // the page was opened on a payroll screen: app.js ran before this file
```

In `static/payroll.js`, delete its last line (`if (location.hash.startsWith("#/payroll")) route();`): `companies.js` now does that, after every script is loaded.

- [ ] **Step 6: Styles**

Append to `static/app.css`:

```css
table.companies { width: 100%; }
table.companies td, table.companies th { padding: 6px 10px; }
tr.company-row { cursor: pointer; }
tr.company-row:hover td, tr.company-row:focus td { background: var(--bg); }
tr.company-row.needs td:last-child { font-weight: 700; }
tr.company-row.none td { color: var(--muted); }
```

- [ ] **Step 7: Malay, and let the checker see the new script**

In `tools/check_i18n.py`, change both tuples: `("i18n.js", "app.js", "payroll.js")` to `("i18n.js", "app.js", "payroll.js", "companies.js")`, and `("app.js", "payroll.js")` to `("app.js", "payroll.js", "companies.js")`.

In `static/i18n.js`, inside the `MS` object (next to the other payroll texts), add:

```js
  "Month before": "Bulan sebelumnya",
  "Month after": "Bulan berikutnya",
  "Old payroll page": "Halaman gaji lama",
  "← All companies": "← Semua syarikat",
  "Needs you": "Perlukan anda",
  "Employees": "Pekerja",
  "Payroll {month}": "Gaji {month}",
  "No files yet": "Belum ada fail",
  "Needs you: {n} thing": "Perlukan anda: {n} perkara",
  "Needs you: {n} things": "Perlukan anda: {n} perkara",
  "Ready, {n} waiting for Million": "Sedia, {n} menunggu Million",
  "Ready": "Sedia",
  "(no company)": "(tiada syarikat)",
  "Status": "Status",
  "No files for this month yet. Add time cards on the start page or in the Inbox folder.": "Belum ada fail untuk bulan ini. Tambah kad perakam waktu di halaman utama atau dalam folder Inbox.",
  "{a} of {b} companies ready.": "{a} daripada {b} syarikat sedia.",
  "{n} employee would be in the file now.": "{n} pekerja akan berada dalam fail sekarang.",
  "{n} employees would be in the file now.": "{n} pekerja akan berada dalam fail sekarang.",
  "The Employee Nos. are not being checked against Million: import Million's employee list.": "No. Pekerja tidak disemak dengan Million: import senarai pekerja Million.",
```

Run `.venv\Scripts\python tools\check_i18n.py`. For every line it prints as `MISSING:`, either the key above is spelled differently from the text in the page (make them equal) or `MS` already has the text ("Company", "Employees" may exist: do not add a key twice). Repeat until it prints `missing Malay: 0`.

- [ ] **Step 8: Run the checks**

Run: `.venv\Scripts\python -m pytest -q; .venv\Scripts\python tools\check_i18n.py; .venv\Scripts\python tools\check_patterns.py`
Expected: all tests pass; `syntax ok: companies.js`; `missing Malay: 0`; `0 not translated`.

- [ ] **Step 9: Look at it in a browser, on made-up data**

Make a throwaway data folder holding made-up finished documents, without calling Claude. Save this as `make_demo.py` in the session's scratch folder (not in the repo):

```python
"""Made-up finished documents in a throwaway Table Reader folder, read by a stand-in for Claude."""
import io
import os
import sys

repo, home = sys.argv[1], sys.argv[2]
os.environ["TABLE_READER_HOME"] = home
sys.path.insert(0, repo)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import app as app_module  # noqa: E402
import jobs  # noqa: E402
from tests.helpers import cell, good, million_listing, record  # noqa: E402

YEAR = __import__("datetime").date.today().year


def card(image):
    rows = [{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)]
    rows[6]["Total"] = cell(None, "9?", 40, "last digit faded")          # one yellow cell that counts
    return record(rows, labels=("Date", "Total"))


png = io.BytesIO()
Image.new("RGB", (60, 40), "white").save(png, "PNG")
store = jobs.Jobs(jobs.default_root(), reader=card)
with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
    listing = million_listing([("MJ(1)", "ALI"), ("MAJUJAY002", "SITI")])
    c.post("/api/million/employees", files={"file": ("rptempepmlist.xls", listing, "application/vnd.ms-excel")})
    names = [f"MAJU JAYA ALI SEPT {YEAR}.png", f"MAJU JAYA SITI SEPT {YEAR}.png", f"A & B (M) ZUL SEPT {YEAR}.png",
             "BINA AMIN.png", "LOOSE.png"]
    for name in names:
        c.post("/api/jobs", files=[("files", (name, png.getvalue(), "application/octet-stream"))])
    store.wait_idle()
    for j in c.get("/api/jobs").json():
        for starts, company in (("MAJU JAYA", "MAJU JAYA"), ("A & B", "A & B (M)"), ("BINA", "BINA")):
            if j["name"].startswith(starts):
                c.put(f"/api/jobs/{j['id']}/company", json={"company": company})
print("made", len(names), "documents in", home)
```

Run it, then start a second copy of the app on that folder (the user's own app keeps running on port 8765; this one takes the next free port, which it prints):

```powershell
$demo = "$env:TEMP\table-reader-stage1"; .venv\Scripts\python <scratch>\make_demo.py "C:\Users\TENGA CEKAP\Documents\table-reader" $demo
$env:TABLE_READER_HOME = $demo; .venv\Scripts\python start.py
```

Then, in the browser, confirm each of these and write down what was seen:

1. `Payroll` in the top bar opens the month overview, titled with the month.
2. One row per company; the one that needs the user is first and bold; "(no company)" is listed.
3. `<` and `>` change the month and the address; a month with nothing says so.
4. "Old payroll page" opens the old page; its back button returns to the overview; its month chooser stays on the old page.
5. "Make the month's Million file" shows its result under the bar.
6. Switch to Bahasa Melayu: every text on the overview is Malay.
7. Reload on `#/payroll/2026-09`: the overview opens (not the start page).

Stop the second copy and delete `$env:TEMP\table-reader-stage1`. Clear the variable: `Remove-Item Env:TABLE_READER_HOME`.

- [ ] **Step 10: Commit**

```powershell
git add static/companies.js static/index.html static/app.js static/payroll.js static/app.css static/i18n.js tools/check_i18n.py tests/test_app.py
git commit -m "Payroll opens on the month overview: one row per company"
```

---

### Task 6: The company screen

**Files:**
- Modify: `static/companies.js`, `static/app.css`, `static/i18n.js`

**Interfaces:**
- Consumes: `GET /api/payroll/{month}/company?name=`, `POST /api/payroll/{month}/place`, `POST /api/payroll/file-month`, `PUT /api/payroll/{month}/employees/{id}`, `PUT /api/jobs/{id}/company` (Task 4 and existing); `companyHash`, `monthTitle`, `statusText`, `moMonth` (Task 5); `companyFilter`, `NO_COMPANY`, `fmt` (existing).
- Produces: `showCompany(month, company)`; nothing later tasks call.

- [ ] **Step 1: Replace the stub with the screen**

In `static/companies.js`, replace the two lines

```js
// Task 6 replaces this with the company screen.
function showCompany(month, company) { showMonth(month); }
```

with:

```js
// ------------------------------------------------------------------------------------------------ company screen
let coCompany = "";        // the company on the screen ("" = no company)
let coView = null;         // what the server last sent for it

function coError(message) { $("co-error").hidden = !message; $("co-error").textContent = message || ""; }

async function showCompany(month, company) {
  clearTimeout(docTimer); currentId = null; currentDoc = null;
  hideScreens(); $("company").hidden = false;
  moMonth = month || defaultPayrollMonth();
  coCompany = company;
  $("co-title").textContent = `${company || t("(no company)")} - ${monthTitle(moMonth)}`;
  coError("");
  await loadCompany();
}

async function loadCompany() {
  try {
    coView = await api("GET", `/api/payroll/${moMonth}/company?name=${encodeURIComponent(coCompany)}`);
    drawCompany();
  } catch (e) { coError(e.message); }
}

// Do something for an item, then draw the company again from the server (the list is always what the server says).
async function coAct(button, action) {
  button.disabled = true;
  try { await action(); coError(""); await loadCompany(); }
  catch (e) { coError(e.message); button.disabled = false; }
}

function employeeName(id) {
  const e = coView.employees.find((x) => x.id === id);
  return e ? (e.name || t("An employee")) : t("An employee");
}

// Open the old payroll page on this company and this employee: every figure, the cards, the number, the overrides.
function openEmployee(id) {
  companyFilter = coCompany || NO_COMPANY;
  try { localStorage.setItem("companyFilter", companyFilter); } catch (_) { /* private window */ }
  window.prOpenEmployee = id;
  location.hash = `#/payroll/${moMonth}/old`;
}

function openEmployeeButton(id) {
  return el("button", { type: "button", text: t("Open employee"), onclick: () => openEmployee(id) });
}

const ITEM_HEADS = {
  look: "{name}: cells to check on the card",
  days: "{name}: days that do not add up",
  column: "{name}: Table Reader cannot work out the days",
  nocard: "{name}: no time card yet",
  held: "{name}: not ready for the Million file",
};

function itemNode(item) {
  const name = item.employee ? employeeName(item.employee) : "";
  const buttons = [];
  let head = "", details = [];
  if (ITEM_HEADS[item.kind]) {
    head = t(ITEM_HEADS[item.kind], { name });
    details = item.texts.map(tm);
    if (item.kind === "look") {
      item.cards.forEach((c, n) => buttons.push(el("button", { type: "button", title: c.name,
        text: item.cards.length > 1 ? t("Open card {n}", { n: n + 1 }) : t("Open the card"),
        onclick: () => { location.hash = `#/doc/${encodeURIComponent(c.id)}`; } })));
    } else buttons.push(openEmployeeButton(item.employee));
  } else if (item.kind === "offer") {
    head = t("{name}: Million has Employee No. {no} for {million}", { name, no: item.emp_no, million: item.million_name });
    const use = el("button", { type: "button", class: "primary", text: t("Use {no}", { no: item.emp_no }) });
    use.addEventListener("click", () => coAct(use, () => api("PUT",
      `/api/payroll/${moMonth}/employees/${encodeURIComponent(item.employee)}`, { emp_no: item.emp_no })));
    buttons.push(use, openEmployeeButton(item.employee));
  } else if (item.kind === "empno") {
    head = t("{name}: Employee No. to fix", { name });
    details = [item.why === "empty" ? t("It is empty. Type it exactly as in Million Payroll.")
      : item.why === "shared" ? t("Employee No. {no} is used for {n} employees. Each employee needs their own.", { no: item.emp_no, n: item.count })
        : t("In Million Payroll, Employee No. {no} is {million}.", { no: item.emp_no, million: item.million_name })];
    buttons.push(openEmployeeButton(item.employee));
  } else if (item.kind === "unplaced") {
    head = t("{file}: whose card is this?", { file: item.name });
    if (!item.readable) details = [t("Table Reader cannot work out the days from this file yet; the figures will have to be typed.")];
    const place = (employee) => (button) => coAct(button, () => api("POST", `/api/payroll/${moMonth}/place`, { ref: item.ref, employee }));
    for (const e of coView.employees) {
      const b = el("button", { type: "button", text: e.name || e.emp_no || t("An employee") });
      b.addEventListener("click", () => place(e.id)(b));
      buttons.push(b);
    }
    const fresh = el("button", { type: "button", text: t("New employee") });
    fresh.addEventListener("click", () => place(null)(fresh));
    const open = el("button", { type: "button", text: t("Open the card"), onclick: () => { location.hash = `#/doc/${encodeURIComponent(item.doc)}`; } });
    buttons.push(fresh, open);
  } else if (item.kind === "month") {
    head = t("{file}: which month is this for?", { file: item.name });
    details = [tm(item.why)];
    const setMonth = (month) => (button) => coAct(button, () => api("POST", "/api/payroll/file-month", { id: item.doc, month }));
    const here = el("button", { type: "button", text: t("It is for {month}", { month: monthTitle(moMonth) }) });
    here.addEventListener("click", () => setMonth(moMonth)(here));
    const none = el("button", { type: "button", text: t("Not a time card") });
    none.addEventListener("click", () => setMonth("none")(none));
    const open = el("button", { type: "button", text: t("Open the card"), onclick: () => { location.hash = `#/doc/${encodeURIComponent(item.doc)}`; } });
    buttons.push(here, none, open);
  }
  return el("li", { class: "need" }, el("strong", { text: head }),
    ...details.map((d) => el("p", { class: "legend", text: d })), el("div", { class: "need-buttons" }, ...buttons));
}

// A finished file with no company: it gets one here, and then shows up under that company.
function looseFileNode(file) {
  const input = el("input", { type: "text", maxlength: "80", placeholder: t("Company name"), value: suggestCompany(file.name),
    "aria-label": t("Company for {name}", { name: file.name }) });
  const save = el("button", { type: "button", class: "primary", text: t("Save") });
  save.addEventListener("click", () => coAct(save, async () => {
    if (!input.value.trim()) throw new Error(t("Type the company's name first."));
    await api("PUT", `/api/jobs/${encodeURIComponent(file.id)}/company`, { company: input.value });
  }));
  return el("li", { class: "need" }, el("strong", { text: t("{file}: which company is this for?", { file: file.name }) }),
    el("div", { class: "need-buttons" }, input, save));
}

const EMPLOYEE_WORDS = { ready: "Ready", million: "Waiting for Million", needs: "Needs you" };

function drawCompany() {
  const files = (coView.files || []).map(looseFileNode);
  const items = coView.items.map(itemNode);
  const count = files.length + items.length;
  $("co-status").textContent = count ? tn(count, "Needs you: {n} thing", "Needs you: {n} things")
    : coView.employees.length ? statusText({ status: coView.status, needs: 0, waiting: coView.waiting }) : "";
  $("co-items").replaceChildren(count ? el("ol", { class: "needs" }, ...files, ...items)
    : el("p", { class: "muted", text: coView.employees.length ? t("Nothing needs you here.") : t("Nothing here for this month.") }));
  const rows = coView.employees.map((e) => {
    const open = () => openEmployee(e.id);
    return el("tr", { class: `company-row ${e.status}`, tabindex: "0", onclick: open, onkeydown: (ev) => { if (ev.key === "Enter") open(); } },
      el("td", { text: e.emp_no }), el("td", { text: e.name || t("An employee") }), el("td", { text: fmt(e.days_worked) }),
      el("td", { text: fmt(e.ot_1_5) }), el("td", { text: fmt(e.ot_rest_day) }), el("td", { text: t(EMPLOYEE_WORDS[e.status]) }));
  });
  $("co-employees").replaceChildren(rows.length
    ? el("table", { class: "daytable companies" },
      el("tr", {}, ...["Employee No.", "Name", "Days Worked", "OT 1.5 (hours)", "Rest day (days)", "Status"].map((h) => el("th", { text: t(h) }))), ...rows)
    : el("p", { class: "muted", text: t("No employees for this company in this month yet.") }));
  if (coView.million_new.length) {
    $("co-employees").append(el("p", { class: "legend", text: tn(coView.million_new.length,
      "{n} employee is not in Million yet: {list}. Create them in Million with exactly this number, then import Million's employee list on the month page.",
      "{n} employees are not in Million yet: {list}. Create them in Million with exactly these numbers, then import Million's employee list on the month page.",
      { list: coView.million_new.map((m) => `${m.emp_no} ${m.name}`.trim()).join("; ") }) }));
  }
}

$("co-back").addEventListener("click", () => { location.hash = `#/payroll/${moMonth}`; });
```

Check while writing: `tn(n, one, many, extra)` accepts a fourth argument with more values (it is used that way in `showMonthRun`); `suggestCompany`, `fmt`, `companyFilter` and `NO_COMPANY` are globals of `app.js` / `payroll.js`.

- [ ] **Step 2: Styles**

Append to `static/app.css`:

```css
ol.needs { margin: 0; padding-left: 22px; }
ol.needs li.need { padding: 8px 0; border-bottom: 1px solid var(--line); }
ol.needs li.need:last-child { border-bottom: 0; }
.need .legend { margin: 2px 0; }
.need-buttons { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; align-items: center; }
.need-buttons button { padding: 4px 12px; }
.need-buttons input { font: inherit; padding: 4px 8px; border: 1px solid var(--line); border-radius: 6px; }
```

- [ ] **Step 3: Malay**

In `static/i18n.js`, inside `MS`, add (skip any key `MS` already has; the checker in Step 4 tells you):

```js
  "An employee": "Seorang pekerja",
  "Open employee": "Buka pekerja",
  "{name}: cells to check on the card": "{name}: sel untuk disemak pada kad",
  "{name}: days that do not add up": "{name}: hari yang tidak sepadan",
  "{name}: Table Reader cannot work out the days": "{name}: Table Reader tidak dapat mengira hari",
  "{name}: no time card yet": "{name}: belum ada kad perakam waktu",
  "{name}: not ready for the Million file": "{name}: belum sedia untuk fail Million",
  "Open card {n}": "Buka kad {n}",
  "Open the card": "Buka kad",
  "{name}: Million has Employee No. {no} for {million}": "{name}: Million ada No. Pekerja {no} untuk {million}",
  "Use {no}": "Guna {no}",
  "{name}: Employee No. to fix": "{name}: No. Pekerja perlu dibetulkan",
  "It is empty. Type it exactly as in Million Payroll.": "Ia kosong. Taip tepat seperti dalam Million Payroll.",
  "Employee No. {no} is used for {n} employees. Each employee needs their own.": "No. Pekerja {no} digunakan untuk {n} pekerja. Setiap pekerja perlukan nombor sendiri.",
  "In Million Payroll, Employee No. {no} is {million}.": "Dalam Million Payroll, No. Pekerja {no} ialah {million}.",
  "{file}: whose card is this?": "{file}: kad siapakah ini?",
  "Table Reader cannot work out the days from this file yet; the figures will have to be typed.": "Table Reader belum dapat mengira hari daripada fail ini; angkanya perlu ditaip.",
  "New employee": "Pekerja baharu",
  "{file}: which month is this for?": "{file}: untuk bulan manakah ini?",
  "It is for {month}": "Ia untuk {month}",
  "Not a time card": "Bukan kad perakam waktu",
  "{file}: which company is this for?": "{file}: untuk syarikat manakah ini?",
  "Type the company's name first.": "Taip nama syarikat dahulu.",
  "Waiting for Million": "Menunggu Million",
  "Nothing needs you here.": "Tiada apa-apa yang perlukan anda di sini.",
  "Nothing here for this month.": "Tiada apa-apa di sini untuk bulan ini.",
  "No employees for this company in this month yet.": "Belum ada pekerja untuk syarikat ini dalam bulan ini.",
  "Days Worked": "Hari Bekerja",
  "OT 1.5 (hours)": "OT 1.5 (jam)",
  "Rest day (days)": "Hari rehat (hari)",
  "{n} employee is not in Million yet: {list}. Create them in Million with exactly this number, then import Million's employee list on the month page.": "{n} pekerja belum ada dalam Million: {list}. Cipta mereka dalam Million dengan nombor yang sama, kemudian import senarai pekerja Million di halaman bulan.",
  "{n} employees are not in Million yet: {list}. Create them in Million with exactly these numbers, then import Million's employee list on the month page.": "{n} pekerja belum ada dalam Million: {list}. Cipta mereka dalam Million dengan nombor yang sama, kemudian import senarai pekerja Million di halaman bulan.",
```

The words in `ITEM_HEADS`, `EMPLOYEE_WORDS` and the table heads are looked up through variables, so the checker cannot see them. In `tools/check_i18n.py`, add them to the `used += [...]` list: `"{name}: cells to check on the card", "{name}: days that do not add up", "{name}: Table Reader cannot work out the days", "{name}: no time card yet", "{name}: not ready for the Million file", "Waiting for Million", "Needs you", "Ready", "Employee No.", "Name", "Days Worked", "OT 1.5 (hours)", "Rest day (days)", "Status"`.

The "month" item shows `item.why` through `tm()`. Its English texts come from `payroll.document_month` ("no month was found in the file name or on the card", "the file name and the card give different months (...)"), which the old page already shows through `tm()`, and from `month_of` ("not a time card", never shown as an item). Run `tools\check_patterns.py`; if it reports a sentence as not translated, add it to `MS_PATTERNS` in `static/i18n.js` in the form the neighbouring entries use.

- [ ] **Step 4: Run the checks**

Run: `.venv\Scripts\python -m pytest -q; .venv\Scripts\python tools\check_i18n.py; .venv\Scripts\python tools\check_patterns.py`
Expected: all tests pass; `syntax ok: companies.js`; `missing Malay: 0`; `0 not translated`.

- [ ] **Step 5: Look at it in a browser, on made-up data**

Delete `$env:TEMP\table-reader-stage1` if it is still there, then make the made-up data again and start the second copy with the same two commands as in Task 5 Step 9 (`make_demo.py` with the repo folder and `$env:TEMP\table-reader-stage1`, then `$env:TABLE_READER_HOME = ...; .venv\Scripts\python start.py`). That data has: two cards of MAJU JAYA and one of "A & B (M)", each with one yellow cell in a row that counts; a card of BINA with no month in its name; a card with no company; and a Million list with one name that fits a MAJU JAYA worker. Confirm each and write down what was seen:

1. Clicking a company row opens its screen; the title names the company and month; the address contains the encoded company name. Do this for a company named `A & B (M) SDN. BHD.` too.
2. "Needs you" lists: the card to check (button opens the document page), the file with no month (both buttons work: "It is for ..." makes it join; "Not a time card" removes the item for good).
3. Take a card off an employee on the old page, come back: "whose card is this?" appears with a button per employee and "New employee"; each places the card and the item goes.
4. The offered Employee No.: "Use ..." sets it and the item goes; the employee's status becomes Ready.
5. Clicking an employee opens the old page with that company chosen and that employee in the results window; its back button returns to the overview.
6. "(no company)": the file is listed with a company box; saving moves it under that company.
7. With nothing left, the status reads "Ready" and the overview shows the company as Ready.
8. Bahasa Melayu: every text on the screen is Malay.

- [ ] **Step 6: Commit**

```powershell
git add static/companies.js static/app.css static/i18n.js tools/check_i18n.py
git commit -m "Company screen: Needs you list, employees at a glance"
```

---

### Task 7: The real September payroll is unchanged, and the notes

**Files:**
- Modify: `PROGRESS.md`, `NEXT-SESSION.md`, `GUIDE - Table Reader to Million.html`, `PANDUAN - Table Reader ke Million.html`
- No product code.

**Interfaces:**
- Consumes: the finished stage; the user's real data, read-only.
- Produces: the counts quoted in `PROGRESS.md`.

- [ ] **Step 1: Compare every calculated figure with the code before this plan**

Write a scratch script outside the repo (in the session's scratch folder) that takes a repo folder as its argument, opens the real data read-only with `jobs.Jobs(jobs.default_root(), reader=lambda image: {})` and `payroll.PayrollStore(jobs.default_root().parent / "payroll")`, loads the plan `2026-09` **without saving anything**, works out every employee with `payroll.compute_all` (give it a `load_pages` like `app.py`'s, built from `jobs.merged_pages`), and prints **one line**: the SHA-256 of the JSON of `[(r["id"], r["values"], r["complete"]) for r in results]` and the number of employees. No names, no figures.

Run it twice: once against a clean checkout of `pdf-text` (`git worktree add ..\tr-before pdf-text`, then pass that folder), once against the working folder.

Expected: the same employee count and the same hash. If the hashes differ, stop: a task changed the calculation, which the Global Constraints forbid. Find it with `git diff pdf-text -- payroll.py` and undo it.

Remove the extra worktree: `git worktree remove ..\tr-before`.

- [ ] **Step 2: Count what the new screens would show on the real month**

In the same scratch folder, a second script that builds the app with `app.create_app(jobs.Jobs(jobs.default_root(), reader=lambda image: {}))` inside `fastapi.testclient.TestClient` **on a copy of the data**: copy `Documents\Table Reader` to a temporary folder first and point `TABLE_READER_HOME` at the copy, because opening a month saves. It calls `GET /api/payroll/2026-09/companies` and prints counts only: companies per status, total items, and items per kind (summed over every company's `GET .../company`). Delete the copy afterwards.

Expected: it runs without an error and every employee of the month appears under exactly one company row (the sum of the rows' `employees` equals the plan's employee count).

- [ ] **Step 3: Notes and guides**

- `PROGRESS.md`: a new entry at the top, "Session 18 - <date> - Company-first payroll, stage 1", saying what was built, the counts from Steps 1 and 2, what was clicked through in the browser and what was not, and that the old page is at "Old payroll page".
- `NEXT-SESSION.md`: section 0 gets one bullet for the session; "Next" names stage 2 (the one-look panel) and the spec's path.
- Both Million guides, section B: one short paragraph at the top saying that Payroll now opens on the list of companies, that each company shows what it needs, and that the steps below are on the "Old payroll page" until the new screens cover them. English in `GUIDE - ...html`, Malay in `PANDUAN - ...html`.

- [ ] **Step 4: Final checks and commit**

Run: `.venv\Scripts\python -m pytest -q; .venv\Scripts\python tools\check_i18n.py; .venv\Scripts\python tools\check_patterns.py`
Expected: all pass; `missing Malay: 0`; `0 not translated`.

Run the real-name scan on `git diff pdf-text` (the scan script from the session's scratch folder: it lists added lines that contain a word found in the user's data and not already in the repo). Read every flagged line; change any that holds a real name.

```powershell
git add PROGRESS.md NEXT-SESSION.md "GUIDE - Table Reader to Million.html" "PANDUAN - Table Reader ke Million.html"
git commit -m "Notes and guides: payroll by company, stage 1"
```

- [ ] **Step 5: Stop and report**

Report to the user: what stage 1 does, the test count, the two real-data results, the browser checklist with what was seen, and anything that did not work. Ask for the OK to merge `company-first` into `pdf-text`, push, rebuild the app and update the `download` branch. Do none of those without it.
