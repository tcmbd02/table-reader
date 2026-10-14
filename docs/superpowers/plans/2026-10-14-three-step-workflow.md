# Three-Step Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rearrange Table Reader's seven screens into three pages (1 Upload → 2 Check reading → 3 Payroll) with step
buttons at the top and buttons between the pages, without changing any calculation or stored data.

**Architecture:** The server keeps its calculation and storage. It gains two read requests built from the existing
`month_state` (`GET /api/payroll/{month}/people` for step 3, `GET /api/payroll/{month}/files` for step 2), and the job
list gains each file's yellow-cell count. The front end (plain JS, no build) gets three `<main>` sections and one
script per page (`upload.js`, `check.js`, `people.js`), a router (`steps.js`), and reuses the existing parts (file view,
column choice, employee view, Look panel, pay table, settings) inside them. The two old company requests go at the end.

**Tech Stack:** Python 3.14, FastAPI, pytest; plain HTML/CSS/JS; headless Edge click-throughs (Chrome DevTools
Protocol over `websockets`).

**Spec:** `docs/superpowers/specs/2026-10-14-three-step-workflow-design.md` (read it first; this plan argues from it).

## Global Constraints

- Branch `three-steps` (already made from `pdf-text`, holds the spec). Commit after every task. **Never push, merge,
  rebuild the app or touch the `download` branch** without the user's OK.
- The repo is PUBLIC: no real names, documents, results or screenshots. Test data uses made-up names only (MAJU JAYA,
  BINA, A & B (M), ALI, SITI, ZUL, AMIN). Scan every diff before committing: `git diff --cached | grep -nE '[A-Z]{3,}'`
  and look at every capitalised word.
- Never guess: nothing here may fill a cell, a figure or an employee by itself. `result.json` is never modified.
- Every new text shown on the page goes through `t()` / `tn()` and gets a Malay entry in `static/i18n.js` (`MS`).
  The Edit Payroll window's labels stay English. `tools/check_i18n.py` must report `missing Malay: 0` and
  `tools/check_patterns.py` `0 not translated` at the end of every front-end task.
- All text from the server is inserted with `textContent` (the `el()` helper), never `innerHTML`.
- `sessionStorage` / `localStorage` are read and written only inside `try/catch` (the `remember` / `recall` / `forget`
  helpers); the page must work when they throw.
- Environment: Windows, PowerShell 5.1 (no `&&`), Git Bash available. This worktree has no `.venv`: use
  `PY="C:/Users/TENGA CEKAP/Documents/table-reader/.venv/Scripts/python.exe"`. Tests: `"$PY" -m pytest -q`.
  Write throwaway scripts to the session scratchpad, not the repo. Never use bare `git stash`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A company name with signs** (`A & B (M)`, `/`, `#`, `%`) in `#/payroll/<month>/c/<company>` and in the buttons
   from step 2 to step 3 — it must open that company, not another or none (test: Task 6 click-through).
2. **A remembered place that no longer exists** (an employee removed in another tab, a file id that is gone) — the
   step opens on its first screen instead of an error or a redirect loop (tests: Task 5 and Task 6 click-throughs).
3. **Typing in the Edit Payroll window, then pressing a step button or another employee straight away** — what was
   typed is saved, not lost (test: Task 7 click-through).
4. **A file still being read when it is chosen in step 2** — the list and the file show its progress, nothing about
   payroll, Download disabled; when it finishes, the list and the file update by themselves (test: Task 5
   click-through with a slow reader).
