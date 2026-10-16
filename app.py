"""Table Reader web app: the API over `Jobs` plus the single page in static/. Runs only on this PC (localhost)."""
from __future__ import annotations

import os
import hashlib
import io
import logging
import re
import sys
import threading
import uuid
from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import companies
import layouts
import ocr
import payroll
from inbox import Inbox
from jobs import Jobs, _read_json, _write_json, count_to_check, merged_pages, safe_name
from ocr import OcrError

MAX_UPLOAD_BYTES = 150 * 1024 * 1024
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}          # urlparse().hostname is lower-case and drops the [ ]
_STATUS_FOR_CODE = {"JOB_NOT_FOUND": 404, "EMPLOYEE_NOT_FOUND": 404, "PAGE_NOT_FOUND": 404, "JOB_BUSY": 409,
                    "JOB_NOT_FINISHED": 409, "CELL_CHANGED": 409}


NO_RETRY_CODES = {"FILE_TYPE", "PDF_UNREADABLE", "PDF_EMPTY", "TOO_MANY_PAGES", "IMAGE_UNREADABLE", "FILE_MISSING"}
log = logging.getLogger(__name__)


def page_problem(page: dict) -> str | None:
    """One plain sentence when a page gave no table, saying what to do (None when there are rows)."""
    if page["rows"]:
        return None
    if page["quality"] == "ILLEGIBLE":
        return ("Claude could not read this page: the picture is too blurry, dark or small. Take the photo again in "
                "good light (or scan it) and add it as a new file.")
    return ("No table was found on this page. If there is one, check that the whole page is in the picture, then "
            "add the file again.")


def static_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))        # _MEIPASS: inside the packaged .exe
    return base / "static"


def page_html() -> str:
    """index.html with each script / style address stamped with that file's fingerprint (app.js?v=1a2b3c4d). A browser
    keeps scripts it already has; after an update the address is new, so it must fetch the new script. Without this an
    old script ran beside the new page and new buttons did nothing."""
    folder = static_dir()

    def stamp(match: re.Match) -> str:
        file = folder / match.group(2)
        if not file.is_file():
            return match.group(0)
        return f'{match.group(1)}{match.group(2)}?v={hashlib.sha256(file.read_bytes()).hexdigest()[:8]}"'

    return re.sub(r'((?:src|href)=")([\w.-]+\.(?:js|css))"', stamp, (folder / "index.html").read_text(encoding="utf-8"))


