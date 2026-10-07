"""Table Reader web app: the API over `Jobs` plus the single page in static/. Runs only on this PC (localhost)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import ocr
from jobs import Jobs, count_to_check, merged_pages
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

    app.mount("/", StaticFiles(directory=static_dir(), html=True), name="static")
    return app