5. **A month with no files** — step 3 shows "No employees for this month yet…" with a button to step 1, step 2 shows
   "No files for <month>…"; no endless redirect (tests: Task 5 and Task 6 click-throughs).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `jobs.py` | `list_jobs()` gains `cells_to_check` (cached on the files' size and time) | 2 |
| `companies.py` | pure: `file_problems()`, `needs_you()`, `people_view()` | 1 |
| `app.py` | `GET /api/payroll/{month}/people`, `GET /api/payroll/{month}/files`; later the two old requests removed | 2, 8 |
| `static/index.html` | three `<main>`: `upload`, `check`, `people`; the step buttons | 4 |
| `static/app.js` | shared: `el`, `api`, Claude sign-in, Quit, storage helpers, step badges, file-company helpers | 4, 5 |
| `static/steps.js` | addresses (new and old), step buttons, remembered places, working month, refresh on return; loaded last | 4 |
| `static/upload.js` | step 1 | 4 |
| `static/check.js` | step 2: file list, file view (moved from `app.js`), "This file needs you", foot buttons | 5 |
| `static/columns.js` | the column choice opened under a file (was `layout.js`) | 5 |
| `static/paycommon.js` | gains `monthTitle`, `shiftMonth` | 5 |
| `static/people.js` | step 3: top bar, list, company panel, employee "Needs you", Previous/Next (replaces `companies.js`) | 6 |
| `static/employee.js`, `look.js`, `paytable.js`, `settings.js` | adapted to live inside step 3 | 6, 7 |
| `static/app.css` | step buttons, two-column layout | 4 |
| `tools/clickthrough/` | headless Edge click-through harness and scenarios (made-up data) | 4–7 |
| `tools/check_i18n.py` | reads every `static/*.js` instead of a fixed list | 4 |
| `tests/test_companies.py`, `tests/test_jobs.py`, `tests/test_app.py` | tests | 1–8 |
| guides, `PROGRESS.md`, `NEXT-SESSION.md` | docs | 8 |

Final script order in `index.html`: `i18n.js, app.js, paycommon.js, upload.js, check.js, columns.js, people.js,
employee.js, look.js, paytable.js, settings.js, steps.js`.

---

### Task 1: Pure functions for step 2's file problems and step 3's list

**Files:**
- Modify: `companies.py` (add after `overview()`, before `LAYOUT_FIGURE_ROWS`)
- Test: `tests/test_companies.py` (append)

**Interfaces:**
- Produces: `companies.file_problems(files, layouts, other, loose) -> dict[str, list[dict]]`,
  `companies.needs_you(items: list[dict]) -> bool`,
  `companies.people_view(views: list[dict], known: list[str], problems: dict[str, list[dict]]) -> dict`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_companies.py`)

```python
def test_file_problems_are_grouped_by_file_with_their_company():
    out = companies.file_problems(
        {"BINA": [{"kind": "month", "doc": "d1", "name": "BINA ZUL.png", "why": "No month."}]},
        {"MAJU JAYA": [{"kind": "layout", "signature": "s", "doc": "d1", "page": 1, "name": "BINA ZUL.png",
                        "columns": ["Rate"], "confirmed": False, "hours_column": None}]},
        {"BINA": [{"doc": "d2", "name": "BINA NOTICE.png", "month": "none"}]},
        [{"id": "d3", "name": "LOOSE.png"}])
    assert [(i["kind"], i["company"]) for i in out["d1"]] == [("month", "BINA"), ("layout", "MAJU JAYA")]
    assert out["d2"] == [{"kind": "other", "doc": "d2", "name": "BINA NOTICE.png", "month": "none", "company": "BINA"}]
    assert out["d3"] == [{"kind": "company", "doc": "d3", "name": "LOOSE.png", "company": ""}]
    assert companies.needs_you(out["d1"]) and companies.needs_you(out["d3"])
    assert not companies.needs_you(out["d2"])            # set aside: shown on the file, asks nothing


def test_people_view_gives_each_employee_their_own_items_and_counts_files():
    views = [{"company": "MAJU JAYA", "status": "needs", "needs": 2, "waiting": 0,
              "items": [{"kind": "settings", "company": "MAJU JAYA"},
                        {"kind": "empno", "employee": "e1", "why": "empty"}],
              "employees": [{"id": "e1", "name": "ALI", "emp_no": "", "status": "needs"},
                            {"id": "e2", "name": "SITI", "emp_no": "MJ2", "status": "ready"}],
              "million_new": [], "settings": {"own": True}},
             {"company": "", "status": "none", "needs": 0, "waiting": 0, "items": [], "employees": [],
              "million_new": []}]
    problems = companies.file_problems(
        {"MAJU JAYA": [{"kind": "unplaced", "ref": "d1", "doc": "d1", "name": "A.png", "readable": True}]}, {},
        {"MAJU JAYA": [{"doc": "d2", "name": "B.png", "month": "none"}]}, [{"id": "d3", "name": "LOOSE.png"}])
    out = companies.people_view(views, ["BINA"], problems)
    assert [r["company"] for r in out["companies"]] == ["MAJU JAYA", "BINA", ""]     # sorted as the overview was
    rows = {r["company"]: r for r in out["companies"]}
    assert rows["MAJU JAYA"]["items"] == [{"kind": "settings", "company": "MAJU JAYA"}]
    ali, siti = rows["MAJU JAYA"]["employees"]
    assert [i["kind"] for i in ali["items"]] == ["empno"] and siti["items"] == []
    assert rows["MAJU JAYA"]["files_needing"] == 1        # d2 is only set aside
    assert rows[""]["files_needing"] == 1 and rows["BINA"]["files_needing"] == 0 and rows["BINA"]["employees"] == []
    assert rows["MAJU JAYA"]["settings"] == {"own": True} and rows["MAJU JAYA"]["needs"] == 2
    assert (out["files_needing"], out["employees"], out["ready_employees"]) == (2, 2, 1)
```

- [ ] **Step 2: Run them to see them fail**

Run: `"$PY" -m pytest -q tests/test_companies.py -k "file_problems or people_view"`
Expected: FAIL with `AttributeError: module 'companies' has no attribute 'file_problems'`.

- [ ] **Step 3: Implement** (in `companies.py`, after `overview()`)

```python
def file_problems(files: dict[str, list[dict]], layouts: dict[str, list[dict]], other: dict[str, list[dict]],
                  loose: list[dict]) -> dict[str, list[dict]]:
    """Step 2's "This file needs you": {file id: items}, each item with its ``company``. ``files``: {company: the
    "unplaced" and "month" items of its files}; ``layouts``: {company: "layout" items}; ``other``: {company: files set
    aside or read as another month and on nobody there, [{doc, name, month}]}, as "other" items; ``loose``: finished
    files with no company, [{id, name}], as "company" items. In one file: unplaced / month, layouts, other, company."""
    out: dict[str, list[dict]] = {}
    for source in (files, layouts):
        for company, items in source.items():
            for item in items:
                out.setdefault(item["doc"], []).append({**item, "company": company})
    for company, rows in other.items():
        for f in rows:
            out.setdefault(f["doc"], []).append({"kind": "other", "doc": f["doc"], "name": f["name"],
                                                 "month": f["month"], "company": company})
    for d in loose:
        out.setdefault(d["id"], []).append({"kind": "company", "doc": d["id"], "name": d["name"], "company": ""})
    return out


def needs_you(items: list[dict]) -> bool:
    """A file needs the user unless all it has is "set aside / another month" (shown so a mistake can be put right)."""
    return any(i["kind"] != "other" for i in items)


def people_view(views: list[dict], known: list[str], problems: dict[str, list[dict]]) -> dict:
    """Step 3's list. ``views``: company_view of each company made WITHOUT file and layout items (so a company's
    status and count are only its own and its employees'); ``known``: companies listed even with nothing this month
    (as overview); ``problems``: file_problems. Rows sorted as overview sorts them, each with its company items
    (those about no one employee), its employees each with their own items, million_new, settings, and
    ``files_needing`` (its files that need the user in step 2; files with no company count under "")."""
    over = overview(views, known)
    by_company = {v["company"]: v for v in views}
    counts: dict[str, int] = {}
    for items in problems.values():
        if needs_you(items):
            company = next(i["company"] for i in items if i["kind"] != "other")
            counts[company] = counts.get(company, 0) + 1
    rows = []
    for row in over["companies"]:
        v = by_company.get(row["company"], {"items": [], "employees": [], "million_new": []})
        rows.append({**row,
                     "items": [i for i in v["items"] if "employee" not in i],
                     "employees": [{**e, "items": [i for i in v["items"] if i.get("employee") == e["id"]]}
                                   for e in v["employees"]],
                     "million_new": v["million_new"], "settings": v.get("settings"),
                     "files_needing": counts.get(row["company"], 0)})
    return {"companies": rows, "ready_companies": over["ready_companies"], "ready_employees": over["ready_employees"],
            "employees": sum(len(r["employees"]) for r in rows), "files_needing": sum(counts.values())}
```

- [ ] **Step 4: Run the tests**

Run: `"$PY" -m pytest -q tests/test_companies.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add companies.py tests/test_companies.py
git commit -m "Payroll: file problems grouped by file (step 2) and the people list (step 3), as pure functions"
```

---

### Task 2: The server's two new requests and each file's yellow-cell count

**Files:**
- Modify: `jobs.py` (`Jobs.__init__`, `list_jobs`, `get_job`; new `_cells_to_check`)
- Modify: `app.py` (`file_items` returns the month of each file; `month_state`; new `step_views`, two routes after
  `payroll_company`)
- Test: `tests/test_jobs.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: Task 1's three functions.
- Produces:
  - `GET /api/jobs` rows gain `cells_to_check` (int for a finished file, `None` otherwise).
  - `GET /api/payroll/{month}/people` → `{month, companies: [{company, status, needs, waiting, own, items,
    employees: [{id, emp_no, name, status, days_worked, ot_1_5, ot_rest_day, items}], million_new, settings,
    files_needing}], files_needing, employees, ready_employees, ready_companies, checked_with_million, settings,
    added_by_themselves, numbered}`. A `look` item's `cards` are `[{id, name}]`.
  - `GET /api/payroll/{month}/files` → `{month, files: {doc: [items with company]}, months: {doc: month|null},
    employees: {doc: [{id, name}]}, choices: {company: [{id, name, emp_no}]}, needs: int}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_jobs.py`:

```python
def test_the_file_list_says_how_many_cells_are_left_to_check(done):
    s, jid = done
    [row] = s.list_jobs()
    assert row["cells_to_check"] == 2
    s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": "7:30"}])
    assert s.list_jobs()[0]["cells_to_check"] == 1 == s.get_job(jid)["cells_to_check"]
```

Append to `tests/test_app.py` (after `test_the_overview_and_a_company_screen`):

```python
def test_step_3_people_and_step_2_files(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        import_million(c, ("ABM001", "ALI"), ("BINA001", "SITI"))
        for name in (f"A & B (M) ALI SEPT {YEAR}.png", f"BINA SITI SEPT {YEAR}.png", "BINA ZUL.png", "LOOSE.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        set_company(c, "A & B", "A & B (M)")
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        people = c.get(f"/api/payroll/{month}/people").json()
        rows = {r["company"]: r for r in people["companies"]}
        assert set(rows) == {"A & B (M)", "BINA", ""}
        [ali] = rows["A & B (M)"]["employees"]
        assert ali["name"] == "ALI" and [i["kind"] for i in ali["items"]] == ["offer"]
        assert rows["A & B (M)"]["items"] == [] and rows["A & B (M)"]["status"] == "needs"
        for r in people["companies"]:                                  # the user presses every "Use ..."
            for e in r["employees"]:
                for i in e["items"]:
                    if i["kind"] == "offer":
                        c.put(f"/api/payroll/{month}/employees/{e['id']}", json={"emp_no": i["emp_no"]})
        people = c.get(f"/api/payroll/{month}/people").json()
        rows = {r["company"]: r for r in people["companies"]}
        # BINA's only problem is a file with no month: counted for step 2, its employees are ready here
        assert rows["BINA"]["status"] == "ready" and rows["BINA"]["files_needing"] == 1
        assert rows[""]["status"] == "none" and rows[""]["files_needing"] == 1 and rows[""]["employees"] == []
        assert (people["files_needing"], people["employees"], people["ready_employees"]) == (2, 2, 2)
        assert people["checked_with_million"] is True and "day_types" in people["settings"]
        files = c.get(f"/api/payroll/{month}/files").json()
        ids = {j["name"]: j["id"] for j in c.get("/api/jobs").json()}
        siti_file, zul_file = ids[f"BINA SITI SEPT {YEAR}.png"], ids["BINA ZUL.png"]
        assert [(i["kind"], i["company"]) for i in files["files"][zul_file]] == [("month", "BINA")]
        assert files["files"][ids["LOOSE.png"]] == [{"kind": "company", "doc": ids["LOOSE.png"], "name": "LOOSE.png",
                                                     "company": ""}]
        assert files["months"][siti_file] == month and files["months"][zul_file] is None
        assert [e["name"] for e in files["employees"][siti_file]] == ["SITI"]
        assert [e["name"] for e in files["choices"]["BINA"]] == ["SITI"] and files["needs"] == 0
        assert all(isinstance(j["cells_to_check"], int) for j in c.get("/api/jobs").json())
        assert c.get("/api/payroll/nonsense/people").status_code == 400
        assert c.get("/api/payroll/nonsense/files").status_code == 400


def test_a_look_item_in_step_3_names_its_cards(tmp_path):
    store, client = company_client(tmp_path, day_9_unclear)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        [row] = [r for r in c.get(f"/api/payroll/{month}/people").json()["companies"] if r["company"] == "BINA"]
        [look] = [i for i in row["employees"][0]["items"] if i["kind"] == "look"]
        assert look["places"] == 1 and look["cards"] == [{"id": c.get("/api/jobs").json()[0]["id"],
                                                          "name": f"BINA SITI SEPT {YEAR}.png"}]
```

(`day_9_unclear` already exists further down in `tests/test_app.py`; Python finds it at call time.)

- [ ] **Step 2: Run them to see them fail**

Run: `"$PY" -m pytest -q tests/test_jobs.py tests/test_app.py -k "cells_are_left or step_3 or look_item_in_step_3"`
Expected: FAIL (`KeyError: 'cells_to_check'`, 404 on `/people`).

- [ ] **Step 3: Implement the yellow-cell count in `jobs.py`**

In `Jobs.__init__`, next to the other attributes, add:

```python
        self._yellow: dict[str, tuple[tuple, int]] = {}    # id -> (sizes and times of result/edits, cells to check)
```

Replace `get_job` and add `_cells_to_check` right after it:

```python
    def get_job(self, job_id: str) -> dict:
        """Status and progress, plus how many cells the user still has to check."""
        meta = self._meta(job_id)
        meta["cells_to_check"] = self._cells_to_check(job_id) if meta["status"] == "done" else None
        return meta

    def _cells_to_check(self, job_id: str) -> int:
        """count_to_check of a finished document, worked out again only when its reading or corrections change on
        disk (so the file list can carry it on every refresh)."""
        d = self._dir(job_id)
        key = tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None
                    for p in (d / "result.json", d / "edits.json"))
        hit = self._yellow.get(job_id)
        if hit is not None and hit[0] == key:
            return hit[1]
        n = count_to_check(merged_pages(self.load_result(job_id), self.load_edits(job_id)))
        self._yellow[job_id] = (key, n)
        return n
```

In `list_jobs`, replace the loop `for m in out: m.setdefault("company", "")` with:

```python
        for m in out:
            m.setdefault("company", "")                            # files added before companies existed
            m["cells_to_check"] = None
            if m.get("status") == "done":
                try:
                    m["cells_to_check"] = self._cells_to_check(m["id"])
                except (OcrError, OSError, ValueError):
                    pass                                           # a reading that cannot be opened: no count
```

(`jobs.py` already has `from ocr import OcrError`.)

- [ ] **Step 4: Implement the two requests in `app.py`**

1. In `file_items`, collect each finished file's month and return it as a third value: add
   `months: dict[str, str | None] = {}` next to `other: dict[...] = {}`; inside the loop, the `try:` block loads the
   pages, `found, why = month_of(...)` and `cards = ...`, and its `except` ends with `continue` — add
   `months[d["id"]] = found` as the first statement right after that `try`/`except`; change the last line to
   `return out, other, months`; and change the signature to:

```python
    def file_items(plan: dict, docs: list[dict], month: str) -> tuple[dict[str, list[dict]], dict[str, list[dict]],
                                                                       dict[str, str | None]]:
```

   Add to its docstring: `Also {file id: its month} (None when it has none) for every finished file with a company.`

2. In `month_state`, change `**dict(zip(("files", "other"), file_items(plan, docs, month)))` to
   `**dict(zip(("files", "other", "months"), file_items(plan, docs, month)))`.

3. After `payroll_company` (the `@app.get("/api/payroll/{month}/company")` route), add:

```python
    def step_views(state: dict) -> tuple[list[dict], dict[str, list[dict]]]:
        """Each company's view without its files' items (step 3), and every file's problems (step 2)."""
        loose = [{"id": d["id"], "name": d["name"]} for d in state["docs"] if not d["company"]]
        problems = companies.file_problems(state["files"], state["layouts"], state["other"], loose)
        names = set(state["company_of"]) | {i["company"] for items in problems.values() for i in items}
        views = [companies.company_view(c, state["plan"], state["results"], state["company_of"], state["million"],
                                        state["offers"], state["held"], [],
                                        payroll.settings_view(state["plan"], c) if c else None)
                 for c in names]
        return views, problems

    @app.get("/api/payroll/{month}/people")
    def payroll_people(month: str):
        """Step 3: every company of the month with its employees and what needs the user about each. The files'
        problems are only counted here (files_needing); step 2 lists them (GET .../files)."""
        state = month_state(month)
        views, problems = step_views(state)
        known = sorted({j["company"] for j in store.list_jobs() if j.get("company")})
        out = companies.people_view(views, known, problems)
        doc_names = {d["id"]: d["name"] for d in state["docs"]}
        for row in out["companies"]:
            for e in row["employees"]:
                for item in e["items"]:
                    if "cards" in item:
                        item["cards"] = [{"id": c, "name": doc_names.get(c, "")} for c in item["cards"]]
        return {"month": month, **out, "checked_with_million": state["million"] is not None,
                "settings": payroll.settings_view(state["plan"], "")["default"],
                "added_by_themselves": state["added"], "numbered": state["numbered"]}

    @app.get("/api/payroll/{month}/files")
    def payroll_files(month: str):
        """Step 2: each file's problems in ``month``, the month each finished file is for, the employees each file's
        cards are on, the employees of each company (for "whose card is this?") and how many things step 3 has."""
        state = month_state(month)
        views, problems = step_views(state)
        plan = state["plan"]
        on: dict[str, list[dict]] = {}
        for e in plan["employees"]:
            for doc in dict.fromkeys(payroll.split_part(ref)[0] for ref in e["jobs"]):
                on.setdefault(doc, []).append({"id": e["id"], "name": e["name"]})
        choices: dict[str, list[dict]] = {}
        for e, company in zip(plan["employees"], state["company_of"]):
            choices.setdefault(company, []).append({"id": e["id"], "name": e["name"], "emp_no": e["emp_no"]})
        return {"month": month, "files": problems, "months": state["months"], "employees": on, "choices": choices,
                "needs": sum(v["needs"] for v in views)}
```

   `/api/jobs` serves `store.list_jobs()` already (check `grep -n '"/api/jobs")' -A3 app.py`); nothing else to change.
   Use the CPU time check below to be sure the job list is not slowed down.

- [ ] **Step 5: Run the tests**

Run: `"$PY" -m pytest -q`
Expected: all pass (551+ tests).

- [ ] **Step 6: Check the job list stays fast on the real data (read-only, counts only)**

Write `<scratchpad>/joblist_speed.py`:

```python
"""Time GET /api/jobs twice on a COPY of the real data (prints only counts and seconds)."""
import os, shutil, sys, tempfile, time
from pathlib import Path
real = Path(os.path.expanduser("~/Documents/Table Reader"))
copy = Path(tempfile.mkdtemp()) / "Table Reader"
shutil.copytree(real, copy)
os.environ["TABLE_READER_HOME"] = str(copy)
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
import app as app_module
from jobs import Jobs, default_root
with TestClient(app_module.create_app(Jobs(default_root(), reader=lambda image: {})), base_url="http://localhost") as c:
    for n in (1, 2):
        t0 = time.time(); rows = c.get("/api/jobs").json()
        print(f"call {n}: {len(rows)} files, {sum(r['cells_to_check'] or 0 for r in rows)} cells, {time.time()-t0:.2f}s")
shutil.rmtree(copy.parent)
```

Run: `"$PY" <scratchpad>/joblist_speed.py "$(pwd)"`
Expected: the second call well under 0.5 s. Delete the script afterwards (it deletes its copy itself).
(`default_root()` is `TABLE_READER_HOME/jobs`, so pointing `TABLE_READER_HOME` at the copy is enough.)

- [ ] **Step 7: Commit**

```bash
git add jobs.py app.py tests/test_jobs.py tests/test_app.py
git commit -m "Payroll: step 3's people list and step 2's file problems as their own requests; the file list carries each file's cells to check"
```

---

### Task 3: Move the tests off the company screen's requests

The old `GET /api/payroll/{month}/companies` and `.../company` stay until Task 8 (the old screens still use them until
then), but no test should depend on them any more.

**Files:**
- Modify: `tests/test_app.py`

**Interfaces:**
- Produces (test helpers in `tests/test_app.py`): `overview(c, month) -> dict` (the `/people` answer) and
  `company(c, month, name) -> dict` with keys `company, month, status, items, employees, million_new, settings,
  files, other_files`.

- [ ] **Step 1: Add the helpers** right after `import_million` in `tests/test_app.py`:

```python
def overview(c, month):
    """Step 3's month (GET /people). Opening it joins newly read files of the month, as opening Payroll does."""
    r = c.get(f"/api/payroll/{month}/people")
    assert r.status_code == 200, r.text
    return r.json()


def company(c, month, name):
    """One company the way the company screen showed it before the three steps, from step 3 (its own and its
    employees' items, its employees) and step 2 (its files' items): {company, month, status, items, employees,
    million_new, settings, files (no company: the files waiting for one), other_files}. Item order: the company's own,
    its files' (unplaced / month), its card layouts, its employees'."""
    people, files = overview(c, month), c.get(f"/api/payroll/{month}/files").json()
    row = next((r for r in people["companies"] if r["company"] == name),
               {"status": "none", "items": [], "employees": [], "million_new": [], "settings": None})
    mine = [i for items in files["files"].values() for i in items if i["company"] == name]
    items = (row["items"] + [i for i in mine if i["kind"] in ("unplaced", "month")]
             + [i for i in mine if i["kind"] == "layout"] + [i for e in row["employees"] for i in e["items"]])
    return {"company": name, "month": month, "status": row["status"], "items": items,
            "employees": row["employees"], "million_new": row["million_new"], "settings": row["settings"],
            "files": [{"id": i["doc"], "name": i["name"]} for i in mine if i["kind"] == "company"],
            "other_files": [{"doc": i["doc"], "name": i["name"], "month": i["month"]}
                            for i in mine if i["kind"] == "other"]}
```

- [ ] **Step 2: Replace the calls mechanically.** Write `<scratchpad>/movetests.py`:

```python
import re
from pathlib import Path

p = Path("tests/test_app.py")
s = p.read_text(encoding="utf-8")
rules = [
    (r'c\.get\(f"/api/payroll/\{(\w+)\}/company", params=\{"name": ([^}]+)\}\)\.json\(\)', r"company(c, \1, \2)"),
    (r'c\.get\(f"/api/payroll/(\{YEAR\}-\d\d)/company", params=\{"name": ([^}]+)\}\)\.json\(\)', r'company(c, f"\1", \2)'),
    (r'c\.get\(f"/api/payroll/\{(\w+)\}/companies"\)\.json\(\)', r"overview(c, \1)"),
    (r'c\.get\(f"/api/payroll/(\{YEAR\}-\d\d)/companies"\)\.json\(\)', r'overview(c, f"\1")'),
    (r'^(\s*)c\.get\(f"/api/payroll/\{(\w+)\}/companies"\)(\s*#.*)?$', r"\1overview(c, \2)\3"),
]
for pattern, to in rules:
    s, n = re.subn(pattern, to, s, flags=re.M)
    print(n, pattern[:50])
p.write_text(s, encoding="utf-8", newline="\n")
```

Run: `"$PY" <scratchpad>/movetests.py` (from the worktree folder), then
`grep -n '/company"\|/companies"' tests/test_app.py` and fix every line it still prints by hand:

- `test_payroll_api_refuses_bad_input`: `client.get("/api/payroll/nonsense/companies").status_code == 400` →
  `client.get("/api/payroll/nonsense/people").status_code == 400`.
- Lines that check `.status_code` of the overview (`test_a_card_no_longer_in_recent_files...`,
  `test_the_overview_opens_when_a_file_is_being_read...`, `test_the_overview_opens_on_a_month_whose_stored_plan...`,
  `test_an_old_bad_plan_is_left_alone...`): `c.get(f"/api/payroll/{month}/companies")` →
  `c.get(f"/api/payroll/{month}/people")`, and `c.get(f"/api/payroll/{month}/company", params={"name": "BINA"})` →
  `c.get(f"/api/payroll/{month}/files")`.

- [ ] **Step 3: Fix what changed on purpose.** A row's `employees` is now a list, and a company's status no longer
  counts its files (spec §9):
  - every `r["employees"] == N` / `["employees"] == N` on an overview row → `len(r["employees"]) == N`;
  - in `test_the_overview_and_a_company_screen`, replace the two lines about BINA and "" with:

```python
        assert len(rows["BINA"]["employees"]) == 1 and rows["BINA"]["status"] == "ready"
        assert rows["BINA"]["files_needing"] == 1                      # a file of BINA has no month: step 2
        assert rows[""]["files_needing"] == 1 and rows[""]["employees"] == []   # a file with no company is not lost
```

- [ ] **Step 4: Run the tests**

Run: `"$PY" -m pytest -q`
Expected: all pass. If a test compares a whole file item dict, it now also has `"company"`: add it to the expected
dict (never drop the check).

- [ ] **Step 5: Commit**

```bash
git add tests/test_app.py
git commit -m "Tests: payroll tests read step 3's and step 2's requests instead of the company screen's"
```

---

### Task 4: The page shell — step buttons, addresses, Upload page, click-through harness

After this task the app shows the top bar with the three steps and a working Upload page. Steps 2 and 3 open the
Upload page until Tasks 5–7 add their scripts (the branch is not merged before Task 8).

**Files:**
- Rewrite: `static/index.html`
- Create: `static/steps.js`, `static/upload.js`
- Modify: `static/app.js`, `static/app.css`, `static/i18n.js`, `tools/check_i18n.py`
- Create: `tools/clickthrough/drive.py`, `tools/clickthrough/serve.py`, `tools/clickthrough/run.sh`,
  `tools/clickthrough/README.md`, `tools/clickthrough/upload_page.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces (globals other scripts call): in `app.js` — `remember(key, value)`, `recall(key) -> string|null`,
  `forget(key)`, `stepBadge(step: "check"|"payroll", n: number)`, `refreshCheckBadge(jobs)`, `companyNames(jobs)`,
  `companyBox(j, companies, done: () => void, say: (text, kind) => void)`, `renderCompanyFilter(jobs, onChange)`,
  `companyMatches(company)`, `companyFilter`, `editingCompany`, `progressText(j)`, `suggestCompany(name)`;
  in `steps.js` — `route()`, `workMonth() -> "YYYY-MM"`, `setWorkMonth(month)`, `showStep(step)`;
  in `upload.js` — `showUpload()`.
- Each later page script defines one entry point that `route()` calls if it exists: `showCheck(fileId|null,
  columns|null)` (Task 5), `showPeople(month, {employee, look, company})` (Task 6); `emLeave()` (Task 7) is called on
  every route change.

- [ ] **Step 1: Write the failing page tests.** In `tests/test_app.py` replace
  `test_the_page_has_the_company_first_screens`, `test_the_company_chooser_for_files_is_on_the_start_page_only` and the
  script list in `test_script_addresses_change_when_a_script_changes` / `test_browser_must_not_keep_an_old_script...`:

```python
SCRIPTS = ["i18n.js", "app.js", "paycommon.js", "upload.js", "steps.js"]       # grows with Tasks 5-7


def test_browser_must_not_keep_an_old_script_after_an_update(client):
    for path in ["/", "/app.css", *(f"/{s}" for s in SCRIPTS)]:
        assert client.get(path).headers["cache-control"] == "no-cache", path
    assert client.get("/api/ping").headers["cache-control"] == "no-store"


def test_the_page_has_the_three_steps(client):
    html = client.get("/").text
    for id_ in ("step-upload", "step-check", "step-payroll", "step-check-n", "step-payroll-n"):
        assert f'id="{id_}"' in html
    assert html.index('<main id="upload"') < html.index('<main id="check"') < html.index('<main id="people"')
    for gone in ('id="home"', 'id="month"', 'id="nav-payroll"', 'id="back"', 'id="mo-back"', 'id="co-back"',
                 'id="em-back"', 'id="co-tab-employees"', 'id="recent-none"', "companies.js", "layout.js"):
        assert gone not in html, gone
    # the parts that move into the steps keep their ids: the file view and the column choice in step 2, the month bar,
    # company panel, employee view and Look panel in step 3
    check = html[html.index('<main id="check"'):html.index('<main id="people"')]
    people = html[html.index('<main id="people"'):]
    for id_ in ("doc", "pages", "download", "ck-files", "ck-month", "ck-needs", "ck-foot", "layout", "ly-save",
                "company-box"):
        assert f'id="{id_}"' in check, id_
    for id_ in ("mo-run", "mo-settings-open", "mo-csv", "pp-list", "pp-search", "company", "co-pay", "co-add",
                "co-million", "employee", "em-needs", "em-cards", "em-window", "em-walk", "look", "lk-accept"):
        assert f'id="{id_}"' in people, id_


def test_script_addresses_change_when_a_script_changes(client, tmp_path, monkeypatch):
    import re
    import shutil

    page = client.get("/").text
    stamped = re.findall(r'(?:src|href)="([\w.-]+)\?v=([0-9a-f]{8})"', page)
    assert [name for name, _ in stamped] == ["app.css", *SCRIPTS]
    assert client.get("/index.html").text == page
    assert all(client.get(f"/{name}?v={v}").status_code == 200 for name, v in stamped)

    copy = tmp_path / "static"
    shutil.copytree(app_module.static_dir(), copy)
    (copy / "steps.js").write_text("// an update\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "static_dir", lambda: copy)
    after = dict(re.findall(r'(?:src|href)="([\w.-]+)\?v=([0-9a-f]{8})"', app_module.page_html()))
    before = dict(stamped)
    assert after["steps.js"] != before["steps.js"] and after["app.js"] == before["app.js"]
```

Run: `"$PY" -m pytest -q tests/test_app.py -k "three_steps or old_script or script_addresses"` — Expected: FAIL.

- [ ] **Step 2: Rewrite `static/index.html`** (complete file; the long texts are copied unchanged from today's file):

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Table Reader</title>
<link rel="stylesheet" href="app.css">
</head>
<body>
<header>
  <h1>Table Reader</h1>
  <nav class="steps" aria-label="Steps" data-t-aria>
    <a id="step-upload" class="step" href="#/"><span data-t>1 Upload</span></a>
    <a id="step-check" class="step" href="#/check"><span data-t>2 Check reading</span> <span id="step-check-n" class="badge" hidden></span></a>
    <a id="step-payroll" class="step" href="#/payroll"><span data-t>3 Payroll</span> <span id="step-payroll-n" class="badge" hidden></span></a>
  </nav>
  <div id="claude-box" class="claude-box" aria-live="polite" data-t>Checking Claude…</div>
  <button id="lang" class="link" type="button">Bahasa Melayu</button>
  <button id="quit" class="link" title="Close Table Reader on this computer" data-t data-t-title>Quit Table Reader</button>
</header>

<main id="upload">
  <div id="drop" class="drop" tabindex="0" role="button" aria-label="Choose files to read" data-t-aria>
    <p class="drop-big" data-t>Drop scans or photos here</p>
    <p><span data-t>PDF, JPG or PNG — or</span> <u data-t>click to choose files</u></p>
    <input id="file-input" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,application/pdf,image/*" multiple hidden>
  </div>
  <div id="upload-messages"></div>
  <p class="legend"><span data-t>No clicks: save files into the Inbox folder (one folder per company) and they are read by themselves. Every finished table is also kept as a CSV in the Tables folder.</span>
    <button id="open-inbox" type="button" data-t>Open the Inbox folder</button>
    <button id="open-tables" type="button" data-t>Open the Tables folder</button></p>
  <section class="card">
    <div class="recent-head"><h2 data-t>Just added</h2><span id="up-state" class="muted" aria-live="polite"></span></div>
    <ul id="recent" class="recent"></ul>
    <p id="recent-empty" class="muted" hidden data-t>Nothing is being read. Files you add here are listed until you close this tab.</p>
    <div class="need-buttons foot"><button id="up-check" class="primary" type="button" data-t>Check them →</button></div>
  </section>
</main>

<main id="check" hidden>
  <div id="ck-error" class="banner error" hidden></div>
  <div class="split">
    <aside class="side" aria-label="Files" data-t-aria>
      <div class="side-filters">
        <div id="company-box" class="company-box" hidden></div>
        <label class="side-month"><span data-t>Month</span> <select id="ck-month"></select></label>
      </div>
      <ul id="ck-files" class="side-list"></ul>
    </aside>
    <section class="pane">
      <div id="ck-empty" class="card" hidden><p id="ck-empty-text"></p>
        <button id="ck-to-upload" type="button" data-t>Go to step 1</button></div>
      <div id="doc" hidden>
        <div class="doc-bar">
          <h2 id="doc-name"></h2>
          <span id="ck-company"></span>
          <div class="doc-actions">
            <button id="next-check" class="secondary" hidden>Go to next cell to check</button>
            <button id="cancel" hidden data-t>Cancel reading</button>
            <button id="continue" hidden data-t>Continue reading</button>
            <button id="download" class="primary" data-t>Download CSV</button>
          </div>
        </div>
        <p id="doc-status" class="doc-status"></p>
        <div id="doc-error" class="banner error" hidden></div>
        <section id="ck-needs" class="card" hidden></section>
        <section id="layout" class="card" hidden>
          <div class="doc-bar">
            <h3 id="ly-title"></h3>
            <div class="doc-actions">
              <button id="ly-ask" type="button" data-t>Ask Claude</button>
              <button id="ly-as-is" type="button" data-t>It is right as it is</button>
              <button id="ly-save" class="primary" type="button" data-t>Save</button>
              <button id="ly-back" type="button" data-t>Close</button>
            </div>
          </div>
          <div id="ly-error" class="banner error" hidden></div>
          <div id="ly-body" hidden>
            <p class="legend" data-t>Say once what each column of this card holds. It is kept for every card with the same headings, for every company and month. Claude can suggest it: it is shown only the headings and how the values are written (digits as 9, letters as A), never the names or figures.</p>
            <div id="ly-note" class="banner info" hidden></div>
            <div class="page-grid">
              <div id="ly-rows"></div>
              <div id="ly-picture" class="page-image"></div>
            </div>
          </div>
        </section>
        <div id="pages"></div>
        <div id="ck-foot" class="need-buttons foot"></div>
      </div>
    </section>
  </div>
</main>

<main id="people" hidden>
  <div class="doc-bar">
    <h2 id="mo-title"></h2>
    <div class="doc-actions">
      <button id="mo-prev" type="button" aria-label="Month before" data-t-aria>&lt;</button>
      <button id="mo-next" type="button" aria-label="Month after" data-t-aria>&gt;</button>
      <button id="mo-settings-open" type="button" data-t>Month settings</button>
      <button id="mo-million-import" type="button" data-t>Import employee list from Million</button>
      <input id="mo-million-file" type="file" accept=".xls" hidden>
      <button id="mo-csv" type="button" data-t>Download payroll CSV</button>
      <button id="mo-run" class="primary" data-t>Make the month's Million file (all companies)</button>
    </div>
  </div>
  <div id="mo-error" class="banner error" hidden></div>
  <div id="mo-info" class="banner info" hidden></div>
  <div id="mo-run-result" class="banner info" hidden></div>
  <section id="mo-settings" class="card" hidden></section>
  <p id="mo-total" class="legend"></p>
  <div class="split">
    <aside class="side" aria-label="Employees" data-t-aria>
      <input id="pp-search" type="search" autocomplete="off">
      <div id="pp-list"></div>
      <p id="pp-none" class="muted" hidden data-t>No company matches.</p>
    </aside>
    <section class="pane">
      <div id="pp-empty" class="card" hidden><p data-t>No employees for this month yet. Add time cards in step 1.</p>
        <button id="pp-to-upload" type="button" data-t>Go to step 1</button></div>
      <div id="company" hidden>
        <div class="doc-bar">
          <h2 id="co-title"></h2>
          <div class="doc-actions"><span id="co-status" class="muted" aria-live="polite"></span>
            <button id="co-million-open" type="button" hidden></button>
            <button id="co-csv" type="button" data-t>Download payroll CSV</button>
            <button id="co-settings-open" type="button" data-t>Company settings</button></div>
        </div>
        <div id="co-error" class="banner error" hidden></div>
        <section id="co-million" class="card" hidden></section>
        <section id="co-settings" class="card" hidden></section>
        <section class="card"><h3 data-t>Needs you</h3><div id="co-items"></div></section>
        <section id="co-pay" class="card">
          <h3 data-t>Pay preview</h3>
          <p class="legend" data-t>What Million Payroll should pay each employee before EPF, SOCSO and tax, worked out with Million's own overtime tables. The pay basis and Basic Rate come from Million's employee list (import its “Payroll Information” report); type a rate to use another. This is a check for you: Million still does the real calculation.</p>
          <div id="co-pay-table"></div>
          <div class="need-buttons"><button id="co-pay-download" type="button" data-t>Download the pay table (CSV)</button>
            <button id="co-add" type="button" data-t>Add employee</button></div>
        </section>
      </div>
      <div id="employee" hidden>
        <div class="doc-bar"><h2 id="em-title"></h2>
          <div class="doc-actions"><span id="em-save" class="muted" aria-live="polite"></span></div></div>
        <div id="em-error" class="banner error" hidden></div>
        <section id="em-needs" class="card" hidden></section>
        <section id="em-cards" class="card" hidden></section>
        <section class="card"><div id="em-window"></div></section>
        <div id="em-walk" class="need-buttons foot"></div>
        <datalist id="em-million-list"></datalist>
      </div>
      <div id="look" hidden>
        <div class="doc-bar">
          <button id="lk-back" class="link" data-t>&larr; Back to the employee</button>
          <h2 id="lk-title"></h2>
          <div class="doc-actions">
            <span id="lk-count" class="muted"></span>
            <button id="lk-prev" type="button" aria-label="Card before" data-t-aria>&lt;</button>
            <button id="lk-next" type="button" aria-label="Card after" data-t-aria>&gt;</button>
          </div>
        </div>
        <div id="lk-error" class="banner error" hidden></div>
        <div id="lk-body" hidden>
          <p id="lk-card" class="doc-status"></p>
          <div class="page-grid">
            <div id="lk-picture" class="page-image look-picture"></div>
            <div>
              <div id="lk-note" class="banner info" hidden></div>
              <ol id="lk-lines" class="look-lines"></ol>
              <div class="look-foot"><span id="lk-left" class="muted" aria-live="polite"></span>
                <button id="lk-accept" class="primary" type="button"></button></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</main>

<script src="i18n.js"></script>
<script src="app.js"></script>
<script src="paycommon.js"></script>
<script src="upload.js"></script>
<script src="steps.js"></script>
</body>
</html>
```

- [ ] **Step 3: Trim `static/app.js`.**
  - Delete from it (they move to `upload.js` in Step 5): the folder-button loop (`for (const [id, name] of [["open-inbox"…`),
    `let uploading`, `updateDropState`, `showMessages`, `upload`, `setupDrop`, `loadRecent`, `drawCompanyEditor`, the
    `setInterval(() => { if (!$("home").hidden) loadRecent(); }, 4000);` line and the `setupDrop();` call.
  - Delete `hideScreens`, `showHome`, `route` and their comment block, the `window.addEventListener("hashchange", route);`
    line and the final `route();` (they move to `steps.js`).
  - In `setupDocButtons`, delete the line `$("back").addEventListener(...)` (the button is gone). Leave the rest of the
    document view code where it is; Task 5 moves it.
  - `refreshClaude()` calls `updateDropState()` after an `await`, so it runs after `upload.js` has loaded; keep it.
  - Replace `companyBox` and `renderCompanyFilter` with these, and add the new helpers under the "client companies"
    block:

```js
function companyNames(jobs) {
  return [...new Set(jobs.map((j) => j.company).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

// The box that files a file under a company. ``done``: called when it closes (saved or not); ``say(text, kind)``:
// where the page shows what happened ("info" / "error").
function companyBox(j, companies, done, say) {
  const input = el("input", { type: "text", list: "company-names", maxlength: "80", value: j.company || suggestCompany(j.name),
    placeholder: t("Company name"), "aria-label": t("Company for {name}", { name: j.name }) });
  const close = () => { editingCompany = null; done(); };
  const save = async () => {
    try {
      const r = await api("PUT", `/api/jobs/${encodeURIComponent(j.id)}/company`, { company: input.value });
      if (r.moved) say(tn(r.moved, "{n} other file starting with “{c}” was put under this company too.", "{n} other files starting with “{c}” were put under this company too.", { c: input.value.trim() }), "info");
    } catch (e) { say(e.message, "error"); }
    close();
  };
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") save(); if (ev.key === "Escape") close(); });
  setTimeout(() => { input.focus(); input.select(); });
  return el("div", { class: "company-edit" },
    el("label", { text: t("Company") }), input,
    el("button", { class: "primary", text: t("Save"), onclick: save }), el("button", { text: t("Cancel"), onclick: close }),
    el("span", { class: "muted", text: t("Check the name. Other files that start with it will go under it too.") }),
    el("datalist", { id: "company-names" }, ...companies.map((c) => el("option", { value: c }))));
}

// The Company chooser of step 2's list (it filters step 3's list too). Remembered in this browser.
let companySignature = "";
function renderCompanyFilter(jobs, onChange) {
  const companies = companyNames(jobs);
  const count = (c) => jobs.filter((j) => (c === NO_COMPANY ? !j.company : j.company === c)).length;
  if (companyFilter && companyFilter !== NO_COMPANY && !companies.includes(companyFilter)) companyFilter = "";
  const none = count(NO_COMPANY);
  const options = [["", t("All companies ({n})", { n: jobs.length })], ...companies.map((c) => [c, `${c} (${count(c)})`]),
    ...(none ? [[NO_COMPANY, t("No company yet ({n})", { n: none })]] : [])];
  const signature = JSON.stringify([options, companyFilter]);
  $("company-box").hidden = jobs.length === 0;
  if (signature === companySignature) return companies;          // unchanged: do not close an open list
  companySignature = signature;
  const sel = el("select", { id: "company-filter", "aria-label": t("Show files of") },
    ...options.map(([value, text]) => el("option", { value, text, selected: value === companyFilter })));
  sel.addEventListener("change", () => {
    companyFilter = sel.value;
    companySignature = JSON.stringify([options, companyFilter]);
    try { localStorage.setItem("companyFilter", companyFilter); } catch (_) { /* private window */ }
    onChange();
  });
  $("company-box").replaceChildren(el("label", {}, t("Company"), sel));
  return companies;
}

// What this tab remembers (sessionStorage): where the user was in each step, the working month, the files added here.
// A private window may refuse it: then nothing is remembered and each step opens on its first screen.
function remember(key, value) { try { sessionStorage.setItem(key, value); } catch (_) { /* refused */ } }
function recall(key) { try { return sessionStorage.getItem(key); } catch (_) { return null; } }
function forget(key) { try { sessionStorage.removeItem(key); } catch (_) { /* refused */ } }

// The number beside a step button (0 hides it).
function stepBadge(step, n) {
  const badge = $(`step-${step}-n`);
  badge.hidden = !n; badge.textContent = n ? String(n) : "";
}

// "2 Check reading": the yellow cells left in the files step 2's list shows (every file until check.js is loaded).
function refreshCheckBadge(jobs) {
  const shown = typeof ckFilter === "function" ? jobs.filter(ckFilter) : jobs;
  stepBadge("check", shown.reduce((n, j) => n + (j.cells_to_check || 0), 0));
}
```

  Also update the comment above `companyMatches` to "Does a file's company pass the Company chooser?".

- [ ] **Step 4: Create `static/steps.js`**

```js
"use strict";
// The three steps: 1 Upload, 2 Check reading, 3 Payroll. The step buttons at the top, the addresses, where the user last
// was in each step (this tab only), the month steps 2 and 3 share, and drawing again on coming back to the tab.
// Loaded last: it draws the first screen.
//   #/                                                         1 Upload
//   #/check[/<file>[/columns/<page>[/h/<hours column>]]]       2 Check reading (a file; its column choice open)
//   #/payroll[/<month>[/e/<employee>[/look] | /c/<company>]]   3 Payroll (an employee; their Look panel; a company)
// Addresses of the screens before the three steps open the matching place.

const OLD_ADDRESSES = [
  [/^#\/doc\/(.+)$/, (m) => `#/check/${m[1]}`],
  [/^#\/payroll\/(\d{4}-\d{2})\/look\/([^/]+)$/, (m) => `#/payroll/${m[1]}/e/${m[2]}/look`],
  [/^#\/payroll\/(\d{4}-\d{2})\/layout\/([^/]+)\/(\d+)(\/h\/[^/]+)?$/, (m) => `#/check/${m[2]}/columns/${m[3]}${m[4] || ""}`],
  [/^#\/payroll\/(\d{4}-\d{2})\/old(?:\/e\/([^/]+))?$/, (m) => (m[2] ? `#/payroll/${m[1]}/e/${m[2]}` : `#/payroll/${m[1]}`)],
];

function workMonth() {
  const m = recall("workMonth");
  return /^\d{4}-\d{2}$/.test(m || "") ? m : defaultPayrollMonth();
}
function setWorkMonth(month) { remember("workMonth", month); }

function showStep(step) {
  for (const s of ["upload", "check", "payroll"]) {
    const button = $(`step-${s}`);
    button.classList.toggle("on", s === step);
    if (s === step) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  }
  for (const [id, s] of [["upload", "upload"], ["check", "check"], ["people", "payroll"]]) $(id).hidden = s !== step;
}

function route() {
  const hash = location.hash;
  for (const [re, to] of OLD_ADDRESSES) {
    const m = hash.match(re);
    if (m) { location.replace(to(m)); return; }               // the hashchange that follows draws it
  }
  if (typeof emLeave === "function") emLeave();               // what was typed in an employee and not sent yet: now
  const ck = hash.match(/^#\/check(?:\/([^/]+)(?:\/columns\/(\d+)(?:\/h\/([^/]+))?)?)?$/);
  const pp = hash.match(/^#\/payroll(?:\/(\d{4}-\d{2})(?:\/e\/([^/]+)(\/look)?|\/c\/(.*))?)?$/);
  if (ck && typeof showCheck === "function") {
    showStep("check");
    if (ck[1]) remember("place.check", hash);
    showCheck(ck[1] ? decodeURIComponent(ck[1]) : null,
      ck[2] ? { page: Number(ck[2]), hours: ck[3] ? decodeURIComponent(ck[3]) : null } : null);
  } else if (pp && typeof showPeople === "function") {
    showStep("payroll");
    if (pp[1]) setWorkMonth(pp[1]);
    if (pp[2] || pp[4] !== undefined) remember("place.payroll", hash);
    showPeople(pp[1] || workMonth(), { employee: pp[2] ? decodeURIComponent(pp[2]) : null, look: Boolean(pp[3]),
      company: pp[4] !== undefined ? decodeURIComponent(pp[4]) : null });
  } else {
    showStep("upload");
    showUpload();
  }
}

// A step button opens the step where the user last was in this tab (step 3: in the working month).
for (const [step, first] of [["upload", "#/"], ["check", "#/check"], ["payroll", "#/payroll"]]) {
  $(`step-${step}`).addEventListener("click", (e) => {
    e.preventDefault();
    let to = step === "upload" ? first : recall(`place.${step}`) || first;
    if (step === "payroll" && !to.startsWith(`#/payroll/${workMonth()}/`)) to = `#/payroll/${workMonth()}`;
    if (location.hash === to) route(); else location.hash = to;
  });
}

// Back in this tab after fixing something in another one: show what is true now (never over a box being typed in).
let lastReturn = 0;
async function refreshOnReturn() {
  if (document.hidden || Date.now() - lastReturn < 1000) return;      // the two events below often come together
  const typing = document.activeElement && ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
  if (typing) return;
  lastReturn = Date.now();
  if (!$("people").hidden && typeof ppLoad === "function") {
    await ppLoad();
    if (!$("look").hidden && typeof refreshLook === "function") refreshLook();
    else if (!$("employee").hidden && typeof emLoad === "function" && emView && !Object.keys(emPending).length) emLoad();
  } else if (!$("check").hidden && $("layout").hidden && typeof ckLoad === "function") {
    await ckLoad();
    if (currentId) ckDrawFile();
  } else if (!$("upload").hidden) showUpload();
}
document.addEventListener("visibilitychange", refreshOnReturn);
window.addEventListener("focus", refreshOnReturn);

window.addEventListener("hashchange", route);
route();
```

- [ ] **Step 5: Create `static/upload.js`**

```js
"use strict";
// Step 1, Upload: the drop box, the Inbox and Tables folders, and "Just added": the files added in this tab and every
// file still waiting or being read, each with its company and progress, then "Check them →" (step 2).
// Loaded after app.js and uses its helpers.

let uploading = false;
let upFirst = null;            // the first file added in this tab that is still there (where "Check them →" goes)

// The Inbox folder (files saved there are read by themselves) and the Tables folder (every finished table as a CSV)
for (const [id, name] of [["open-inbox", "inbox"], ["open-tables", "tables"]]) {
  $(id).addEventListener("click", async () => {
    try { await api("POST", `/api/folders/${name}/open`); }
    catch (e) { showMessages([e.message], "error"); }
  });
}

function updateDropState() {
  const drop = $("drop");
  drop.classList.toggle("disabled", !claudeReady || uploading);
  drop.setAttribute("aria-disabled", String(!claudeReady || uploading));
}

function showMessages(items, kind) {
  $("upload-messages").replaceChildren(...items.map((m) => el("div", { class: `banner ${kind}`, text: m })));
}

function addedHere() {
  try { const ids = JSON.parse(recall("added") || "[]"); return Array.isArray(ids) ? ids : []; } catch (_) { return []; }
}

async function upload(fileList) {
  const files = [...fileList];
  if (!files.length || uploading) return;
  if (!claudeReady) { showMessages([t("Connect your Claude account first (top right), then add your files.")], "error"); return; }
  uploading = true; updateDropState();
  showMessages([tn(files.length, "Adding {n} file…", "Adding {n} files…")], "info");
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));
  try {
    const r = await api("POST", "/api/jobs", form);
    showMessages(r.rejected.map((x) => tm(x.message)), "error");
    remember("added", JSON.stringify([...r.created.map((c) => c.id), ...addedHere()].slice(0, 200)));
  } catch (e) { showMessages([e.message], "error"); }
  uploading = false; updateDropState();
  loadJustAdded();
}

function setupDrop() {
  const drop = $("drop"), input = $("file-input");
  drop.addEventListener("click", () => {
    if (!claudeReady) showMessages([t("Connect your Claude account first (top right), then add your files.")], "error");
    else if (!uploading) input.click();
  });
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); drop.click(); } });
  input.addEventListener("change", () => { upload(input.files); input.value = ""; });
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); });
  // a file dropped beside the box must not make the browser leave the page
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());
}