def create_app(jobs: Jobs | None = None) -> FastAPI:
    app = FastAPI(title="Table Reader", docs_url=None, redoc_url=None, openapi_url=None)
    store = jobs or Jobs()
    app.state.jobs = store

    # ---------------------------------------------------------------------------------------------- safety
    @app.middleware("http")
    async def local_only(request: Request, call_next):
        """Only this PC's own page may talk to the app (blocks other websites reaching localhost)."""
        if (urlparse("//" + (request.headers.get("host") or "")).hostname or "") not in LOCAL_HOSTS:
            return JSONResponse({"code": "FORBIDDEN", "message": "This app can only be opened on this computer."}, 403)
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD") and origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"code": "FORBIDDEN", "message": "This request did not come from the Table Reader page."}, 403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        else:
            # The page and its scripts: always ask whether they changed. Without this the browser keeps an old script
            # for hours after an update, next to the new page (a new button then does nothing).
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.exception_handler(OcrError)
    async def ocr_error(_: Request, exc: OcrError):
        return JSONResponse({"code": exc.code, "message": exc.message}, _STATUS_FOR_CODE.get(exc.code, 400))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.error("Unexpected error on %s", request.url.path, exc_info=exc)
        return JSONResponse({"code": "UNEXPECTED", "message": "Something went wrong inside Table Reader. Reload the "
                             "page and try again. If it keeps happening, tell your support person."}, 500)

    # ---------------------------------------------------------------------------------------------- Claude
    @app.get("/api/ping")
    def ping():
        return {"app": "table-reader"}

    @app.get("/api/status")
    def status():
        return ocr.auth_status()

    @app.get("/api/activity")
    def activity():
        return {"active": store.active_count()}

    @app.post("/api/quit")
    def quit_app():
        """Close Table Reader (the page's Quit button). Documents still being read are cancelled so they can be
        continued next time."""
        store.shutdown()
        callback = getattr(app.state, "on_quit", None)
        if callback:
            callback()
        return {"quit": True}

    @app.post("/api/login")
    def login():
        ocr.start_login()
        return {"started": True}

    # ---------------------------------------------------------------------------------------------- jobs
    def detail(job_id: str) -> dict:
        meta = store.get_job(job_id)
        merged = merged_pages(store.load_result(job_id), store.load_edits(job_id))
        meta["cells_to_check"] = count_to_check(merged)
        for page in merged:
            page["problem"] = page_problem(page)
        meta["pages"] = merged
        # A damaged or oversize file fails the same way every time: Continue would only repeat the failure.
        meta["can_continue"] = meta["status"] == "failed" and (meta.get("error") or {}).get("code") not in NO_RETRY_CODES
        return meta

    @app.post("/api/jobs")
    def upload(files: list[UploadFile] = File(...)):
        """Each file becomes its own document. Files that cannot be used are reported, the rest still go ahead."""
        created, rejected = [], []
        for f in files:
            name = f.filename or "file"
            try:
                content = f.file.read(MAX_UPLOAD_BYTES + 1)
                if len(content) > MAX_UPLOAD_BYTES:
                    raise OcrError("FILE_TOO_BIG", f"{name} is larger than 150 MB. Scan it at a lower quality or split "
                                                   "it into smaller files.")
                created.append(store.create_job(name, content))
            except OcrError as exc:
                rejected.append({"name": name, "code": exc.code, "message": exc.message})
            except OSError:
                rejected.append({"name": name, "code": "SAVE_FAILED", "message": f"{name} could not be saved. Check "
                                 "that the computer has free disk space, then add it again."})
        return {"created": created, "rejected": rejected}

    @app.get("/api/jobs")
    def list_jobs():
        return store.list_jobs()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return detail(job_id)

    @app.put("/api/jobs/{job_id}/company")
    async def set_company(job_id: str, request: Request):
        try:
            body = await request.json()
        except ValueError:
            body = None
        moved = store.set_company(job_id, body.get("company") if isinstance(body, dict) else None)
        return {"moved": moved}

    @app.post("/api/jobs/{job_id}/resume")
    def resume(job_id: str):
        return store.resume(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        return store.cancel(job_id)

    @app.put("/api/jobs/{job_id}/cells")
    async def save_cells(job_id: str, request: Request):
        try:
            body = await request.json()
        except ValueError:
            body = None
        changes = body.get("changes") if isinstance(body, dict) else None
        if not isinstance(changes, list):
            raise OcrError("BAD_EDIT", "That correction could not be understood. Reload the page and try again.")
        store.save_edits(job_id, changes)
        return detail(job_id)

    @app.get("/api/jobs/{job_id}/csv")
    def download_csv(job_id: str):
        path = store.write_csv(job_id)
        return FileResponse(path, media_type="text/csv; charset=utf-8", filename=path.name)

    @app.get("/api/jobs/{job_id}/pages/{number}")
    def page_image(job_id: str, number: int):
        return FileResponse(store.page_path(job_id, number), media_type="image/png")

    # ---------------------------------------------------------------------------------------------- payroll
    plans = payroll.PayrollStore(store.root.parent / "payroll")

    def finished_documents() -> list[dict]:
        """Documents the payroll can use. ``parts`` lists the pages separately when they show different workers, and
        each worker's row separately when a month grid lists several workers."""
        docs = []
        for j in store.list_jobs():
            if j.get("status") != "done":
                continue
            try:
                parts = payroll.document_parts(merged_pages(store.load_result(j["id"]), store.load_edits(j["id"])))
            except (OcrError, OSError, ValueError):
                parts = []
            docs.append({"id": j["id"], "name": j["name"], "company": j["company"], "created": j["created"],
                         "parts": [{"ref": j["id"] + payroll.part_suffix(p["page"], p["row"]), **p} for p in parts]})
        return docs

    def part_name(doc_name: str, page: int, row: int | None, n_pages: int) -> str:
        """"card.pdf (page 2)", "grid.jpg (row 3)", "grid.pdf (page 2, row 3)"."""
        if row is None:
            return f"{doc_name} (page {page})"
        return f"{doc_name} (row {row})" if n_pages == 1 else f"{doc_name} (page {page}, row {row})"

    def part_pages(pages: list[dict], page: int, row: int | None) -> list[dict]:
        """The pages of one part: one page, or one page holding only one worker's row."""
        chosen = [p for p in pages if p["page"] == page]
        if row is None:
            return chosen
        return [{**p, "rows": p["rows"][row - 1:row], "first_row": row - 1} for p in chosen]

    def known_refs(docs: list[dict]) -> set[str]:
        return {d["id"] for d in docs} | {p["ref"] for d in docs for p in d["parts"]}

    def drop_gone_documents(plan: dict, known: set[str]) -> dict[str, int]:
        """Take time cards that are no longer in Recent files (deleted, or history reset) off each employee, so they
        cannot block saving. Returns {employee id: how many were taken off}."""
        gone = {}
        for e in plan.get("employees") or []:
            if isinstance(e, dict) and isinstance(e.get("jobs"), list):
                kept = [j for j in e["jobs"] if j in known]
                if len(kept) != len(e["jobs"]):
                    gone[e.get("id")] = len(e["jobs"]) - len(kept)
                    e["jobs"] = kept
        return gone

    def page_loader() -> tuple[Callable[[str], tuple[str, list[dict]]], dict[str, tuple[str, list[dict]]]]:
        """(load_pages, its cache) for payroll.compute_all: a card's name and pages by ref, each read once. A part
        (one worker's page of a report, or row of a sheet) gets only its own pages; a row says where it is in the
        document (``first_row``), so a problem in it points at the right row."""
        cache: dict[str, tuple[str, list[dict]]] = {}

        def load_pages(ref: str) -> tuple[str, list[dict]]:
            if ref not in cache:
                job_id, page, row = payroll.split_part(ref)
                try:
                    meta = store.get_job(job_id)
                    done = meta["status"] == "done"
                    pages = merged_pages(store.load_result(job_id), store.load_edits(job_id)) if done else []
                except (OSError, ValueError) as exc:        # a damaged reading is that employee's problem, not a crash
                    raise OcrError("JOB_NOT_FOUND", "A time card of this employee could not be opened. Read the file "
                                                    "again, or take it off this employee.") from exc
                if not done:
                    raise OcrError("JOB_NOT_FINISHED", f"{meta['name']} has not been read completely yet.")
                if page is None:
                    cache[ref] = (meta["name"], pages)
                else:                                           # one worker's page of a report, or row of a grid
                    cache[ref] = (part_name(meta["name"], page, row, len(pages)), part_pages(pages, page, row))
            return cache[ref]

        return load_pages, cache

    def million_by_no(million: dict | None) -> dict[str, dict] | None:
        return {e["emp_no"].casefold(): e for e in million["employees"]} if million else None

    def payroll_view(plan: dict, docs: list[dict], gone: dict[str, int] | None = None) -> dict:
        load_pages, cache = page_loader()
        million = plans.load_million()
        company_of_doc = {d["id"]: d["company"] for d in docs}
        results = payroll.compute_all(plan, load_pages, million_by_no(million),       # each with its company's settings
                                      [payroll.employee_company(e, company_of_doc) for e in plan["employees"]],
                                      plans.load_layouts())
        for r in results:
            n = (gone or {}).get(r["id"])
            if n:
                r["issues"].insert(0, {"kind": "removed", "job": None, "text": (
                    f"{n} time-card file{'s' if n > 1 else ''} chosen before "
                    f"{'are' if n > 1 else 'is'} no longer in Recent files, so "
                    f"{'they were' if n > 1 else 'it was'} taken off this employee.")})
        for r, e in zip(results, plan["employees"]):
            labels: list[str] = []
            for job_id in e["jobs"]:
                if job_id in cache:
                    for page in cache[job_id][1]:
                        labels += [c for c in page["column_labels"] if c not in labels]
            r["columns"] = labels
        return {"plan": plan, "documents": docs, "results": results, "million": million,
                "fields": [{"key": k, "label": label, "unit": unit} for k, label, unit in payroll.FIELDS],
                "list_heads": {kind: {"title": title, "type": type_head} for kind, (title, type_head, _) in payroll.LISTS.items()}}

    def new_numbers(plan: dict, docs: list[dict], only: set[str] | None = None) -> dict[str, str]:
        """{employee id: a new Employee No.} for employees without one (``only``: among these), from the company's name
        (payroll.new_employee_nos). Not for an employee Million's list has a number to offer for."""
        million = (plans.load_million() or {}).get("employees") or []
        offered = payroll.suggest_employee_nos(plan, million) if million else {}
        company_of_doc = {d["id"]: d["company"] for d in docs}
        companies = {e["id"]: payroll.employee_company(e, company_of_doc) for e in plan["employees"]
                     if e["id"] not in offered and (only is None or e["id"] in only)}
        return payroll.new_employee_nos(plan, companies, plans.used_employee_nos() | {m["emp_no"] for m in million})

    def number_new_employees(plan: dict, docs: list[dict], before: set[str]) -> int:
        """Employees just made from the files (not in ``before``) who are still without an Employee No. get a new one,
        marked ``emp_no_new``. The numbers are remembered at once, so another month never gives them to someone else.
        Returns how many."""
        new = new_numbers(plan, docs, {e["id"] for e in plan["employees"]} - before)
        for e in plan["employees"]:
            if e["id"] in new:
                e["emp_no"] = e["emp_no_new"] = new[e["id"]]
        directory = plans.load_directory()
        if payroll.remember_employees(plan, directory):
            plans.save_directory(directory)
        return len(new)

    def candidates_of(d: dict) -> list[dict]:
        """What "Add employees from files" chooses from in one finished document: the document, or its parts."""
        pages = merged_pages(store.load_result(d["id"]), store.load_edits(d["id"]))
        if d["parts"]:
            return [{"ref": p["ref"], "name": part_name(d["name"], p["page"], p["row"], len(pages)),
                     "company": d["company"], "pages": part_pages(pages, p["page"], p["row"])} for p in d["parts"]]
        return [{"ref": d["id"], "name": d["name"], "company": d["company"], "pages": pages}]

    # Files read from now on go into their month's payroll by themselves, once each, when that month's Payroll page is
    # opened (never while the page is open: it keeps its own copy of the plan and would save over a change made here).
    # The month is what the file name or the card prints (payroll.document_month). Files read before this existed are
    # left as they are. A file taken off an employee is not added again.
    auto_index_path = plans.root / "added-by-themselves.json"
    auto_lock = threading.Lock()

    def read_auto_index() -> dict | None:
        try:
            index = _read_json(auto_index_path) if auto_index_path.exists() else None
        except (OSError, ValueError):
            index = None
        return index if isinstance(index, dict) else None

    if read_auto_index() is None:                       # first start with this: the files already here stay as they are
        try:
            plans.root.mkdir(parents=True, exist_ok=True)
            _write_json(auto_index_path, {j["id"]: "before" for j in store.list_jobs()})
        except Exception:  # noqa: BLE001 - never stops the app starting; nothing is added until the list exists
            log.exception("The list of files added to a payroll could not be written")

    def month_of(d: dict, pages: list[dict], chosen: dict[str, str]) -> tuple[str | None, str]:
        """The payroll month of a finished document: the one the user chose for it, else what it prints
        (payroll.document_month). (None, why) when there is none; "none" chosen = not a time card."""
        if chosen.get(d["id"]) == "none":
            return None, "not a time card"
        if chosen.get(d["id"]):
            return chosen[d["id"]], ""
        return payroll.document_month(d["name"], pages, date.fromisoformat(d["created"][:10]))

    def add_new_documents(plan: dict, docs: list[dict]) -> dict | None:
        index = read_auto_index()
        if index is None:
            return None
        chosen = plans.load_file_months()
        taken = {payroll.split_ref(r)[0] for e in plan["employees"] for r in e["jobs"]}
        mine, no_month, marked = [], [], False
        for d in docs:
            if d["id"] in index:
                continue
            if d["id"] in taken:                                    # ticked by hand for this month: done
                index[d["id"]] = plan["month"]
                marked = True
                continue
            try:
                pages = merged_pages(store.load_result(d["id"]), store.load_edits(d["id"]))
                month, why = month_of(d, pages, chosen)
            except (OcrError, OSError, ValueError):
                continue
            if month == plan["month"]:
                mine.append(d)
            elif month is None and chosen.get(d["id"]) != "none":
                no_month.append({"name": d["name"], "why": why})
        info = {"added": [], "joined": [], "skipped": [], "unnamed": [], "no_month": no_month, "from_million": 0,
                "new_numbers": 0}
        if mine:
            before = {e["id"]: len(e["jobs"]) for e in plan["employees"]}
            linked = [{"ref": r, "name": d["name"], "company": d["company"], "pages": []}
                      for d in docs if d["id"] in taken for r in [d["id"]] + [p["ref"] for p in d["parts"]]]
            new = [c for d in mine for c in candidates_of(d)]
            _, info["skipped"], info["unnamed"] = payroll.auto_employees(
                plan, linked + new, plans.load_directory(), lambda: "e" + uuid.uuid4().hex[:12], {c["ref"] for c in new},
                (plans.load_million() or {}).get("employees"))
            for e in plan["employees"]:
                grown = len(e["jobs"]) - before.get(e["id"], 0)
                if grown > 0:
                    info["added" if e["id"] not in before else "joined"].append({"name": e["name"], "cards": grown})
            info["from_million"] = sum(1 for e in plan["employees"] if e["id"] not in before and e.get("emp_no_million"))
            info["new_numbers"] = number_new_employees(plan, docs, set(before))
            plans.save(payroll.validate_plan(plan, known_refs(docs)))
            for d in mine:
                index[d["id"]] = plan["month"]
        if mine or marked:
            _write_json(auto_index_path, index)
        return info if any(info.values()) else None

    def open_month(month: str) -> tuple[dict, list[dict], dict, dict | None, int]:
        """What opening a month does, once, under the lock: cards that are gone are taken off, newly read files of
        the month join it, and everyone still without an Employee No. gets a new one. Returns (plan, documents,
        cards taken off per employee, what joined by itself, how many numbers were made)."""
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            gone = drop_gone_documents(plan, known_refs(docs))
            try:
                payroll.validate_plan(plan, known_refs(docs))
            except OcrError:
                # A plan that cannot be saved as it is (old data, for example one card on two employees) is left
                # alone: nothing joins it and nobody is numbered until the user has put it right (employee view).
                return plan, docs, gone, None, 0
            if gone:
                plans.save(payroll.validate_plan(plan, known_refs(docs)))
            added = add_new_documents(plan, docs)
            # everyone still without an Employee No. gets a new one here too (the user's rule: no number, make one),
            # also employees who were in the payroll before; like the files above, only when the page is opened
            numbered = number_new_employees(plan, docs, set())
            if numbered:
                plans.save(payroll.validate_plan(plan, known_refs(docs)))
        return plan, docs, gone, added, numbered

    # ------------------------------------------------------------------------------------- payroll by company
    def month_state(month: str) -> dict:
        """The month opened (open_month) and worked out once, for step 3 (people) and step 2 (files)."""
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
                "added": added, "numbered": numbered, **dict(zip(("files", "other", "months"), file_items(plan, docs, month))),
                "layouts": layout_items(plan, docs, company_of)}

    def layout_items(plan: dict, docs: list[dict], company_of: list[str]) -> dict[str, list[dict]]:
        """{company: "card layout" items} from the cards on its employees (companies.unknown_layouts). A grid row is
        read by the grid's own rules and is left out; a card that cannot be opened is left out."""
        names, pages_of, cards = {d["id"]: d["name"] for d in docs}, {}, {}
        for e, company in zip(plan["employees"], company_of):
            for ref in e["jobs"]:
                doc, page, row = payroll.split_part(ref)
                if row is not None:
                    continue
                if doc not in pages_of:
                    try:
                        pages_of[doc] = merged_pages(store.load_result(doc), store.load_edits(doc))
                    except (OcrError, OSError, ValueError):
                        pages_of[doc] = []
                cards.setdefault(company, []).extend(
                    {"doc": doc, "name": names.get(doc, ""), "page": p, "hours_column": e.get("hours_column")}
                    for p in pages_of[doc] if page is None or p["page"] == page)
        saved = plans.load_layouts()
        return {company: companies.unknown_layouts(found, saved) for company, found in cards.items()}

    def file_items(plan: dict, docs: list[dict], month: str) -> tuple[dict[str, list[dict]], dict[str, list[dict]],
                                                                       dict[str, str | None]]:
        """{company: items} for the finished files that need the user in ``month``: a card of the month that is on no
        employee ("unplaced"), and a file with no month that is on no employee in any month ("month").
        Also {company: other files}, on no employee in ``month``: set aside as "not a time card" ("month": "none"), or
        read as another month and on no employee there. They do not need the user (not items); step 2 shows
        them on the file, so a mistaken "Not a time card" or a month read wrongly can be put right.
        Also {file id: its month} (None when it has none) for every finished file with a company."""
        chosen, index = plans.load_file_months(), read_auto_index() or {}
        out: dict[str, list[dict]] = {}
        other: dict[str, list[dict]] = {}
        months: dict[str, str | None] = {}
        taken_in: dict[str, set[str]] = {}                          # month -> documents on its employees
        for d in docs:
            if not d["company"]:
                continue                                            # first it needs a company (asked on its own)
            try:
                pages = merged_pages(store.load_result(d["id"]), store.load_edits(d["id"]))
                found, why = month_of(d, pages, chosen)
                cards = companies.unplaced(plan, candidates_of(d))
            except (OcrError, OSError, ValueError):
                continue                                            # a reading that cannot be loaded is not an item
            months[d["id"]] = found
            if chosen.get(d["id"]) == "none" or (found not in (None, month) and cards):
                if found is not None and found not in taken_in:
                    taken_in[found] = {payroll.split_part(r)[0] for e in plans.load(found)["employees"] for r in e["jobs"]}
                if cards and (found is None or d["id"] not in taken_in[found]):
                    other.setdefault(d["company"], []).append({"doc": d["id"], "name": d["name"], "month": found or "none"})
                continue
            if found is None and index.get(d["id"]) not in (None, "before"):
                continue                                            # ticked by hand for some month: answered already
            if found == month:
                out.setdefault(d["company"], []).extend(
                    {"kind": "unplaced", "ref": c["ref"], "name": c["name"], "doc": d["id"],
                     "readable": any(payroll.readable(p) for p in c["pages"] if p["rows"])} for c in cards)
            elif found is None and chosen.get(d["id"]) != "none" and cards:
                out.setdefault(d["company"], []).append({"kind": "month", "doc": d["id"], "name": d["name"], "why": why})
        return out, other, months

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
        cards are on, the employees of each company (for "whose card is this?"), how many things step 3 has, and what
        opening the month did by itself (as GET .../people says it)."""
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
                "needs": sum(v["needs"] for v in views),
                # opening the month here (step 2 usually does it first): what joined by itself, for step 3 to say
                "added_by_themselves": state["added"], "numbered": state["numbered"]}

    @app.post("/api/payroll/{month}/place")
    async def place_card(month: str, request: Request):
        """Put a card on an employee of the month, or on a new employee ("employee": null). "move": true takes it off
        the employee who has it first ("from": the employee the screen showed it on, see take_off_card); without it, a
        card that is on someone else is refused."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not isinstance(body.get("ref"), str) or "employee" not in body \
                or not (body["employee"] is None or isinstance(body["employee"], str)) \
                or not isinstance(body.get("move", False), bool) \
                or not (body.get("from") is None or isinstance(body["from"], str)):
            raise OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            drop_gone_documents(plan, known_refs(docs))
            doc = next((d for d in docs if d["id"] == payroll.split_part(body["ref"])[0]), None)
            try:                                        # only this card's document is opened, not every reading
                candidate = next((c for c in candidates_of(doc) if c["ref"] == body["ref"]), None) if doc else None
            except (OSError, ValueError) as exc:
                raise OcrError("JOB_NOT_FOUND", "That card could not be opened. Read the file again.") from exc
            if candidate is None:
                raise OcrError("JOB_NOT_FOUND", "That card was not found. It may have been moved or deleted.")
            before = {e["id"] for e in plan["employees"]}
            if body.get("move"):                        # "Move to ..." in the employee view: off its employee first
                payroll.take_off_card(plan, body["ref"], body.get("from"))
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
            payroll.days_in(body["month"])                               # OcrError when it is not a month
        if body["id"] not in {d["id"] for d in finished_documents()}:
            raise OcrError("JOB_NOT_FOUND", "That file was not found. It may have been moved or deleted.")
        with auto_lock:
            months = plans.load_file_months()
            months[body["id"]] = body["month"]
            plans.save_file_months(months)
        return {"ok": True}

    @app.get("/api/payroll/{month}/look")
    def look_panel(month: str, employee: str = ""):
        """The one-look panel of one employee: each of their cards with the lines the calculation could not use, and
        every cell it read there as it is now. Accepting goes through PUT /api/jobs/{id}/cells ("via": "look").
        Changes nothing: the month was opened by step 3, where this comes from."""
        plan = plans.load(month)
        person = next((e for e in plan["employees"] if e["id"] == employee), None)
        if person is None:
            raise OcrError("EMPLOYEE_NOT_FOUND", payroll.EMPLOYEE_GONE)
        files = {j["id"]: j for j in store.list_jobs()}
        company = payroll.employee_company(person, {i: j["company"] for i, j in files.items()})
        load_pages, _ = page_loader()
        [result] = payroll.compute_all({**plan, "employees": [person]}, load_pages, million_by_no(plans.load_million()),
                                       [company], plans.load_layouts())
        pages = {}
        for doc in {i["at"]["doc"] for i in result["issues"] if "at" in i}:
            try:
                pages[doc] = merged_pages(store.load_result(doc), store.load_edits(doc))
            except (OcrError, OSError, ValueError):
                continue                                # changed or damaged since: that card is left out
        return {"month": month, "employee": person["id"], "name": person["name"], "company": company,
                "cards": companies.look_cards(result, person, pages, {i: j["name"] for i, j in files.items()})}

    # ----------------------------------------------------------------------------- card layouts (layout maps)
    def layout_page(doc: str, page: int) -> tuple[dict, str]:
        """One page of a finished card, as read and corrected, and the file's name."""
        try:
            name = store.get_job(doc)["name"]
            pages = merged_pages(store.load_result(doc), store.load_edits(doc))
        except (OcrError, OSError, ValueError) as exc:
            raise OcrError("JOB_NOT_FOUND", "That card could not be opened. Read the file again.") from exc
        found = next((p for p in pages if p["page"] == page), None)
        if found is None:
            raise OcrError("PAGE_NOT_FOUND", "That page of the card was not found.")
        return found, name

    def chosen_hours(labels: list[str], hours: str | None) -> str | None:
        if hours is not None and hours not in labels:
            raise OcrError("BAD_LAYOUT", "What the columns mean could not be understood. Open the card layout again.")
        return hours

    @app.get("/api/layouts")
    def get_layout(doc: str, page: int, ask: bool = False, hours: str | None = None):
        """What the columns of a card's layout mean: the map the user saved, today's reading as a map, and the value
        shapes Claude would see. ``ask``: Claude's suggestion too (only when nothing is saved; never by just
        opening)."""
        p, name = layout_page(doc, page)
        labels = p["column_labels"]
        saved = (plans.load_layouts().get(payroll.layout_signature(labels)) or {}).get("columns")
        suggestion = error = as_read = None
        if ask and saved is None:
            try:
                suggestion = layouts.suggest(p)
            except OcrError as exc:
                error = exc.message
        try:
            as_read = payroll.map_as_read(labels, chosen_hours(labels, hours))
        except OcrError:
            pass
        return {"doc": doc, "page": page, "name": name, "labels": labels, "shapes": layouts.shapes(p), "saved": saved,
                "suggestion": suggestion, "error": error, "as_read": as_read, "roles": list(payroll.LAYOUT_ROLES),
                "units": list(payroll.LAYOUT_UNITS)}

    @app.put("/api/layouts")
    async def save_layout(request: Request):
        """The user confirms what a card layout's columns mean ("columns"), or that today's reading is right and the
        other columns are not used ("as_is"). Kept for every card with the same headings (payroll.layout_signature)."""
        body = await settings_body(request)
        if not isinstance(body.get("doc"), str) or not isinstance(body.get("page"), int):
            raise OcrError("BAD_LAYOUT", "What the columns mean could not be understood. Open the card layout again.")
        p, _ = layout_page(body["doc"], body["page"])
        labels = p["column_labels"]
        hours = body.get("hours_column") if isinstance(body.get("hours_column"), str) else None
        columns = payroll.map_as_read(labels, chosen_hours(labels, hours)) if body.get("as_is") is True \
            else payroll.valid_layout_map(labels, body.get("columns"))
        with auto_lock:
            saved = plans.load_layouts()
            saved[payroll.layout_signature(labels)] = {"columns": columns, "confirmed": date.today().isoformat()}
            plans.save_layouts(saved)
        return {"ok": True}

    async def settings_body(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")
        return body

    def change_plan(month: str, change: Callable[[dict], None]) -> dict:
        """Change the month's plan under the lock and save it, checked as every plan is (validate_plan)."""
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            drop_gone_documents(plan, known_refs(docs))
            change(plan)
            plans.save(payroll.validate_plan(plan, known_refs(docs)))
        return {"ok": True}

    @app.put("/api/payroll/{month}/settings")
    async def save_month_settings(month: str, request: Request):
        """The month's default: normal hours, break and calendar (companies with their own settings keep theirs)."""
        body = await settings_body(request)
        return change_plan(month, lambda plan: plan.update({k: body.get(k) for k in payroll.SETTING_KEYS}))

    @app.put("/api/payroll/{month}/company-settings")
    async def save_company_settings(month: str, request: Request):
        """A company follows the month's default ("own": false), or has its own complete set ("own": true; values
        not given are copied from the default, "keep" = start next month with it)."""
        body = await settings_body(request)
        company = " ".join(body["company"].split()) if isinstance(body.get("company"), str) else ""
        if not company:
            raise OcrError("BAD_PAYROLL", "Choose the company first.")

        def change(plan: dict) -> None:
            own = dict(plan.get("companies") or {})
            own.pop(company, None)
            if body.get("own") is True:
                own[company] = payroll.own_settings(plan, {k: body[k] for k in (*payroll.SETTING_KEYS, "keep") if k in body})
            plan["companies"] = own

        return change_plan(month, change)

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

    # ------------------------------------------------------------------- one employee (the employee view)
    def employee_view(month: str, plan: dict, employee_id: str) -> dict:
        """One employee as the employee view shows them: the saved entry, their figures (with their company's
        settings), their cards, the same company's other employees, and what the Results window needs."""
        person = next((e for e in plan["employees"] if e["id"] == employee_id), None)
        if person is None:
            raise OcrError("EMPLOYEE_NOT_FOUND", payroll.EMPLOYEE_GONE)
        files = {j["id"]: j for j in store.list_jobs()}
        company_of_doc = {i: j["company"] for i, j in files.items()}
        company = payroll.employee_company(person, company_of_doc)
        load_pages, cache = page_loader()
        million, saved_layouts = plans.load_million(), plans.load_layouts()
        [result] = payroll.compute_all({**plan, "employees": [person]}, load_pages, million_by_no(million), [company],
                                       saved_layouts)
        labels: list[str] = []
        cards = []
        for ref in person["jobs"]:
            doc = payroll.split_part(ref)[0]
            name, pages = cache.get(ref, ((files.get(doc) or {}).get("name", ""), []))
            for page in pages:
                labels += [c for c in page["column_labels"] if c not in labels]
            # a confirmed layout map says itself which column holds the hours: the Hours column list does not apply
            cards.append({"ref": ref, "doc": doc, "name": name,
                          "mapped": any(payroll.has_layout_map(p["column_labels"], saved_layouts) for p in pages)})
        result["columns"] = labels
        others = [{"id": e["id"], "emp_no": e["emp_no"], "name": e["name"]} for e in plan["employees"]
                  if e["id"] != person["id"] and payroll.employee_company(e, company_of_doc) == company]
        return {"month": month, "employee": person, "result": result, "company": company, "cards": cards,
                "others": others, "lists": plan["lists"],
                "fields": [{"key": k, "label": label, "unit": unit} for k, label, unit in payroll.FIELDS],
                "list_heads": {kind: {"title": title, "type": type_head}
                               for kind, (title, type_head, _) in payroll.LISTS.items()},
                "million": [{"emp_no": e["emp_no"], "name": e["name"]} for e in million["employees"]] if million else None}

    def addable_cards(plan: dict, person: dict, company: str) -> list[dict]:
        """What "Add a time card" offers on an employee: every card (a file, or its page / grid row when it shows several
        workers) of the finished files of the employee's company that is not on this employee, with the month it is
        for ("none" = set aside as not a time card, None = no month) and who has it now in this month (None = nobody).
        A whole file counts as someone's when one of its parts is, and a part when its file or its page is (as
        companies.unplaced counts them)."""
        chosen = plans.load_file_months()

        def holder(ref: str) -> dict | None:
            base, page, row = payroll.split_part(ref)
            for e in plan["employees"]:
                for job in e["jobs"]:
                    j_base, j_page, j_row = payroll.split_part(job)
                    if job == ref or (j_base == base and (ref == base or job == base
                                                          or (row is not None and j_page == page and j_row is None))):
                        return e
            return None

        out = []
        for d in finished_documents():
            if d["company"] != company:
                continue
            try:
                pages = merged_pages(store.load_result(d["id"]), store.load_edits(d["id"]))
                found, _ = month_of(d, pages, chosen)
                cards = candidates_of(d)
            except (OcrError, OSError, ValueError):
                continue                                            # a reading that cannot be opened is not offered
            for c in cards:
                who = holder(c["ref"])
                if who is person:
                    continue
                out.append({"ref": c["ref"], "doc": d["id"], "name": c["name"],
                            "month": "none" if chosen.get(d["id"]) == "none" else found,
                            "on": {"id": who["id"], "name": who["name"]} if who else None})
        return out

    def bad_body() -> OcrError:
        return OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")

    @app.get("/api/payroll/{month}/employee/{employee_id}")
    def get_employee(month: str, employee_id: str):
        """The employee view. Reads the plan as saved; changes nothing (the month was opened by step 3). Also what
        "Add a time card" offers (only here: the changes below answer without it, the page keeps the last list)."""
        plan = plans.load(month)
        view = employee_view(month, plan, employee_id)
        return {**view, "addable": addable_cards(plan, view["employee"], view["company"])}

    @app.put("/api/payroll/{month}/employee/{employee_id}")
    async def change_employee(month: str, employee_id: str, request: Request):
        """Change only the keys sent ({"changes": {key: value}}), so a view opened before another tab changed
        something else on this employee does not undo it."""
        body = await settings_body(request)
        changes = body.get("changes")
        if not isinstance(changes, dict):
            raise bad_body()
        with auto_lock:                                             # as change_plan, and the number remembered with it
            plan, docs = plans.load(month), finished_documents()
            drop_gone_documents(plan, known_refs(docs))
            payroll.change_employee(plan, employee_id, changes)
            plan = payroll.validate_plan(plan, known_refs(docs))
            plans.save(plan)
            if "emp_no" in changes or "name" in changes:            # Employee No. typed: kept for next month
                directory = plans.load_directory()
                if payroll.remember_employees(plan, directory):
                    plans.save_directory(directory)
        return employee_view(month, plan, employee_id)

    @app.delete("/api/payroll/{month}/employee/{employee_id}")
    def delete_employee(month: str, employee_id: str):
        return change_plan(month, lambda plan: payroll.remove_employee(plan, employee_id))

    @app.post("/api/payroll/{month}/employee")
    async def add_employee(month: str, request: Request):
        """An employee typed in by hand; in a company, with a new Employee No. made from the company's name."""
        body = await settings_body(request)
        if not isinstance(body.get("company"), str):
            raise bad_body()
        company = " ".join(body["company"].split())
        new_id = "e" + uuid.uuid4().hex[:12]
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            drop_gone_documents(plan, known_refs(docs))
            before = {e["id"] for e in plan["employees"]}
            payroll.add_employee(plan, new_id, company)
            payroll.validate_plan(plan, known_refs(docs))
            if company:
                number_new_employees(plan, docs, before)
            plans.save(payroll.validate_plan(plan, known_refs(docs)))
        return {"employee": new_id}

    @app.post("/api/payroll/{month}/take-off")
    async def take_off(month: str, request: Request):
        """Take a card off its employee: it is a "whose card is this?" item again."""
        body = await settings_body(request)
        if not isinstance(body.get("ref"), str) or not (body.get("from") is None or isinstance(body["from"], str)):
            raise bad_body()

        def change(plan: dict) -> None:                             # "from": the employee the screen showed it on
            if payroll.take_off_card(plan, body["ref"], body.get("from")) is None:
                raise OcrError("BAD_PAYROLL", "That card is not on any employee any more. Reload the page.")

        return change_plan(month, change)

    @app.put("/api/payroll/{month}/lists")
    async def save_lists(month: str, request: Request):
        """One allowance, deduction, benefit or leave line added ({"kind", "add": {"name", "type"}}) or removed
        ({"kind", "remove": name}); the other lines stay as saved (payroll.change_list)."""
        body = await settings_body(request)
        add, remove = body.get("add"), body.get("remove")
        if not isinstance(body.get("kind"), str) or (add is None) == (remove is None) \
                or not (add is None or isinstance(add, dict)) or not (remove is None or isinstance(remove, str)):
            raise bad_body()
        return change_plan(month, lambda plan: payroll.change_list(plan, body["kind"], add, remove))

    @app.get("/api/payroll/{month}/pay")
    def pay_table(month: str, company: str = ""):
        """The company's pay preview: per employee the pay basis and Basic Rate (typed, or from Million's list) and
        the basic pay they give."""
        try:
            plan, results = payroll_of(month, company)
        except OcrError as exc:
            if exc.code != "PAYROLL_EMPTY":
                raise
            return {"rows": []}
        return {"rows": [{"id": e["id"], "emp_no": e["emp_no"], "name": e["name"], "typed_basis": e["pay_basis"],
                          "typed_rate": e["basic_rate"], "rate_source": r["rate_source"], "pay_basis": r["pay_basis"],
                          "basic_rate": r["basic_rate"], "pay": r["pay"],
                          "days_worked": r["values"]["days_worked"]["value"], "complete": r["complete"]}
                         for e, r in zip(plan["employees"], results)]}

    def payroll_of(month: str, company: str) -> tuple[dict, list[dict]]:
        """The month's plan and results; with ``company`` only that company's employees (chosen at the top of the page)."""
        docs = finished_documents()
        view = payroll_view(plans.load(month), docs)
        plan, results = view["plan"], view["results"]
        if company:
            company_of_doc = {d["id"]: d["company"] for d in docs}
            keep = [i for i, e in enumerate(plan["employees"]) if payroll.employee_company(e, company_of_doc) == company]
            plan = {**plan, "employees": [plan["employees"][i] for i in keep]}
            results = [results[i] for i in keep]
        if not plan["employees"]:
            raise OcrError("PAYROLL_EMPTY", "Add at least one employee before downloading the payroll file.")
        return plan, results

    def save_payroll_file(name: str, data: bytes) -> Path:
        plans.root.mkdir(parents=True, exist_ok=True)
        path = plans.root / name
        try:
            path.write_bytes(data)
        except OSError as exc:
            raise OcrError("SAVE_FAILED", f"{name} could not be saved. If it is open in Excel, close it and try "
                                          "again.") from exc
        return path

    @app.get("/api/payroll/{month}/csv")
    def payroll_csv(month: str, company: str = ""):
        """The payroll file (CSV, all Edit Payroll figures); with ``company`` only that company's employees."""
        plan, results = payroll_of(month, company)
        text = payroll.build_csv(plan, results)
        path = save_payroll_file(f"Payroll {month} {safe_name(company)}.csv" if company else f"Payroll {month}.csv",
                                 text.encode("utf-8-sig"))
        return FileResponse(path, media_type="text/csv; charset=utf-8", filename=path.name)

    @app.get("/api/payroll/{month}/export")
    def payroll_export(month: str, format: str = "csv", split: str = "one", c: list[str] | None = Query(None)):
        """Export...: the payroll table (all Edit Payroll figures) as CSV or Excel .xls, of the chosen companies (``c``;
        none = every company, "" = the employees with no company), in one file or one per company (``split`` "each",
        several companies: one .zip). A copy is kept in the payroll folder, as the CSV always was."""
        import zipfile

        if format not in ("csv", "xls"):
            raise bad_body()
        chosen = chosen_of(c, split)
        docs = finished_documents()
        view = payroll_view(plans.load(month), docs)
        plan, results = view["plan"], view["results"]
        company_of_doc = {d["id"]: d["company"] for d in docs}
        companies = [payroll.employee_company(e, company_of_doc) for e in plan["employees"]]
        keep = [i for i, company in enumerate(companies) if chosen is None or company in chosen]
        if not keep:
            raise OcrError("PAYROLL_EMPTY", "Nobody of the chosen companies is in this month's payroll yet."
                           if chosen is not None else "Add at least one employee before downloading the payroll file.")

        def data_of(indexes: list[int]) -> bytes:
            part = {**plan, "employees": [plan["employees"][i] for i in indexes]}
            rows = [results[i] for i in indexes]
            return payroll.build_csv(part, rows).encode("utf-8-sig") if format == "csv" else payroll.build_table_xls(part, rows)

        groups: dict[str, list[int]] = {}
        for i in keep:
            groups.setdefault(companies[i], []).append(i)
        media = "text/csv; charset=utf-8" if format == "csv" else "application/vnd.ms-excel"
        if split == "one" or len(groups) == 1:
            name = group_name(month, sorted(groups, key=str.casefold), chosen is None) + f".{format}"
            path = save_payroll_file(name, data_of(keep))
            return FileResponse(path, media_type=media, filename=path.name)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for company in sorted(groups, key=str.casefold):
                z.writestr(group_name(month, [company], False) + f".{format}", data_of(groups[company]))
        path = save_payroll_file(group_name(month, list(groups), chosen is None) + ".zip", buffer.getvalue())
        return FileResponse(path, media_type="application/zip", filename=path.name)

    @app.get("/api/payroll/{month}/basic-pay")
    def payroll_basic_pay(month: str, company: str = ""):
        """The basic-pay table (CSV): each employee's counts, pay basis, Basic Rate and basic pay."""
        plan, results = payroll_of(month, company)
        company_of_doc = {d["id"]: d["company"] for d in finished_documents()}
        text = payroll.build_basic_pay_csv(results, [payroll.employee_company(e, company_of_doc) for e in plan["employees"]])
        path = save_payroll_file(f"Basic pay {month} {safe_name(company)}.csv" if company else f"Basic pay {month}.csv",
                                 text.encode("utf-8-sig"))
        return FileResponse(path, media_type="text/csv; charset=utf-8", filename=path.name)

    def chosen_of(c: list[str] | None, split: str) -> set[str] | None:
        """The companies of an export (None = every company; "" = the employees with no company), and its split."""
        if split not in ("one", "each"):
            raise bad_body()
        return None if c is None else set(c)

    def group_name(month: str, groups: list[str], every: bool) -> str:
        """The name part of an export file: the month, then the company (one), "(N companies)" (several) or nothing
        (every company)."""
        if every:
            return f"Payroll {month}"
        if len(groups) == 1:
            return f"Payroll {month} {safe_name(groups[0]) or 'no company'}"
        return f"Payroll {month} ({len(groups)} companies)"

    def month_file(month: str, make: bool, chosen: set[str] | None = None, split: str = "one") -> dict:
        """The Million file of the month with everyone who can go in; the others are listed by company with the reason
        (payroll.month_run, worked out over the whole month so an Employee No. used twice is seen across companies).
        ``chosen``: only these companies (None = every company); ``split`` "each" = one file per company. ``make``
        False = the summary shown first: worked out the same way, nothing written ("files" []). Making it works
        everything out again; it never relies on a summary."""
        docs = finished_documents()
        view = payroll_view(plans.load(month), docs)
        plan, results = view["plan"], view["results"]
        if not plan["employees"]:
            raise OcrError("PAYROLL_EMPTY", "Add at least one employee before downloading the payroll file.")
        company_of_doc = {d["id"]: d["company"] for d in docs}
        companies = [payroll.employee_company(e, company_of_doc) for e in plan["employees"]]
        listed = plans.load_million()
        names = {e["emp_no"].casefold(): e["name"] for e in listed["employees"]} if listed else None
        known = set(names) if names else payroll.load_million_employees()
        run = payroll.month_run(plan, results, companies, names=names, known=known)
        if chosen is not None:
            if not any(company in chosen for company in companies):
                raise OcrError("PAYROLL_EMPTY", "Nobody of the chosen companies is in this month's payroll yet.")
            run = {**run, **{kind: [w for w in run[kind] if w["company"] in chosen] for kind in ("ready", "held")}}
        files = []
        if make and run["ready"]:
            by_id = {r["id"]: r for r in results}
            groups: dict[str, list[dict]] = {}
            for who in run["ready"]:
                groups.setdefault(who["company"] if split == "each" else "", []).append(by_id[who["id"]])
            for company, people in sorted(groups.items(), key=lambda g: g[0].casefold()):
                names_of = sorted({w["company"] for w in run["ready"]}) if split == "one" else [company]
                data = payroll.build_xls(plan, people, known=known, names=names)
                name = group_name(month, names_of, chosen is None and split == "one") + " (Million).xls"
                files.append(save_payroll_file(name, data).name)
        by_company: dict[str, dict] = {}
        for kind in ("ready", "held"):
            for who in run[kind]:
                entry = by_company.setdefault(who["company"], {"company": who["company"], "ready": 0,
                                                               "ready_people": [], "held": []})
                if kind == "ready":
                    entry["ready"] += 1
                    entry["ready_people"].append({"emp_no": who["emp_no"], "name": who["name"]})
                else:
                    entry["held"].append({"emp_no": who["emp_no"], "name": who["name"], "reasons": who["reasons"]})
        return {"file": files[0] if files else None, "files": files, "made": make, "every": chosen is None,
                "folder": str(plans.root), "ready": len(run["ready"]),
                "held": len(run["held"]), "checked_with_million": bool(listed),
                "companies": sorted(by_company.values(), key=lambda c: (c["company"] == "", c["company"].casefold()))}

    @app.get("/api/payroll/{month}/run")
    def payroll_month_summary(month: str, split: str = "one", c: list[str] | None = Query(None)):
        """What the month's Million file would hold, shown before it is made (``c``: only these companies)."""
        return month_file(month, make=False, chosen=chosen_of(c, split), split=split)

    @app.post("/api/payroll/{month}/run")
    def payroll_month_run(month: str, split: str = "one", c: list[str] | None = Query(None)):
        """Make the Million file: of the chosen companies (``c``; none = every company), one file or one per company
        (``split`` "each"), saved in the payroll folder."""
        return month_file(month, make=True, chosen=chosen_of(c, split), split=split)

    # ------------------------------------------------------------------------------- the Inbox and Tables folders
    watcher = Inbox(store)
    app.state.inbox = watcher
    FOLDERS = {"inbox": watcher.folder, "tables": watcher.tables, "payroll": plans.root}

    @app.get("/api/folders")
    def folders():
        """Where files are taken in by themselves, and where every finished table is kept as a CSV."""
        return {name: str(path) for name, path in FOLDERS.items()}

    @app.post("/api/folders/{name}/open")
    def open_folder(name: str):
        """Show the folder in Windows Explorer (it is made first if it is not there yet)."""
        if name not in FOLDERS:
            raise OcrError("NOT_FOUND", "That folder is not one of Table Reader's.")
        FOLDERS[name].mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(FOLDERS[name])                             # noqa: S606 - a folder of the app's own, on this PC
        except (OSError, AttributeError) as exc:
            raise OcrError("FOLDER_NOT_OPENED", f"The folder could not be opened. Open it yourself: {FOLDERS[name]}") from exc
        return {"opened": str(FOLDERS[name])}

    @app.post("/api/million/employees")
    def import_million_employees(file: UploadFile = File(...)):
        """Million Payroll's employee list (its Employment Listing saved as Excel): Employee No. and name are kept, to
        offer the Employee Nos. on the Payroll screen and to check them before the Million file is made."""
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise OcrError("MILLION_LIST", "This file is too large to be Million Payroll's employee list.")
        return plans.save_million(payroll.parse_million_employees(content), safe_name(file.filename or "file"))

    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    def page():
        return page_html()

    app.mount("/", StaticFiles(directory=static_dir(), html=True), name="static")
    return app
