"""Table Reader web app: the API over `Jobs` plus the single page in static/. Runs only on this PC (localhost)."""
from __future__ import annotations

import os
import hashlib
import logging
import re
import sys
import threading
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import ocr
import payroll
from inbox import Inbox
from jobs import Jobs, _read_json, _write_json, count_to_check, merged_pages, safe_name
from ocr import OcrError

MAX_UPLOAD_BYTES = 150 * 1024 * 1024
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}          # urlparse().hostname is lower-case and drops the [ ]
_STATUS_FOR_CODE = {"JOB_NOT_FOUND": 404, "PAGE_NOT_FOUND": 404, "JOB_BUSY": 409, "JOB_NOT_FINISHED": 409}


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
        return [{**p, "rows": p["rows"][row - 1:row]} for p in chosen]

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

    def payroll_view(plan: dict, docs: list[dict], gone: dict[str, int] | None = None) -> dict:
        cache: dict[str, tuple[str, list[dict]]] = {}

        def load_pages(ref: str) -> tuple[str, list[dict]]:
            if ref not in cache:
                job_id, page, row = payroll.split_part(ref)
                meta = store.get_job(job_id)
                if meta["status"] != "done":
                    raise OcrError("JOB_NOT_FINISHED", f"{meta['name']} has not been read completely yet.")
                pages = merged_pages(store.load_result(job_id), store.load_edits(job_id))
                if page is None:
                    cache[ref] = (meta["name"], pages)
                else:                                           # one worker's page of a report, or row of a grid
                    cache[ref] = (part_name(meta["name"], page, row, len(pages)), part_pages(pages, page, row))
            return cache[ref]

        million = plans.load_million()
        results = payroll.compute_all(plan, load_pages, {e["emp_no"].casefold(): e for e in million["employees"]} if million else None)
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
        suggestions = payroll.suggest_employee_nos(plan, million["employees"]) if million else {}
        new = new_numbers(plan, docs)
        for r in results:
            r["suggest"] = suggestions.get(r["id"])                 # Million's Employee No. for this name, to offer
            r["assign"] = new.get(r["id"])                          # else a new one (company letters + number), to offer
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

    def add_new_documents(plan: dict, docs: list[dict]) -> dict | None:
        index = read_auto_index()
        if index is None:
            return None
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
                month, why = payroll.document_month(d["name"], pages, date.fromisoformat(d["created"][:10]))
            except (OcrError, OSError, ValueError):
                continue
            if month == plan["month"]:
                mine.append(d)
            elif month is None:
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

    @app.get("/api/payroll/{month}")
    def get_payroll(month: str):
        with auto_lock:
            plan, docs = plans.load(month), finished_documents()
            gone = drop_gone_documents(plan, known_refs(docs))
            if gone:
                plans.save(payroll.validate_plan(plan, known_refs(docs)))
            added = add_new_documents(plan, docs)
        view = payroll_view(plan, docs, gone)
        view["added_by_themselves"] = added
        return view

    @app.put("/api/payroll/{month}")
    async def save_payroll(month: str, request: Request):
        try:
            body = await request.json()
        except ValueError:
            body = None
        gone, docs = {}, finished_documents()
        if isinstance(body, dict):
            body["month"] = month
            gone = drop_gone_documents(body, known_refs(docs))
        plan = payroll.validate_plan(body, known_refs(docs))
        with auto_lock:
            plans.save(plan)
        directory = plans.load_directory()
        if payroll.remember_employees(plan, directory):              # Employee No. typed: kept for next month
            plans.save_directory(directory)
        return payroll_view(plan, docs, gone)

    @app.post("/api/payroll/{month}/auto")
    async def auto_add_employees(month: str, request: Request):
        """One employee per worker found in the finished documents of a company ("" = every company)."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        company = body.get("company") if isinstance(body, dict) else None
        if not isinstance(company, str):
            raise OcrError("BAD_PAYROLL", "The payroll settings could not be understood. Reload the page and try again.")
        plan, docs = plans.load(month), finished_documents()
        drop_gone_documents(plan, known_refs(docs))
        candidates = [c for d in docs if not company or d["company"] == company for c in candidates_of(d)]
        before = {e["id"] for e in plan["employees"]}
        added, skipped, unnamed = payroll.auto_employees(plan, candidates, plans.load_directory(),
                                                         lambda: "e" + uuid.uuid4().hex[:12],
                                                         million=(plans.load_million() or {}).get("employees"))
        new_numbers_made = number_new_employees(plan, docs, before)
        plan = payroll.validate_plan(plan, known_refs(docs))
        plans.save(plan)
        view = payroll_view(plan, docs)
        view["auto"] = {"added": added, "skipped": skipped, "unnamed": unnamed, "new_numbers": new_numbers_made,
                        "from_million": sum(1 for e in plan["employees"] if e["id"] not in before and e.get("emp_no_million"))}
        return view

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

    @app.get("/api/payroll/{month}/basic-pay")
    def payroll_basic_pay(month: str, company: str = ""):
        """The basic-pay table (CSV): each employee's counts, pay basis, Basic Rate and basic pay."""
        plan, results = payroll_of(month, company)
        company_of_doc = {d["id"]: d["company"] for d in finished_documents()}
        text = payroll.build_basic_pay_csv(results, [payroll.employee_company(e, company_of_doc) for e in plan["employees"]])
        path = save_payroll_file(f"Basic pay {month} {safe_name(company)}.csv" if company else f"Basic pay {month}.csv",
                                 text.encode("utf-8-sig"))
        return FileResponse(path, media_type="text/csv; charset=utf-8", filename=path.name)

    @app.get("/api/payroll/{month}/xls")
    def payroll_xls(month: str, company: str = "", allow_incomplete: bool = False, allow_unknown: bool = False,
                    allow_names: bool = False):
        """The Million import file for the office (.xls, the office File Format Setting's columns). Refused, with every
        problem listed, when it would import wrong. Asked about first (``allow_…``): Employee Nos. that are not in
        Million's employee list (the imported one, else employees.txt), employees whose name is another one in
        Million, and INCOMPLETE employees."""
        plan, results = payroll_of(month, company)
        listed = plans.load_million()
        names = {e["emp_no"].casefold(): e["name"] for e in listed["employees"]} if listed else None
        data = payroll.build_xls(plan, results, allow_incomplete=allow_incomplete, allow_unknown=allow_unknown,
                                 known=set(names) if names else payroll.load_million_employees(),
                                 names=names, allow_names=allow_names)
        name = f"Payroll {month} {safe_name(company)} (Million).xls" if company else f"Payroll {month} (Million).xls"
        path = save_payroll_file(name, data)
        return FileResponse(path, media_type="application/vnd.ms-excel", filename=path.name)

    @app.post("/api/payroll/{month}/run")
    def payroll_month_run(month: str):
        """One Million file for the whole month (every company), with everyone who can go in; the others are listed
        by company with the reason. See payroll.month_run."""
        docs = finished_documents()
        view = payroll_view(plans.load(month), docs)
        plan, results = view["plan"], view["results"]
        if not plan["employees"]:
            raise OcrError("PAYROLL_EMPTY", "Add at least one employee before downloading the payroll file.")
        company_of_doc = {d["id"]: d["company"] for d in docs}
        companies = [payroll.employee_company(e, company_of_doc) for e in plan["employees"]]
        listed = plans.load_million()
        names = {e["emp_no"].casefold(): e["name"] for e in listed["employees"]} if listed else None
        run = payroll.month_run(plan, results, companies, names=names,
                                known=set(names) if names else payroll.load_million_employees())
        name = None
        if run["file"] is not None:
            name = save_payroll_file(f"Payroll {month} (Million).xls", run["file"]).name
        by_company: dict[str, dict] = {}
        for kind in ("ready", "held"):
            for who in run[kind]:
                entry = by_company.setdefault(who["company"], {"company": who["company"], "ready": 0, "held": []})
                if kind == "ready":
                    entry["ready"] += 1
                else:
                    entry["held"].append({"emp_no": who["emp_no"], "name": who["name"], "reasons": who["reasons"]})
        return {"file": name, "folder": str(plans.root), "ready": len(run["ready"]), "held": len(run["held"]),
                "checked_with_million": bool(listed),
                "companies": sorted(by_company.values(), key=lambda c: (c["company"] == "", c["company"].casefold()))}

    # ------------------------------------------------------------------------------- the Inbox and Tables folders
    watcher = Inbox(store)
    app.state.inbox = watcher
    FOLDERS = {"inbox": watcher.folder, "tables": watcher.tables}

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