function fileRow(j, companies) {
  const cancelled = j.status === "failed" && j.error && j.error.code === "CANCELLED";
  const active = j.status === "queued" || j.status === "reading";
  const cls = j.status === "done" ? "pill good" : j.status === "failed" && !cancelled ? "pill bad" : "pill";
  const li = el("li", {},
    el("span", { class: "name", text: j.name }),
    el("button", { class: j.company ? "company" : "company unset", text: j.company || t("Set company"),
      title: j.company ? t("Click to change the company") : t("Choose the client company of this file"),
      onclick: () => {
        editingCompany = j.id;
        document.querySelectorAll("#recent .company-edit").forEach((n) => n.remove());
        li.append(companyBox(j, companies, loadJustAdded, (text, kind) => showMessages([text], kind)));
      } }),
    el("span", { class: "when", text: new Date(j.created).toLocaleString(LOCALE) }),
    el("span", { class: cls, text: cancelled ? t("Cancelled") : progressText(j) }),
    active && el("button", { text: t("Cancel"), onclick: async () => {
      try { await api("POST", `/api/jobs/${encodeURIComponent(j.id)}/cancel`); } catch (e) { showMessages([e.message], "error"); }
      loadJustAdded();
    } }),
    j.status === "done" && el("button", { text: t("Open"), onclick: () => { location.hash = `#/check/${encodeURIComponent(j.id)}`; } }));
  if (j.status === "failed" && j.error && !cancelled) li.append(el("div", { class: "muted", style: "flex-basis:100%", text: tm(j.error.message) }));
  return li;
}

async function loadJustAdded() {
  if (editingCompany) return;
  let jobs;
  try { jobs = await api("GET", "/api/jobs"); } catch (e) { showMessages([e.message], "error"); return; }
  refreshCheckBadge(jobs);
  const mine = new Set(addedHere());
  const busy = (j) => j.status === "queued" || j.status === "reading";
  const shown = jobs.filter((j) => mine.has(j.id) || busy(j));
  const companies = companyNames(jobs);
  $("recent").replaceChildren(...shown.map((j) => fileRow(j, companies)));
  $("recent-empty").hidden = shown.length > 0;
  $("up-state").textContent = jobs.some(busy) ? t("Reading…") : shown.length ? t("Everything is read.") : "";
  const first = shown.find((j) => mine.has(j.id));
  upFirst = first ? first.id : null;
}

$("up-check").addEventListener("click", () => { location.hash = upFirst ? `#/check/${encodeURIComponent(upFirst)}` : "#/check"; });

function showUpload() { loadJustAdded(); }

setInterval(() => { if (!$("upload").hidden) loadJustAdded(); }, 4000);
setupDrop();
```

- [ ] **Step 6: Styles.** In `static/app.css`: change the selectors `.recent .company` and `.recent .company.unset` to
  `button.company` and `button.company.unset`; delete `.navlink` and `.navlink:hover`; append:

```css
/* the three steps */
.steps { display: flex; gap: 6px; flex-wrap: wrap; }
.step { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border: 1px solid var(--line);
  border-radius: 999px; color: var(--text); text-decoration: none; font-weight: 600; }
.step:hover { border-color: var(--accent); }
.step.on { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
.badge { min-width: 20px; padding: 0 6px; border-radius: 999px; background: var(--warn-bg); border: 1px solid var(--warn-line);
  color: var(--text); font-size: .78rem; text-align: center; }
.split { display: grid; grid-template-columns: minmax(220px, 300px) minmax(0, 1fr); gap: 16px; align-items: start; }
.side { position: sticky; top: 8px; max-height: calc(100vh - 16px); overflow: auto; background: var(--card);
  border: 1px solid var(--line); border-radius: 10px; padding: 8px; }
@media (max-width: 900px) {
  .split { grid-template-columns: 1fr; }
  .side { position: static; max-height: 45vh; }
}
.side-filters { display: grid; gap: 6px; margin-bottom: 8px; }
.side-filters select, .side input[type=search] { font: inherit; padding: 4px 6px; width: 100%; }
.side-list { list-style: none; margin: 0; padding: 0; }
.side-item, .side-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; width: 100%;
  text-align: left; border: 0; border-radius: 6px; padding: 6px 8px; background: transparent; }
.side-item .name { display: flex; flex-direction: column; min-width: 0; overflow-wrap: anywhere; }
.side-item small, .side-head small { color: var(--muted); font-size: .8rem; font-weight: 400; }
.side-item.on, .side-head.on { background: var(--bg); box-shadow: inset 3px 0 0 var(--accent); }
.side-head { flex-direction: column; align-items: flex-start; gap: 0; margin-top: 6px; }
.pp-company + .pp-company { border-top: 1px solid var(--line); }
.foot { justify-content: flex-end; margin: 16px 0; }
```

- [ ] **Step 7: Malay.** Add to `MS` in `static/i18n.js` (next to the page texts at the top):

```js
  "Steps": "Langkah",
  "1 Upload": "1 Muat naik",
  "2 Check reading": "2 Semak bacaan",
  "3 Payroll": "3 Gaji",
  "Just added": "Baru ditambah",
  "Nothing is being read. Files you add here are listed until you close this tab.": "Tiada fail sedang dibaca. Fail yang anda tambah di sini disenaraikan sehingga anda menutup tab ini.",
  "Check them →": "Semak fail ini →",
  "Reading…": "Sedang membaca…",
  "Everything is read.": "Semua sudah dibaca.",
  "Files": "Fail",
  "Go to step 1": "Pergi ke langkah 1",
  "No company matches.": "Tiada syarikat yang sepadan.",
  "No employees for this month yet. Add time cards in step 1.": "Belum ada pekerja untuk bulan ini. Tambah kad masa dalam langkah 1.",
  "← Back to the employee": "← Kembali kepada pekerja",
```

  In `tools/check_i18n.py`, replace both fixed lists of script names with every script of the folder:

```python
SCRIPTS = sorted(p.name for p in S.glob("*.js"))
```

  (define it right after `S = ...`; use `SCRIPTS` where the two tuples were, keeping `i18n.js` in the first loop and
  leaving it out of the second: `for name in [n for n in SCRIPTS if n != "i18n.js"]:`).

- [ ] **Step 8: Run the tests and the checks**

Run: `"$PY" -m pytest -q` — Expected: all pass.
Run: `"$PY" tools/check_i18n.py` and `"$PY" tools/check_patterns.py` — Expected: `missing Malay: 0`, `0 not translated`.
(Install the dev-only parser if missing: `"$PY" -m pip install esprima`.)

- [ ] **Step 9: The click-through harness.** Install the dev-only browser driver: `"$PY" -m pip install websockets`.
  Copy the session-23 harness into the repo (made-up data only), from
  `C:\Users\TENGAC~1\AppData\Local\Temp\claude\C--Users-TENGA-CEKAP-Documents-table-reader--claude-worktrees-progress-review-docs-336fd9\970e6455-3804-4a37-b46a-d0e4e3a4e38f\scratchpad\`
  (`drive.py`, `serve.py`, `run.sh`) to `tools/clickthrough/`, then:
  - in `drive.py` delete `sys.path.insert(0, str(Path(__file__).parent / "pylib"))` (websockets is installed now) and
    make `profile` and `downloads` live under `tempfile.gettempdir()` instead of next to the script;
  - in `run.sh` set `R` to the repository root (`R="$(cd "$S/../.." && pwd)"`), keep the server's data in
    `$(mktemp -d)` instead of `home6`, and keep the venv path line;
  - in `serve.py` add, before `fresh = ...`, a slow reader for files whose name starts with `SLOW`:

```python
import time  # noqa: E402

def reader(image):
    if mode.get("slow"):
        time.sleep(4)
    return mode["card"](image)
```

    and after the made-up files are seeded (still inside `if fresh:`) add a company with signs and a slow file:

```python
        mode["card"] = month_card
        c.post("/api/jobs", files=[("files", (f"A & B (M) SITI SEPT {YEAR}.png", png(), "application/octet-stream"))])
        store.wait_idle()
        for j in c.get("/api/jobs").json():
            if j["name"].startswith("A & B"):
                c.put(f"/api/jobs/{j['id']}/company", json={"company": "A & B (M)"})
```

    and right before `uvicorn.run(...)`, when the environment variable `SLOW_FILE` is set, queue one slow file in a
    thread after the server starts (`threading.Timer(2, lambda: store.create_job("SLOW MAJU JAYA ALI SEPT.png", png()))`
    with `mode["slow"] = True` set first).
  - If the scratchpad files are gone, write the harness anew with the same shape: `serve.py` seeds made-up data with
    `tests.test_app`'s `month_card` / `report_2_card` / `report_2_map` and starts uvicorn on a port; `drive.py` starts
    headless Edge (`--headless=new --remote-debugging-port=9344`), talks CDP over `websockets`, injects the `T` helpers
    (`T.until`, `T.click(text, root)`, `T.set(id, value)`, `T.text(selector)`), collects JS exceptions and console
    errors as problems, and runs `scenario(page, downloads)` from the module named on the command line.
  - `tools/clickthrough/README.md`: three lines — what it is (made-up data only), how to run
    (`sh tools/clickthrough/run.sh <scenario module>`), and that `websockets` is a dev-only install like `esprima`.

  Create `tools/clickthrough/upload_page.py`:

```python
"""Step 1 and the step buttons: the page opens on Upload; the steps' buttons are there; old addresses redirect."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/")
    expect("Upload shown", await page.ev("!document.getElementById('upload').hidden"), True)
    expect("step 1 is on", await page.ev("document.getElementById('step-upload').classList.contains('on')"), True)
    expect("just added starts empty", await page.ev("document.getElementById('recent').children.length"), 0)
    await page.goto(f"{BASE}/#/doc/nothing")
    expect("old file address becomes step 2's", await page.ev("location.hash"), "#/check/nothing")
    await page.goto(f"{BASE}/#/payroll/2026-09/look/e1")
    expect("old Look address", await page.ev("location.hash"), "#/payroll/2026-09/e/e1/look")
    await page.goto(f"{BASE}/#/payroll/2026-09/layout/d1/2/h/Total")
    expect("old layout address", await page.ev("location.hash"), "#/check/d1/columns/2/h/Total")
    await page.ev("Storage.prototype.setItem = () => { throw new Error('refused'); }; "
                  "Storage.prototype.getItem = () => { throw new Error('refused'); }; true")
    await page.ev("document.getElementById('step-upload').click(); T.sleep(300)")
    expect("works when storage is refused", await page.ev("!document.getElementById('upload').hidden"), True)
```

  Run: `sh tools/clickthrough/run.sh upload_page` — Expected: `No problems.`

- [ ] **Step 10: Commit** (scan the diff first)

```bash
git add static/index.html static/app.js static/steps.js static/upload.js static/app.css static/i18n.js tools/check_i18n.py tools/clickthrough tests/test_app.py
git commit -m "Page: three steps at the top, the addresses of the new pages, and step 1 (Upload with Just added)"
```

---

### Task 5: Step 2 — Check reading

**Files:**
- Create: `static/check.js`, `static/columns.js` (from `static/layout.js`, then delete `layout.js`)
- Modify: `static/app.js` (the document view moves out), `static/paycommon.js`, `static/index.html` (scripts),
  `static/i18n.js`, `tests/test_app.py` (`SCRIPTS`)
- Create: `tools/clickthrough/check_page.py`

**Interfaces:**
- Consumes: Task 2's `/files` and `cells_to_check`; Task 4's `remember/recall/forget`, `workMonth`, `stepBadge`,
  `refreshCheckBadge`, `companyBox`, `renderCompanyFilter`, `companyMatches`, `companyNames`, `progressText`.
- Produces: `showCheck(id, columns)`, `ckLoad() -> Promise`, `ckDrawFile()`, `ckFilter(job) -> bool`, globals
  `currentId`, `currentDoc`, `docTimer`; in `paycommon.js` `monthTitle(month)`, `shiftMonth(month, by)`;
  `showLayout(doc, page, hours)` in `columns.js`.

- [ ] **Step 1: Write the failing click-through** `tools/clickthrough/check_page.py`:

```python
"""Step 2: the file list, a file with a problem, the column choice in place, the buttons on, empty and stale cases."""
import asyncio

from drive import BASE, expect

M = "2026-09"


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => /^#\\/check\\/./.test(location.hash), 'a file is chosen')")
    expect("step 2 on", await page.ev("document.getElementById('step-check').classList.contains('on')"), True)
    print("  files:", await page.ev("T.text('#ck-files .side-item strong')"))
    # the August card is on nobody in August: listed so a wrong month can be put right, marked as not in this month
    amin = await page.ev("[...document.querySelectorAll('#ck-files .side-item')].find((b) => b.textContent.includes('AMIN')).textContent")
    expect("August card marked", "Not in this month" in amin, True)
    # ZUL's card has a confirmed layout map: no problem; the slow file is not there yet
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    ids = {j["name"]: j["id"] for j in jobs}
    zul = next(v for k, v in ids.items() if "ZUL" in k)
    await page.goto(f"{BASE}/#/check/{zul}")
    await page.ev("T.until(() => document.getElementById('doc-name').textContent.includes('ZUL'), 'ZUL open')")
    expect("Download enabled", await page.ev("document.getElementById('download').disabled"), False)
    foot = await page.ev("T.text('#ck-foot button')")
    expect("foot buttons", "See ZUL in payroll →" in foot and "Go to payroll for September 2026 →" in foot, True)
    await page.ev("T.click('See ZUL in payroll →')")
    expect("goes to step 3's ZUL", await page.ev("location.hash.startsWith('#/payroll/2026-09/e/')"), True)
    # All months shows the August card; its problem is not asked about there
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.until(() => document.getElementById('ck-month').options.length > 1, 'months'); "
                  "T.set('ck-month', 'all'); T.sleep(500)")
    expect("All months lists the August card", "AMIN AUG" in await page.ev("T.text('#ck-files .side-item strong')"), True)
    await page.ev("T.set('ck-month', '2026-09'); T.sleep(500)")
    # a month with no files
    await page.ev("T.set('ck-month', '2026-03'); T.sleep(800)")
    expect("empty month", await page.ev("document.getElementById('ck-empty-text').textContent"),
           "No files for March 2026. Choose “All months” to see every file.")
    # a remembered file that is gone
    await page.ev("sessionStorage.setItem('place.check', '#/check/gone-file'); T.set('ck-month', '2026-09'); T.sleep(300)")
    await page.goto(f"{BASE}/#/check/gone-file")
    await page.ev("T.until(() => location.hash !== '#/check/gone-file', 'redirect')")
    expect("a gone file opens step 2's first file", await page.ev("/^#\\/check(\\/|$)/.test(location.hash)"), True)
```

Add a second scenario module `tools/clickthrough/check_reading.py` for Review Focus 4 (run with `SLOW_FILE=1`):

```python
"""Step 2 while a file is being read: progress in the list and on the file, then it updates by itself."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/check")
    await page.ev("T.set('ck-month', 'all'); T.until(() => T.text('#ck-files').includes('SLOW'), 'slow file listed', 8000)")
    jobs = await page.ev("fetch('/api/jobs').then((r) => r.json())")
    slow = next(j["id"] for j in jobs if j["name"].startswith("SLOW"))
    await page.goto(f"{BASE}/#/check/{slow}")
    await page.ev("T.until(() => document.getElementById('doc-name').textContent.startsWith('SLOW'), 'open')")
    expect("Download off while reading", await page.ev("document.getElementById('download').disabled"), True)
    expect("no needs box while reading", await page.ev("document.getElementById('ck-needs').hidden"), True)
    await page.ev("T.until(() => document.getElementById('download').disabled === false, 'finished', 15000)")
    expect("list shows it finished", "Reading" in await page.ev("T.text('#ck-files .side-item.on')"), False)
```

Run: `sh tools/clickthrough/run.sh check_page` — Expected: problems (step 2 still opens Upload).

- [ ] **Step 2: Move the month helpers.** Cut `monthTitle` and `shiftMonth` from `static/companies.js` and paste them
  into `static/paycommon.js` right after `defaultPayrollMonth`. (`companies.js` is not loaded any more; Task 6 deletes it.)

- [ ] **Step 3: Create `static/columns.js`** from `static/layout.js` (`git mv static/layout.js static/columns.js`), then:
  - first comment line: "The column choice of a card layout, opened under the file in step 2 (#/check/<file>/columns/<page>)."
    and its last sentence: "Loaded after check.js and uses its helpers.";
  - replace `let lyMonth = null; ...` with `let lyDoc = null;        // the file the choice is opened from`;
  - replace `showLayout` and `backFromLayout`:

```js
async function showLayout(doc, page, hours) {
  lyDoc = doc;
  lyHours = hours || null;
  $("layout").hidden = false;
  for (const id of ["ly-save", "ly-as-is", "ly-ask"]) $(id).disabled = false;   // a save made before left them off
  $("ly-title").textContent = ""; $("ly-body").hidden = true; $("ly-note").hidden = true;
  lyError("");
  $("layout").scrollIntoView({ block: "start" });
  await loadLayout(doc, page, false);
}

function backFromLayout() { location.hash = `#/check/${encodeURIComponent(lyDoc)}`; }
```

  - in `saveLayout`, replace `backFromLayout();` with `await ckLoad(); backFromLayout();` (the file's problems change);
  - delete the last line (`if (location.hash.startsWith("#/payroll")) route();` and its comment).

- [ ] **Step 4: Create `static/check.js`.** Move these from `static/app.js` unchanged: `const QUALITY`,
  `let currentId`, `let currentDoc`, `findCell`, `paintCell`, `makeCell`, `buildPage`, `showDoc`, `let docTimer`, the
  "document view" comment. Move and change `saveCell`, `paintStatus`, `openDoc`, `pollDoc` and `setupDocButtons` as
  shown below. Then add the rest:

```js
"use strict";
// Step 2, Check reading: the list of files (left) and the chosen file (right): its company, what it needs from the user
// in the working month ("This file needs you": whose card, which month, an unknown card layout, no company, set aside),
// Claude's reading beside the picture with its yellow cells, and the buttons on to the next file and to step 3.
// Claude's reading is never changed here: Enter or typing in a cell saves a correction (edits.json).
// Loaded after app.js and paycommon.js; columns.js (the column choice opened under a file) and steps.js come after.

// ... the moved QUALITY, currentId, currentDoc, findCell, paintCell, makeCell, buildPage, showDoc, docTimer ...

let ckJobs = null;           // GET /api/jobs, newest first
let ckFiles = null;          // GET /api/payroll/<working month>/files (null with "All months")
let ckAll = recall("checkAll") === "1";

function ckError(message, kind = "error") {
  $("ck-error").hidden = !message; $("ck-error").textContent = message || "";
  $("ck-error").className = `banner ${kind}`;
}
function ckBusy(j) { return j.status === "queued" || j.status === "reading"; }
function ckItems(id) { return (!ckAll && ckFiles && ckFiles.files[id]) || []; }

// Does step 2's list show this file? Every file of the chosen company with "All months"; otherwise a file still being
// read or stopped, a file of the month, a file with something to settle in it, and a file on one of its employees.
function ckFilter(j) {
  if (!companyMatches(j.company)) return false;
  if (ckAll || j.status !== "done" || !ckFiles) return true;
  return ckFiles.months[j.id] === ckFiles.month || j.id in ckFiles.files || j.id in ckFiles.employees;
}

function ckNeeds(j) {
  return j.status === "done" && (j.cells_to_check > 0 || ckItems(j.id).some((i) => i.kind !== "other"));
}

function ckState(j) {
  const cancelled = j.status === "failed" && j.error && j.error.code === "CANCELLED";
  if (j.status !== "done") return { text: cancelled ? t("Cancelled") : progressText(j), cls: j.status === "failed" && !cancelled ? "pill bad" : "pill" };
  const items = ckItems(j.id);
  const parts = [];
  if (j.cells_to_check) parts.push(tn(j.cells_to_check, "{n} yellow", "{n} yellow"));
  if (items.some((i) => i.kind !== "other")) parts.push(t("! Needs you"));
  else if (items.length) parts.push(t("Not in this month"));
  return parts.length ? { text: parts.join(" · "), cls: "pill check" } : { text: "✓", cls: "pill good" };
}

// The list (and, for one month, its files' problems) from the server.
async function ckLoad() {
  try {
    const month = workMonth();
    const [jobs, files] = await Promise.all([api("GET", "/api/jobs"),
      ckAll ? Promise.resolve(null) : api("GET", `/api/payroll/${month}/files`)]);
    ckJobs = jobs; ckFiles = files;
    if (files) stepBadge("payroll", files.needs);
    ckError("");
  } catch (e) { ckError(e.message); ckJobs = ckJobs || []; }
  ckDrawList();
}

function ckDrawMonth() {
  const base = defaultPayrollMonth();
  const months = [shiftMonth(base, 1), ...Array.from({ length: 12 }, (_, k) => shiftMonth(base, -k))];
  if (!months.includes(workMonth())) months.unshift(workMonth());
  $("ck-month").replaceChildren(el("option", { value: "all", text: t("All months"), selected: ckAll }),
    ...months.map((m) => el("option", { value: m, text: monthTitle(m), selected: !ckAll && m === workMonth() })));
}

function ckDrawList() {
  ckDrawMonth();
  renderCompanyFilter(ckJobs, () => { ckDrawList(); if (currentId) ckDrawFile(); });
  const shown = ckJobs.filter(ckFilter);
  $("ck-files").replaceChildren(...shown.map((j) => {
    const s = ckState(j);
    return el("li", {}, el("button", { type: "button", class: "side-item" + (j.id === currentId ? " on" : ""),
      onclick: () => { location.hash = `#/check/${encodeURIComponent(j.id)}`; } },
    el("span", { class: "name" }, el("strong", { text: j.name }), el("small", { text: j.company || t("No company yet") })),
    el("span", { class: s.cls, text: s.text })));
  }));
  refreshCheckBadge(ckJobs);
}

async function showCheck(id, columns) {
  const stale = !ckJobs || (!ckAll && (!ckFiles || ckFiles.month !== workMonth())) || (id && !ckJobs.some((j) => j.id === id));
  if (stale) await ckLoad(); else ckDrawList();
  $("ck-empty").hidden = true;
  if (!id) {                                       // no file in the address: the first that needs the user, else the first
    const shown = ckJobs.filter(ckFilter);
    const first = shown.find(ckNeeds) || shown[0];
    if (first) location.replace(`#/check/${encodeURIComponent(first.id)}`); else ckShowEmpty();
    return;
  }
  if (!ckJobs.some((j) => j.id === id)) { forget("place.check"); location.replace("#/check"); return; }
  if (id !== currentId || !currentDoc) await openDoc(id); else ckDrawFile();
  if (columns) showLayout(id, columns.page, columns.hours); else $("layout").hidden = true;
}

function ckShowEmpty() {
  currentId = null; currentDoc = null; clearTimeout(docTimer);
  $("doc").hidden = true; $("ck-empty").hidden = false;
  $("ck-empty-text").textContent = !ckJobs.length ? t("Nothing here yet. Add files in step 1.")
    : !ckJobs.some((j) => companyMatches(j.company)) ? t("No files for this company. Choose “All companies” to see every file.")
      : t("No files for {month}. Choose “All months” to see every file.", { month: monthTitle(workMonth()) });
}

// The file's company, what it needs in the month, and the buttons on.
function ckDrawFile() {
  const j = ckJobs && ckJobs.find((x) => x.id === currentId);
  if (!j || !currentDoc) return;
  if (editingCompany !== j.id) {
    $("ck-company").replaceChildren(el("button", { type: "button", class: j.company ? "company" : "company unset",
      text: j.company || t("Set company"), title: j.company ? t("Click to change the company") : t("Choose the client company of this file"),
      onclick: () => {
        editingCompany = j.id;
        $("ck-company").append(companyBox(j, companyNames(ckJobs), async () => { await ckLoad(); ckDrawFile(); }, ckError));
      } }));
  }
  const items = ckItems(j.id);
  $("ck-needs").hidden = !items.length || j.status !== "done";
  $("ck-needs").replaceChildren(
    el("h3", { text: items.some((i) => i.kind !== "other") ? t("This file needs you") : t("Not in this month's payroll") }),
    el("ol", { class: "needs" }, ...items.map(fileItemNode)));
  ckDrawFoot(j);
}

function ckDrawFoot(j) {
  const shown = ckJobs.filter(ckFilter);
  const at = shown.findIndex((x) => x.id === j.id);
  const next = [...shown.slice(at + 1), ...shown.slice(0, Math.max(at, 0))].find(ckNeeds);
  const month = workMonth();
  const people = (!ckAll && ckFiles && ckFiles.employees[j.id]) || [];
  $("ck-foot").replaceChildren(
    el("button", { type: "button", text: next ? t("Next file with yellow cells →") : t("No other file needs checking"),
      disabled: !next, onclick: () => { location.hash = `#/check/${encodeURIComponent(next.id)}`; } }),
    ...people.map((p) => el("button", { type: "button", text: t("See {name} in payroll →", { name: p.name || t("An employee") }),
      onclick: () => { location.hash = `#/payroll/${month}/e/${encodeURIComponent(p.id)}`; } })),
    el("button", { type: "button", class: "primary", text: t("Go to payroll for {month} →", { month: monthTitle(month) }),
      onclick: () => { location.hash = `#/payroll/${month}`; } }));
}

// Do something about the file, then draw the list and the file again from the server.
async function ckAct(button, action) {
  button.disabled = true;
  try { await action(); ckError(""); await ckLoad(); ckDrawFile(); }
  catch (e) { ckError(e.message); button.disabled = false; }
}

// One thing the file needs (wording and buttons as on the company screen before the three steps).
function fileItemNode(item) {
  const buttons = [];
  let head = "", details = [];
  const month = ckFiles.month;
  if (item.kind === "unplaced") {
    head = t("{file}: whose card is this?", { file: item.name });
    if (!item.readable) details = [t("Table Reader cannot work out the days from this file yet; the figures will have to be typed.")];
    const place = (button, employee) => ckAct(button, () => api("POST", `/api/payroll/${month}/place`, { ref: item.ref, employee }));
    for (const e of ckFiles.choices[item.company] || []) {
      const b = el("button", { type: "button", text: e.name || e.emp_no || t("An employee") });
      b.addEventListener("click", () => place(b, e.id));
      buttons.push(b);
    }
    const fresh = el("button", { type: "button", text: t("New employee") });
    fresh.addEventListener("click", () => place(fresh, null));
    buttons.push(fresh);
    if (item.ref === item.doc) {                 // a whole file that is nobody's card (a notice, a second scan)
      const none = el("button", { type: "button", text: t("Not a time card") });
      none.addEventListener("click", () => ckAct(none, () => api("POST", "/api/payroll/file-month", { id: item.doc, month: "none" })));
      buttons.push(none);
    }
  } else if (item.kind === "layout") {
    head = item.confirmed ? t("{file}: the days cannot be worked out with the saved card layout", { file: item.name })
      : t("{file}: a card layout Table Reader does not know", { file: item.name });
    details = [item.confirmed ? t("Say which column holds the date and which the hours or times.")
      : t("Columns with figures that are not used: {list}. Say once what they mean; it is kept for every card with the same headings.",
        { list: item.columns.join(", ") })];
    const hours = item.hours_column ? `/h/${encodeURIComponent(item.hours_column)}` : "";
    buttons.push(el("button", { type: "button", class: "primary", text: t("Check the columns"),
      onclick: () => { location.hash = `#/check/${encodeURIComponent(item.doc)}/columns/${item.page}${hours}`; } }));
    if (!item.confirmed) {
      const asIs = el("button", { type: "button", text: t("It is right as it is") });
      asIs.addEventListener("click", () => ckAct(asIs, () => api("PUT", "/api/layouts",
        { doc: item.doc, page: item.page, as_is: true, hours_column: item.hours_column })));
      buttons.push(asIs);
    }
  } else if (item.kind === "month") {
    head = t("{file}: which month is this for?", { file: item.name });
    details = [tm(item.why)];
    const here = el("button", { type: "button", text: t("It is for {month}", { month: monthTitle(month) }) });
    here.addEventListener("click", () => ckAct(here, () => api("POST", "/api/payroll/file-month", { id: item.doc, month })));
    const none = el("button", { type: "button", text: t("Not a time card") });
    none.addEventListener("click", () => ckAct(none, () => api("POST", "/api/payroll/file-month", { id: item.doc, month: "none" })));
    buttons.push(here, none);
  } else if (item.kind === "other") {
    head = item.name;
    details = [item.month === "none" ? t("Set aside as not a time card.") : t("Read as a file of {month}.", { month: monthTitle(item.month) })];
    const here = el("button", { type: "button", text: t("It is for {month}", { month: monthTitle(month) }) });
    here.addEventListener("click", () => ckAct(here, () => api("POST", "/api/payroll/file-month", { id: item.doc, month })));
    buttons.push(here);
  } else if (item.kind === "company") {
    head = t("{file}: which company is this for?", { file: item.name });
    const input = el("input", { type: "text", maxlength: "80", placeholder: t("Company name"), value: suggestCompany(item.name),
      "aria-label": t("Company for {name}", { name: item.name }) });
    const save = el("button", { type: "button", class: "primary", text: t("Save") });
    save.addEventListener("click", () => ckAct(save, async () => {
      if (!input.value.trim()) throw new Error(t("Type the company's name first."));
      await api("PUT", `/api/jobs/${encodeURIComponent(item.doc)}/company`, { company: input.value });
    }));
    buttons.push(input, save);
  }
  return el("li", { class: "need" }, el("strong", { text: head }),
    ...details.map((d) => el("p", { class: "legend", text: d })), el("div", { class: "need-buttons" }, ...buttons));
}

$("ck-month").addEventListener("change", () => {
  ckAll = $("ck-month").value === "all";
  remember("checkAll", ckAll ? "1" : "");
  if (!ckAll) setWorkMonth($("ck-month").value);
  ckFiles = null;
  showCheck(currentId, null);
});
$("ck-to-upload").addEventListener("click", () => { location.hash = "#/"; });

// While a file is being read the list follows it; when one finishes, its problems in the month are fetched too.
setInterval(async () => {
  if ($("check").hidden || editingCompany || !ckJobs || !ckJobs.some(ckBusy)) return;
  const done = ckJobs.filter((j) => j.status === "done").length;
  let jobs;
  try { jobs = await api("GET", "/api/jobs"); } catch (_) { return; }
  if (jobs.filter((j) => j.status === "done").length !== done) { await ckLoad(); if (currentId) ckDrawFile(); }
  else { ckJobs = jobs; ckDrawList(); }
}, 4000);
```

  The changed moved functions:

```js
async function saveCell(loc, value, node) {
  const change = { page: loc.page, value };
  if (loc.header !== undefined) change.header = loc.header; else { change.row = loc.row; change.column = loc.column; }
  try {
    const doc = await api("PUT", `/api/jobs/${encodeURIComponent(currentId)}/cells`, { changes: [change] });
    currentDoc = doc;
    const cell = findCell(doc, loc);
    if (cell) paintCell(node, loc, cell);
    paintStatus(doc);
    const j = ckJobs && ckJobs.find((x) => x.id === doc.id);       // the list's count follows
    if (j) { j.cells_to_check = doc.cells_to_check; ckDrawList(); ckDrawFoot(j); }
  } catch (e) { alert(e.message); }
}
```

  In `paintStatus`, change the line `if (!doc.can_continue) err.append(t(" Use “All files” to go back and add a corrected file."));`
  to `if (!doc.can_continue) err.append(t(" Go to step 1 to add a corrected file."));`.

```js
async function openDoc(id) {
  currentId = id; currentDoc = null;
  $("doc").hidden = false;
  $("pages").replaceChildren(); $("doc-name").textContent = ""; $("doc-status").textContent = t("Opening…");
  $("doc-error").hidden = true; $("ck-needs").hidden = true; $("ck-foot").replaceChildren(); $("ck-company").replaceChildren();
  clearTimeout(docTimer);
  ckDrawList();                                  // the chosen file is marked in the list
  await pollDoc(true);
}

async function pollDoc(first) {
  if (currentId === null || $("check").hidden) return;
  const id = currentId;
  try {
    const doc = await api("GET", `/api/jobs/${encodeURIComponent(id)}`);
    if (id !== currentId) return;
    const finished = currentDoc && currentDoc.status !== "done" && doc.status === "done";
    const changed = first || !currentDoc || doc.status !== currentDoc.status || doc.pages_done !== currentDoc.pages_done;
    const active = changed ? showDoc(doc) : ckBusy(doc);
    if (finished) await ckLoad();                // its problems in the month are known now
    if (changed) ckDrawFile();
    if (active) docTimer = setTimeout(() => pollDoc(false), 2500);
  } catch (e) {
    if (id !== currentId) return;
    $("doc-status").textContent = "";
    $("doc-error").hidden = false; $("doc-error").textContent = e.message;
  }
}
```

  `setupDocButtons` moves without the `back` line (already deleted in Task 4) and is called at the end of `check.js`:
  `setupDocButtons();`. Delete its call and every moved function from `app.js` (check: `grep -n "function buildPage\|setupDocButtons\|currentDoc" static/app.js` prints nothing).

- [ ] **Step 5: Load the scripts.** In `static/index.html` insert after `upload.js`:

```html
<script src="check.js"></script>
<script src="columns.js"></script>
```

  and in `tests/test_app.py` set
  `SCRIPTS = ["i18n.js", "app.js", "paycommon.js", "upload.js", "check.js", "columns.js", "steps.js"]`.

- [ ] **Step 6: Malay.** Add to `MS`:

```js
  "All months": "Semua bulan",
  "No company yet": "Belum ada syarikat",
  "{n} yellow": "{n} kuning",
  "! Needs you": "! Perlukan anda",
  "Not in this month": "Tiada dalam bulan ini",
  "This file needs you": "Fail ini perlukan anda",
  "Not in this month's payroll": "Tiada dalam gaji bulan ini",
  "Next file with yellow cells →": "Fail seterusnya dengan sel kuning →",
  "No other file needs checking": "Tiada fail lain perlu disemak",
  "See {name} in payroll →": "Lihat {name} dalam gaji →",
  "Go to payroll for {month} →": "Pergi ke gaji {month} →",
  "Nothing here yet. Add files in step 1.": "Belum ada apa-apa di sini. Tambah fail dalam langkah 1.",
  "No files for {month}. Choose “All months” to see every file.": "Tiada fail untuk {month}. Pilih “Semua bulan” untuk melihat semua fail.",
  " Go to step 1 to add a corrected file.": " Pergi ke langkah 1 untuk menambah fail yang dibetulkan.",
```

- [ ] **Step 7: Run everything**

Run: `"$PY" -m pytest -q`; `"$PY" tools/check_i18n.py`; `"$PY" tools/check_patterns.py`;
`sh tools/clickthrough/run.sh upload_page`; `sh tools/clickthrough/run.sh check_page`;
`SLOW_FILE=1 sh tools/clickthrough/run.sh check_reading`.
Expected: tests pass, `missing Malay: 0`, `0 not translated`, each click-through `No problems.` (In `check_page`,
"See ZUL in payroll →" leads to step 3, which opens Upload until Task 6: assert only `location.hash` there, as written.)

- [ ] **Step 8: Commit** (scan the diff)

```bash
git add static tools/clickthrough tests/test_app.py
git commit -m "Step 2: the list of files with their state, the chosen file with what it needs in the month, the column choice in place, and the buttons on"
```

---

### Task 6: Step 3 — the people list, top bar and company panel

**Files:**
- Create: `static/people.js` (replaces `static/companies.js`; delete `companies.js`)
- Modify: `static/settings.js`, `static/paytable.js`, `static/index.html` (scripts), `static/i18n.js`,
  `tests/test_app.py` (`SCRIPTS`)
- Create: `tools/clickthrough/people_page.py`

**Interfaces:**
- Consumes: Task 2's `/people`; Task 4's helpers; Task 5's `monthTitle`, `shiftMonth`.
- Produces: `showPeople(month, sel)`, `ppLoad() -> Promise`, `ppRefreshSoon()`, `ppDrawEmployeeNeeds()`,
  `ppDrawWalk()`, `employeeHash(month, id)`, `companyHash(month, company)`, and the names `settings.js` /
  `paytable.js` use: `moMonth`, `ppView`, `coCompany`, `coView`, `coError(msg)`, `moError(msg)`, `coAct(button,
  action)`, `loadCompany()`, `downloadFile(url, showError)`, `itemNode(item)`.

- [ ] **Step 1: Write the failing click-through** `tools/clickthrough/people_page.py`:

```python
"""Step 3: the list, an employee chosen by itself, a company with signs in its name, an empty month, a gone employee."""
from drive import BASE, expect


async def scenario(page, downloads):
    await page.goto(f"{BASE}/#/payroll/2026-09")
    await page.ev("T.until(() => /\\/e\\//.test(location.hash), 'an employee is chosen')")
    expect("step 3 on", await page.ev("document.getElementById('step-payroll').classList.contains('on')"), True)
    heads = await page.ev("T.text('#pp-list .side-head strong')")
    print("  companies:", heads)
    expect("A & B (M) listed", "A & B (M)" in heads, True)
    await page.ev("[...document.querySelectorAll('#pp-list .side-head')].find((b) => b.textContent.includes('A & B (M)')).click(); T.sleep(600)")
    expect("company address", await page.ev("decodeURIComponent(location.hash)"), "#/payroll/2026-09/c/A & B (M)")
    expect("company panel shows it", await page.ev("document.getElementById('co-title').textContent"), "A & B (M) - September 2026")
    expect("pay table drawn", await page.ev("T.until(() => document.querySelector('#co-pay-table table'), 'pay table')"), True)
    # search filters the list
    await page.ev("T.set('pp-search', 'siti'); T.sleep(200)")
    found = await page.ev("T.text('#pp-list .side-item')")
    expect("search keeps SITI only", "SITI" in found and "ALI" not in found, True)
    await page.ev("T.set('pp-search', ''); T.sleep(200)")
    # an empty month
    await page.goto(f"{BASE}/#/payroll/2026-03")
    await page.ev("T.until(() => !document.getElementById('pp-empty').hidden, 'empty month')")
    expect("empty month stays put", await page.ev("location.hash"), "#/payroll/2026-03")
    await page.ev("T.click('Go to step 1')")
    expect("to step 1", await page.ev("!document.getElementById('upload').hidden"), True)
```

(The remembered employee removed in another tab is checked in Task 7, once the employee view is in step 3.)

Run: `sh tools/clickthrough/run.sh people_page` — Expected: problems.

- [ ] **Step 2: Create `static/people.js`**

```js
"use strict";
// Step 3, Payroll: the month bar (‹ ›, Month settings, Million's employee list, payroll CSV, the month's Million file),
// the list of the month's companies and employees (left), and the company or employee chosen (right).
// What the list says comes from GET /api/payroll/<month>/people; the employee view (employee.js), the Look panel
// (look.js), the pay table (paytable.js) and the settings (settings.js) draw inside this page.
// Loaded after check.js and paycommon.js; uses their helpers.

let moMonth = null;          // the month shown ("2026-09")
let ppView = null;           // what the server last sent (GET /people)
let ppSel = { employee: null, look: false, company: null };
let coCompany = null;        // the company whose panel is open
let coView = null;           // its row of ppView
let ppChain = Promise.resolve();
let ppTimer = null;

function companyHash(month, company) { return `#/payroll/${month}/c/${encodeURIComponent(company)}`; }
function employeeHash(month, id) { return `#/payroll/${month}/e/${encodeURIComponent(id)}`; }
function moError(message) { $("mo-error").hidden = !message; $("mo-error").textContent = message || ""; }
function coError(message) { $("co-error").hidden = !message; $("co-error").textContent = message || ""; }

function statusText(row) {
  if (row.status === "none") return t("No files yet");
  if (row.status === "needs") return tn(row.needs, "Needs you: {n} thing", "Needs you: {n} things");
  if (row.status === "million") return tn(row.waiting, "Ready, {n} waiting for Million", "Ready, {n} waiting for Million");
  return t("Ready");
}

function companyStatus(r) {
  const parts = [r.status === "none" && r.files_needing ? "" : statusText(r)];
  if (r.files_needing) parts.push(tn(r.files_needing, "{n} file needs you in step 2", "{n} files need you in step 2"));
  if (r.own) parts.push(t("own settings"));
  return parts.filter(Boolean).join(" · ");
}

function everyone() { return ppView ? ppView.companies.flatMap((r) => r.employees) : []; }

async function showPeople(month, sel) {
  const other = month !== moMonth;
  moMonth = month; ppSel = sel;
  $("mo-title").textContent = t("Payroll {month}", { month: monthTitle(moMonth) });
  if (other) { $("mo-run-result").hidden = true; $("mo-settings").hidden = true; }
  moError("");
  if (!ppView || ppView.month !== month) await ppLoad();
  else { ppDraw(); ppRefreshSoon(); }
  ppShowSelection();
}

// The month from the server again (one request after the other, so an older answer never draws over a newer one).
function ppLoad() {
  const month = moMonth;
  ppChain = ppChain.then(async () => {
    if (month !== moMonth) return;
    try {
      const view = await api("GET", `/api/payroll/${month}/people`);
      if (month === moMonth) { ppView = view; ppDraw(); }
    } catch (e) { moError(e.message); }
  });
  return ppChain;
}
function ppRefreshSoon() { clearTimeout(ppTimer); ppTimer = setTimeout(() => ppLoad(), 800); }
function loadCompany() { return ppLoad(); }          // settings.js and paytable.js say this after a change

function ppDraw() {
  if (!ppView) return;
  const v = ppView;
  const info = [addedByThemselves(v.added_by_themselves), v.numbered ? newNumbersText(v.numbered) : ""].filter(Boolean).join(" ");
  $("mo-info").hidden = !info; $("mo-info").textContent = info;
  $("mo-total").replaceChildren(
    t("{a} of {b} employees ready.", { a: v.ready_employees, b: v.employees }) + " ",
    v.checked_with_million ? "" : t("The Employee Nos. are not being checked against Million: import Million's employee list.") + " ",
    v.files_needing ? el("button", { type: "button", class: "link",
      text: tn(v.files_needing, "{n} file needs you in step 2 →", "{n} files need you in step 2 →"),
      onclick: () => { location.hash = "#/check"; } }) : "");
  $("mo-csv").disabled = !v.employees;
  stepBadge("payroll", v.companies.reduce((n, r) => n + r.needs, 0));
  ppDrawList();
  if (!$("company").hidden) drawCompany();
  if (!$("employee").hidden) { ppDrawEmployeeNeeds(); ppDrawWalk(); }
}

// The companies the list shows (Company chooser of step 2, search box), each with its employees that match.
function ppRows() {
  const q = $("pp-search").value.trim().toLowerCase();
  return ppView.companies.filter((r) => companyMatches(r.company))
    .map((r) => ({ ...r, shown: r.employees.filter((e) => !q || `${e.emp_no} ${e.name}`.toLowerCase().includes(q)) }))
    .filter((r) => !q || r.shown.length || r.company.toLowerCase().includes(q));
}
function ppOrder() { return ppRows().flatMap((r) => r.shown); }

function ppDrawList() {
  const rows = ppRows();
  $("pp-list").replaceChildren(...rows.map((r) => el("div", { class: "pp-company" },
    el("button", { type: "button", class: "side-head" + (ppSel.company === r.company && !ppSel.employee ? " on" : ""),
      onclick: () => { location.hash = companyHash(moMonth, r.company); } },
    el("strong", { text: r.company || t("(no company)") }), el("small", { text: companyStatus(r) })),
    el("ul", { class: "side-list" }, ...r.shown.map((e) => el("li", {},
      el("button", { type: "button", class: "side-item" + (ppSel.employee === e.id ? " on" : ""),
        onclick: () => { location.hash = employeeHash(moMonth, e.id); } },
      el("span", { class: "name", text: [e.emp_no, e.name].filter(Boolean).join(" ") || t("An employee") }),
      el("span", { class: e.status === "needs" ? "pill check" : "pill good",
        text: e.status === "needs" ? "!" : e.status === "million" ? t("Waiting for Million") : "✓" }))))))));
  $("pp-none").hidden = rows.length > 0 || !ppView.companies.length;
}

function ppShowPane(which) {
  for (const id of ["company", "employee", "look", "pp-empty"]) $(id).hidden = id !== which;
}

// What the address chose, or else the first employee who needs the user (or the first one).
function ppShowSelection() {
  if (!ppView) return;
  const sel = ppSel;
  const gone = (sel.employee && !everyone().some((e) => e.id === sel.employee))
    || (sel.company !== null && !ppView.companies.some((r) => r.company === sel.company));
  if (gone) { forget("place.payroll"); location.replace(`#/payroll/${moMonth}`); return; }
  if (!sel.employee && sel.company === null) {
    const order = ppOrder();
    const first = order.find((e) => e.status === "needs") || order[0] || everyone()[0];
    if (first) location.replace(employeeHash(moMonth, first.id)); else ppShowPane("pp-empty");
    return;
  }
  if (sel.employee && sel.look) { ppShowPane("look"); if (typeof showLook === "function") showLook(moMonth, sel.employee); }
  else if (sel.employee) { ppShowPane("employee"); if (typeof showEmployee === "function") showEmployee(moMonth, sel.employee); }
  else { ppShowPane("company"); showCompany(sel.company); }
}

// ------------------------------------------------------------------------------------------------ the company panel
function showCompany(company) {
  if (company !== coCompany) { $("co-settings").hidden = true; $("co-million").hidden = true; coError(""); }
  coCompany = company;
  drawCompany();
  if (company) loadPayTable();
}

function drawCompany() {
  coView = ppView.companies.find((r) => r.company === coCompany)
    || { company: coCompany, status: "none", needs: 0, waiting: 0, items: [], employees: [], million_new: [], files_needing: 0 };
  $("co-title").textContent = `${coCompany || t("(no company)")} - ${monthTitle(moMonth)}`;
  $("co-status").textContent = companyStatus(coView);
  for (const id of ["co-settings-open", "co-csv", "co-pay"]) $(id).hidden = !coCompany;   // files with no company: none
  const items = coView.items.map(itemNode);
  if (coView.files_needing) {
    items.push(el("li", { class: "need" }, el("strong", { text: tn(coView.files_needing,
      "{n} file of this company needs you in step 2.", "{n} files of this company need you in step 2.") }),
    el("div", { class: "need-buttons" }, el("button", { type: "button", class: "primary", text: t("Go to step 2 →"),
      onclick: () => { location.hash = "#/check"; } }))));
  }
  $("co-items").replaceChildren(items.length ? el("ol", { class: "needs" }, ...items)
    : el("p", { class: "muted", text: t("Nothing needs you here.") }));
  $("co-csv").disabled = !coView.employees.length;
  drawMillionNew();
}

// Do something for an item, then draw the month again from the server (and the employee, when one is open).
async function coAct(button, action) {
  button.disabled = true;
  try {
    await action(); coError(""); moError("");
    await ppLoad();
    if (!$("employee").hidden && typeof emLoad === "function") await emLoad();
  } catch (e) { ($("company").hidden ? moError : coError)(e.message); button.disabled = false; }
}

function employeeName(id) {
  const e = everyone().find((x) => x.id === id);
  return e ? (e.name || t("An employee")) : t("An employee");
}

const ITEM_HEADS = {
  look: "{name}: cells to check on the card",
  days: "{name}: days that do not add up",
  column: "{name}: Table Reader cannot work out the days",
  nocard: "{name}: no time card yet",
  held: "{name}: not ready for the Million file",
};

// One thing that needs the user about an employee or a company (the files' are in step 2).
function itemNode(item) {
  const name = item.employee ? employeeName(item.employee) : "";
  const buttons = [];
  let head = "", details = [];
  if (ITEM_HEADS[item.kind]) {
    head = t(ITEM_HEADS[item.kind], { name });
    details = item.texts.map(item.kind === "held" ? runReason : tm);
    if (item.places) {
      details.unshift(tn(item.places, "{n} line of the time cards to check.", "{n} lines of the time cards to check."));
      buttons.push(el("button", { type: "button", class: "primary", text: t("Look"),
        onclick: () => { location.hash = `${employeeHash(moMonth, item.employee)}/look`; } }));
    }
    if (item.kind === "look" && item.texts.length) {               // problems the panel cannot show: on the card
      item.cards.forEach((c, n) => buttons.push(el("button", { type: "button", title: c.name,
        text: item.cards.length > 1 ? t("Check card {n} →", { n: n + 1 }) : t("Check this card →"),
        onclick: () => { location.hash = `#/check/${encodeURIComponent(c.id)}`; } })));
    }
  } else if (item.kind === "settings") {
    head = t("{company}: the month's default changed after this company got its own settings", { company: item.company });
    details = [t("Public holidays and rest days marked in the month's settings are not copied to a company with its own settings. Check its calendar.")];
    const right = el("button", { type: "button", text: t("It is right") });
    right.addEventListener("click", () => keepCompanySettings(right));
    buttons.push(el("button", { type: "button", class: "primary", text: t("Open settings"), onclick: openCompanySettings }), right);
  } else if (item.kind === "offer") {
    head = t("{name}: Million has Employee No. {no} for {million}", { name, no: item.emp_no, million: item.million_name });
    const use = el("button", { type: "button", class: "primary", text: t("Use {no}", { no: item.emp_no }) });
    use.addEventListener("click", () => coAct(use, () => api("PUT",
      `/api/payroll/${moMonth}/employees/${encodeURIComponent(item.employee)}`, { emp_no: item.emp_no })));
    buttons.push(use);
  } else if (item.kind === "empno") {
    head = t("{name}: Employee No. to fix", { name });
    details = [item.why === "empty" ? t("It is empty. Type it exactly as in Million Payroll.")
      : item.why === "shared" ? t("Employee No. {no} is used for {n} employees. Each employee needs their own.", { no: item.emp_no, n: item.count })
        : t("In Million Payroll, Employee No. {no} is {million}.", { no: item.emp_no, million: item.million_name })];
  }
  return el("li", { class: "need" }, el("strong", { text: head }),
    ...details.map((d) => el("p", { class: "legend", text: d })), el("div", { class: "need-buttons" }, ...buttons));
}

// The open employee's "Needs you", and Previous / Next needing you.
function ppDrawEmployeeNeeds() {
  const e = everyone().find((x) => x.id === ppSel.employee);
  const items = e ? e.items : [];
  $("em-needs").hidden = !items.length;
  $("em-needs").replaceChildren(el("h3", { text: t("Needs you") }), el("ol", { class: "needs" }, ...items.map(itemNode)));
}

function ppDrawWalk() {
  const order = ppOrder();
  const at = order.findIndex((e) => e.id === ppSel.employee);
  const prev = at > 0 ? order[at - 1] : null;
  const next = [...order.slice(at + 1), ...order.slice(0, Math.max(at, 0))].find((e) => e.status === "needs");
  $("em-walk").replaceChildren(
    el("button", { type: "button", text: t("‹ Previous"), disabled: !prev,
      onclick: () => { location.hash = employeeHash(moMonth, prev.id); } }),
    el("button", { type: "button", class: "primary", text: next ? t("Next needing you ›") : t("Nobody else needs you"),
      disabled: !next, onclick: () => { location.hash = employeeHash(moMonth, next.id); } }));
}
```

  Then move these from `static/companies.js` into `people.js` **unchanged**: `personText`, `showMonthSummary`,
  `downloadFile`, `copyBySelecting`, `copyText`, `drawMillionNew`, and the listeners for `co-million-open`, `co-csv`,
  `mo-csv`, `mo-million-import`. Then change:
  - the `mo-run` listener: `!$("month").hidden` → `!$("people").hidden`;
  - the `mo-million-file` change listener: `showMonth(moMonth)` → `await ppLoad()`;
  - the month arrows: `$("mo-prev").addEventListener("click", () => { location.hash = `#/payroll/${shiftMonth(moMonth, -1)}`; });`
    and the same with `1` for `mo-next`;
  - add `$("pp-to-upload").addEventListener("click", () => { location.hash = "#/"; });`,
    `$("pp-search").addEventListener("input", () => { ppDrawList(); if (!$("employee").hidden) ppDrawWalk(); });`,
    and set the search box's words: `$("pp-search").placeholder = t("Search name or Employee No.");
    $("pp-search").setAttribute("aria-label", t("Search name or Employee No."));`.

  Delete `static/companies.js` (`git rm static/companies.js`).

- [ ] **Step 3: Adapt `static/settings.js`.** Header comment: "Loaded after people.js and uses its state (moMonth,
  ppView, coCompany, coView) and helpers." In `openMonthSettings`: `moOver.settings` → `ppView.settings`, and
  `drawMonth(await api("GET", `/api/payroll/${moMonth}/companies`));` → `await ppLoad();`.

- [ ] **Step 4: Adapt `static/paytable.js`.** Header comment: "The company panel's Pay preview table … Loaded after
  people.js and uses its helpers." Delete `showCompanyTab` and the two `co-tab-*` listeners. Replace the `co-add`
  listener:

```js
// An employee typed in by hand, in this company (a new Employee No. from its name), opened right away.
$("co-add").addEventListener("click", async () => {
  const button = $("co-add"), month = moMonth;
  button.disabled = true;
  try {
    const { employee } = await api("POST", `/api/payroll/${month}/employee`, { company: coCompany });
    coError(""); ppView = null;                  // step 3 asks the server again, so the list has the new employee
    location.hash = employeeHash(month, employee);
  } catch (e) { coError(e.message); }
  finally { button.disabled = false; }
});
```

- [ ] **Step 5: Load the scripts.** In `index.html` after `columns.js`:

```html
<script src="people.js"></script>
<script src="paytable.js"></script>
<script src="settings.js"></script>
```

  and `SCRIPTS = ["i18n.js", "app.js", "paycommon.js", "upload.js", "check.js", "columns.js", "people.js",
  "paytable.js", "settings.js", "steps.js"]`.

- [ ] **Step 6: Malay.** Add to `MS`:

```js
  "{n} file needs you in step 2": "{n} fail perlukan anda dalam langkah 2",
  "{n} files need you in step 2": "{n} fail perlukan anda dalam langkah 2",
  "{n} file needs you in step 2 →": "{n} fail perlukan anda dalam langkah 2 →",
  "{n} files need you in step 2 →": "{n} fail perlukan anda dalam langkah 2 →",
  "{n} file of this company needs you in step 2.": "{n} fail syarikat ini perlukan anda dalam langkah 2.",
  "{n} files of this company need you in step 2.": "{n} fail syarikat ini perlukan anda dalam langkah 2.",
  "Go to step 2 →": "Pergi ke langkah 2 →",
  "{a} of {b} employees ready.": "{a} daripada {b} pekerja sedia.",
  "Check this card →": "Semak kad ini →",
  "Check card {n} →": "Semak kad {n} →",
  "‹ Previous": "‹ Sebelumnya",
  "Next needing you ›": "Seterusnya yang perlukan anda ›",
  "Nobody else needs you": "Tiada orang lain perlukan anda",
  "Search name or Employee No.": "Cari nama atau No. Pekerja",
```

  In `tools/check_i18n.py`'s list of "words looked up through variables", change the comment
  `# companies.js: ...` to `# people.js: ...` and the one for `layout.js` to `columns.js`.

- [ ] **Step 7: Run everything**

Run: `"$PY" -m pytest -q`; the two translation checks; `sh tools/clickthrough/run.sh people_page`; and again
`upload_page` and `check_page`.
Expected: all pass, `No problems.` (The employee pane is empty until Task 7: `people_page` asserts only addresses,
the list and the company panel.)

- [ ] **Step 8: Commit** (scan the diff)

```bash
git add static tools tests/test_app.py
git commit -m "Step 3: the month's companies and employees in one list, the month bar, the company panel with its pay table; the overview and company screens are gone"
```

---

### Task 7: Step 3 — the employee panel and the Look panel in place

**Files:**
- Modify: `static/employee.js`, `static/look.js`, `static/index.html` (scripts), `static/i18n.js`,
  `tests/test_app.py` (`SCRIPTS`)
- Create: `tools/clickthrough/employee_page.py`

**Interfaces:**
- Consumes: Task 6's `ppDrawEmployeeNeeds`, `ppDrawWalk`, `ppRefreshSoon`, `employeeHash`; Task 4's `forget`.
- Produces: `emLeave()` (called by `route()` on every address change), `showEmployee(month, id)`,
  `showLook(month, id)`, `refreshLook()`.

- [ ] **Step 1: Write the failing click-through** `tools/clickthrough/employee_page.py`:

```python
"""Step 3's employee: Needs you, the window, a card to step 2, Look in place, typing then leaving, Previous / Next."""
from drive import BASE, expect

M = "2026-09"


async def scenario(page, downloads):
    people = await page.ev(f"fetch('/api/payroll/{M}/people').then((r) => r.json())")
    ids = {e["name"]: e["id"] for r in people["companies"] for e in r["employees"]}
    await page.goto(f"{BASE}/#/payroll/{M}/e/{ids['ALI']}")
    await page.ev("T.until(() => document.querySelector('#em-window .pw-title'), 'window drawn')")
    expect("walk buttons", "Previous" in await page.ev("T.text('#em-walk button')"), True)
    expect("card button", "Check this card →" in await page.ev("T.text('#em-cards button')"), True)
    # typing in the name and leaving at once (before the 500 ms wait ends) keeps what was typed (Review Focus 3)
    await page.ev("T.set('ew-name', 'ALI BIN TEST'); document.getElementById('step-check').click(); T.sleep(1500)")
    after = await page.ev(f"fetch('/api/payroll/{M}/employee/{ids['ALI']}').then((r) => r.json())")
    expect("typed name saved", after["employee"]["name"], "ALI BIN TEST")
    # the card button opens the file in step 2
    await page.goto(f"{BASE}/#/payroll/{M}/e/{ids['ALI']}")
    await page.ev("T.until(() => document.querySelector('#em-cards button'), 'cards'); T.click('Check this card →')")
    expect("card in step 2", await page.ev("location.hash.startsWith('#/check/')"), True)
    # Look in place and back
    await page.goto(f"{BASE}/#/payroll/{M}/e/{ids['SITI']}/look")
    await page.ev("T.until(() => !document.getElementById('look').hidden, 'look shown'); T.sleep(500)")
    await page.ev("document.getElementById('lk-back').click(); T.sleep(500)")
    expect("back to SITI", await page.ev("location.hash"), f"#/payroll/{M}/e/{ids['SITI']}")
    # a remembered employee removed in another tab: step 3 starts again from the list (Review Focus 2)
    await page.goto(f"{BASE}/#/payroll/{M}/e/{ids['ZUL']}")
    await page.ev("T.until(() => document.querySelector('#em-window .pw-title'), 'ZUL drawn')")
    await page.ev(f"fetch('/api/payroll/{M}/employee/{ids['ZUL']}', {{ method: 'DELETE' }}).then((r) => r.status)")
    await page.ev("document.getElementById('step-upload').click(); T.sleep(300); document.getElementById('step-payroll').click()")
    await page.ev(f"T.until(() => /\\/e\\//.test(location.hash) && !location.hash.includes({ids['ZUL']!r}), 'another employee', 6000)")
    expect("no error left", await page.ev("document.getElementById('em-error').hidden && document.getElementById('mo-error').hidden"), True)
```

(If SITI has no lines to look at in the made-up data, the Look panel goes straight back to the employee: the scenario
still checks that the address ends on SITI.)

Run: `sh tools/clickthrough/run.sh employee_page` — Expected: problems.

- [ ] **Step 2: Adapt `static/employee.js`.**
  - Header comment, first two lines: "The employee view inside step 3 (#/payroll/<month>/e/<employee id>): one employee's
    Edit Payroll window, their time cards (check in step 2, move to another employee, take off), the Hours column,
    and Remove." and "Loaded after people.js and uses its helpers (monthTitle, employeeHash, ppDrawEmployeeNeeds,
    ppDrawWalk, ppRefreshSoon) and paycommon.js's."
  - Replace the start of `showEmployee` (its first two lines and the two assignments) with:

```js
async function showEmployee(month, id) {
  if (emView && (month !== emMonth || id !== emId)) await emFlush();     // what was typed for the last one goes first
  emMonth = month;
  emId = id;
```

    (keep the rest of the function from `emView = null; emTab = "basic";` on).
  - Add after `emFlush`:

```js
// Leaving the employee (another address): what is still waiting for the user to stop typing goes now.
function emLeave() { if (emView) emFlush(); }
```

  - Replace `emFail` (an employee removed in another tab: step 3 starts again from its list instead of showing an
    employee that is gone):

```js
function emFail(e) {
  emError(e.message);
  if (e.code === "EMPLOYEE_NOT_FOUND") {
    emView = null;
    $("em-cards").hidden = true; $("em-window").replaceChildren(); emState("");
    forget("place.payroll"); ppView = null;
    location.replace(`#/payroll/${emMonth}`);
  }
}
```

  - In `emSend`, after `emDraw();` in the success branch add `ppRefreshSoon();`; in `emAct`, change
    `await emLoad();` to `await emLoad(); ppRefreshSoon();`.
  - At the end of `emDraw` add: `ppDrawEmployeeNeeds(); ppDrawWalk();`.
  - In `emDrawCards`: the "Open the card" button becomes
    `el("button", { type: "button", text: t("Check this card →"), onclick: () => { location.hash = `#/check/${encodeURIComponent(card.doc)}`; } })`;
    the Take off confirm text becomes
    `t("Take this card off the employee? It goes back to step 2 as a card whose employee is not known.")`;
    in Remove, replace `const back = companyHash(emMonth, emView.company);` with
    `const back = `#/payroll/${emMonth}`;` and `.then(() => { location.hash = back; })` with
    `.then(() => { forget("place.payroll"); ppView = null; location.hash = back; })`.
  - Delete the `em-back` listener at the end of the file.

- [ ] **Step 3: Adapt `static/look.js`.**
  - Header comment last line: "Inside step 3 (#/payroll/<month>/e/<employee id>/look). Loaded after people.js and uses
    its helpers (monthTitle, employeeHash, ppRefreshSoon)."
  - In `showLook`, delete the first two lines (`clearTimeout(docTimer)…` and `hideScreens()…`).
  - Replace `backFromLook`:

```js
function backFromLook() { location.hash = employeeHash(lkMonth, lkEmployee); }
```

  - In the `lk-accept` listener, after `await loadLook(card.doc, true);` add `ppRefreshSoon();`.

- [ ] **Step 4: Load the scripts.** In `index.html` after `people.js`:

```html
<script src="employee.js"></script>
<script src="look.js"></script>
```

  and set `SCRIPTS` to the final order: `["i18n.js", "app.js", "paycommon.js", "upload.js", "check.js", "columns.js",
  "people.js", "employee.js", "look.js", "paytable.js", "settings.js", "steps.js"]`.

- [ ] **Step 5: Malay.** Add to `MS`:

```js
  "Take this card off the employee? It goes back to step 2 as a card whose employee is not known.": "Tanggalkan kad ini daripada pekerja? Ia kembali ke langkah 2 sebagai kad yang pekerjanya tidak diketahui.",
```

- [ ] **Step 6: Run everything**

Run: `"$PY" -m pytest -q`; the two translation checks; all click-throughs:
`upload_page`, `check_page`, `SLOW_FILE=1 … check_reading`, `people_page`, `employee_page`.
Expected: all pass, every click-through `No problems.`

- [ ] **Step 7: Commit** (scan the diff)

```bash
git add static tools tests/test_app.py
git commit -m "Step 3: the employee with what needs them, Previous and Next, the card to step 2, and the Look panel in place"
```

---

### Task 8: Old requests removed, guides, the real-data comparison, notes

**Files:**
- Modify: `app.py` (remove `payroll_companies`, `payroll_company`, `view_of`), `static/app.css` (dead rules),
  `GUIDE - Table Reader to Million.html`, `PANDUAN - Table Reader ke Million.html`, `packaging/guide/guide.html`,
  `PROGRESS.md`, `NEXT-SESSION.md`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_app.py`):

```python
def test_the_company_screens_requests_are_gone(client):
    assert client.get("/api/payroll/2026-09/companies").status_code == 404
    assert client.get("/api/payroll/2026-09/company", params={"name": ""}).status_code == 404
```

Run: `"$PY" -m pytest -q -k company_screens_requests_are_gone` — Expected: FAIL (200).

- [ ] **Step 2: Before removing them, take the "before" figures of the real data** (read-only, on a copy, counts only).
  Write `<scratchpad>/steps_compare.py`:

```python
"""Real data, on a COPY: every employee's figures, the month's run, and the count of each kind of file problem,
with one version of the code. Prints counts only; writes figures keyed by random employee ids (no names).

python steps_compare.py <repo> <home copy> <before|after> <month> <out.json>"""
import json, os, sys
from collections import Counter
from pathlib import Path

repo, home, mode, month, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5])
os.environ["TABLE_READER_HOME"] = str(home)
sys.path.insert(0, str(repo))
from fastapi.testclient import TestClient  # noqa: E402
import app as app_module  # noqa: E402
from jobs import Jobs, default_root  # noqa: E402


def figures(result):
    return {"values": {k: [v["value"], v["computed"], v["edited"]] for k, v in result["values"].items()},
            "issues": sorted(i["text"] for i in result["issues"] if i["kind"] != "removed"),
            "complete": result["complete"], "pay": result.get("pay")}


with TestClient(app_module.create_app(Jobs(default_root(), reader=lambda image: {})), base_url="http://localhost") as c:
    got, kinds, ids = {"employees": {}}, Counter(), []
    if mode == "before":
        for row in c.get(f"/api/payroll/{month}/companies").json()["companies"]:
            view = c.get(f"/api/payroll/{month}/company", params={"name": row["company"]}).json()
            ids += [e["id"] for e in view["employees"]]
            kinds.update(i["kind"] for i in view["items"] if i["kind"] in ("unplaced", "month", "layout"))
            kinds["other"] += len(view.get("other_files", []))
            kinds["company"] += len(view.get("files", []))
    else:
        ids = [e["id"] for r in c.get(f"/api/payroll/{month}/people").json()["companies"] for e in r["employees"]]
        for items in c.get(f"/api/payroll/{month}/files").json()["files"].values():
            kinds.update(i["kind"] for i in items)
    for i in ids:
        got["employees"][i] = figures(c.get(f"/api/payroll/{month}/employee/{i}").json()["result"])
    run = c.get(f"/api/payroll/{month}/run").json()
    got["run"] = {"ready": run["ready"], "held": len(run["held"])}
    got["kinds"] = dict(kinds)
out.write_text(json.dumps(got), encoding="utf-8")
print(mode, "employees:", len(got["employees"]), "run:", got["run"], "file problems:", got["kinds"])
```

  Make two copies of the data folder (as in Task 2 Step 6). Run "before" on the main folder's checkout (branch
  `pdf-text`, path `C:/Users/TENGA CEKAP/Documents/table-reader`) with copy 1, and "after" on this worktree with copy 2:

```bash
"$PY" <scratchpad>/steps_compare.py "C:/Users/TENGA CEKAP/Documents/table-reader" <copy1> before 2026-09 <scratchpad>/before.json
"$PY" <scratchpad>/steps_compare.py "$(pwd)" <copy2> after 2026-09 <scratchpad>/after.json
```

  Then compare with a three-line script: `employees` equal, `run` equal, `kinds` equal; print only `True/False` and
  counts. Expected: all `True` (84 employees, run 8 ready / 76 held; the same count of each kind). Delete both copies,
  both JSON files and the scripts afterwards. If anything differs, stop and report it to the user with counts only.

- [ ] **Step 3: Remove the old requests.** In `app.py` delete `view_of`, `payroll_companies` and `payroll_company`
  (the three blocks under "payroll by company" after `file_items`). Keep `month_state`, `layout_items`, `file_items`,
  `step_views` and the two new routes. Run `"$PY" -m pytest -q` — Expected: all pass, including the new test.
  `grep -rn "api/payroll/[^\"']*/compan" static/ tests/ app.py` must print nothing.

- [ ] **Step 4: Dead styles.** In `static/app.css` delete the rules `tr.company-row`, `tr.company-row:hover td, …`,
  `tr.company-row.needs td:last-child`, `tr.company-row.none td` (no table uses `company-row` any more — check with
  `grep -rn "company-row" static/`).

- [ ] **Step 5: Guides.** Rewrite for the three steps (made-up names in every example):
  - `packaging/guide/guide.html`: step 1 "Open it and add your files" mentions **1 Upload** and that the files appear
    under "Just added"; step 3's text says the files are in **2 Check reading** (list on the left, file on the right,
    "Next file with yellow cells"); the "For Million Payroll" paragraph becomes: "press **3 Payroll** at the top. The
    month's employees are listed by company on the left; ! marks someone who needs you. Mark the public holidays in
    **Month settings**. A file that needs you (whose card, which month, the columns of a new kind of card) is shown in
    step 2 on that file. Table Reader works out days worked and overtime from the cells you checked and lists anything
    it could not work out; you can type over any figure in the employee's window. Then press **Make the month's Million
    file**. The full steps are in the guide "Table Reader to Million"."
  - `GUIDE - Table Reader to Million.html` and `PANDUAN - Table Reader ke Million.html`: sections B and C (written in
    session 23 for the month overview, company screen and employee view) become: B — "2 Check reading": the list, the
    Month and Company filters, "This file needs you" (each kind, with its buttons), the column choice, "See … in
    payroll →"; C — "3 Payroll": the month bar, the list (search, !, ✓), an employee (Needs you, Look, cards, the Edit
    Payroll window, Previous / Next needing you), a company heading (settings, pay preview, Add employee, New in
    Million), then the month's Million file with its summary first. Keep everything about Million itself unchanged.
  - Do not regenerate `Table Reader guide.pdf` or its pictures (needs the user's OK).

- [ ] **Step 6: Notes.** `PROGRESS.md`: a "Session 24" entry at the top (what was built, the server requests, what was
  removed, the real-data counts, the click-throughs, what is left). `NEXT-SESSION.md`: the paste-in line mentions
  sessions 9 to 24; section 0 gets a "Session 24" bullet ("three steps built on branch `three-steps`, not merged, not
  pushed, app not rebuilt"); section 1's table row "Company-first payroll" and "Browser check" are updated; the tests
  count is updated.

- [ ] **Step 7: Run everything one last time**

Run: `"$PY" -m pytest -q`; both translation checks; every click-through.
Expected: all pass; `missing Malay: 0`; `0 not translated`; `No problems.` everywhere.

- [ ] **Step 8: Commit** (scan the diff; the guides must hold only made-up names)

```bash
git add app.py static/app.css tests/test_app.py "GUIDE - Table Reader to Million.html" "PANDUAN - Table Reader ke Million.html" packaging/guide/guide.html PROGRESS.md NEXT-SESSION.md
git commit -m "Payroll: the company screen's two requests are gone; guides and notes for the three steps"
```

- [ ] **Step 9: Whole-branch review.** One fresh reviewer for `git diff pdf-text...three-steps` against the spec and
  this plan's Review Focus; fix what it finds (tests first), re-run Step 7, commit, then ask the user about merging,
  rebuilding, pushing and the `download` branch — each separately.
