"""Jobs: one folder per uploaded document, background reading with progress, corrections, CSV.

    <root>\\<yyyy-mm-dd_hhmm>_<name>\\
        original\\<file>          the upload, never touched
        pages\\page-N.png         derived page images (turned upright when Claude found them sideways)
        reading\\page-N.json      Claude's reading of each page, written once, never changed (lets a stopped job resume)
        result.json              all pages together, written once when the last page is read; never edited
        edits.json               the user's corrections, kept apart from Claude's reading
        job.json                 status and progress
        <name>.csv               built on request: Claude's reading with the corrections applied on top

Documents are read one at a time (Claude plan limits, and a second click must not read a document twice).
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import queue
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import ocr
import pages
from ocr import OcrError

log = logging.getLogger(__name__)

# Failures that will hit every other waiting document too, so the queue stops instead of repeating them.
STOP_QUEUE_CODES = {"CLAUDE_PLAN_LIMIT", "CLAUDE_LOGIN_REQUIRED", "CLAUDE_CLI_MISSING"}
_CANCELLED = {"code": "CANCELLED", "message": "Reading was cancelled. Pages already read are kept; press Continue to "
                                                 "read the rest."}
MAX_EDIT_LENGTH = 1000
_FORBIDDEN_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def documents_dir() -> Path:
    """The user's real Documents folder (it may be redirected to OneDrive or a network drive)."""
    if os.name == "nt":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:   # 5 = CSIDL_PERSONAL
                return Path(buf.value)
        except Exception:  # noqa: BLE001 - fall back to the usual place
            pass
    return Path.home() / "Documents"


def default_root() -> Path:
    base = os.environ.get("TABLE_READER_HOME")
    return (Path(base) if base else documents_dir() / "Table Reader") / "jobs"


def safe_name(name: str, limit: int = 80) -> str:
    """A file/folder-safe version of a name that keeps Unicode (Malay, Chinese…) letters."""
    name = _FORBIDDEN_NAME_CHARS.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:limit].strip(" .") or "document"


def _norm(text: str) -> str:
    return " ".join((text or "").replace("_", " ").split()).casefold()


def company_for(filename: str, companies: list[str]) -> str:
    """The known company a file name starts with ("MAJU JAYA ALI SEPT 26.pdf" -> "MAJU JAYA"), longest first, or "".
    Only companies the user has already confirmed are matched: a new company is never worked out from the name."""
    name = _norm(Path(filename).stem)
    for c in sorted(companies, key=len, reverse=True):
        if c and (name == _norm(c) or name.startswith(_norm(c) + " ")):
            return c
    return ""


def _write_json(path: Path, data) -> None:
    """Write atomically so a page that polls progress never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:          # Windows: the target is open in another reader for a moment
            if attempt == 5:
                raise
            time.sleep(0.05)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------------- the store
class Jobs:
    def __init__(self, root: str | Path | None = None, reader: Callable[[Path], dict] | None = None):
        self.root = Path(root) if root else default_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._reader = reader or (lambda image: ocr.read_image(image))
        self._lock = threading.RLock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._pending: set[str] = set()          # queued or being read right now
        self._cancels: dict[str, threading.Event] = {}   # set = the user pressed Cancel for this job
        self._current: str | None = None         # the job the worker is reading at this moment
        self._worker: threading.Thread | None = None
        self._recover_interrupted()

    # ------------------------------------------------------------------------------------------- folders
    def _dir(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not job_id or job_id in (".", "..") or _FORBIDDEN_NAME_CHARS.search(job_id):
            raise OcrError("JOB_NOT_FOUND", "That document was not found. It may have been moved or deleted.")
        d = self.root / job_id
        if not (d / "job.json").is_file():
            raise OcrError("JOB_NOT_FOUND", "That document was not found. It may have been moved or deleted.")
        return d

    def _meta(self, job_id: str) -> dict:
        return _read_json(self._dir(job_id) / "job.json")

    def _update(self, job_id: str, **changes) -> dict:
        with self._lock:
            meta = self._meta(job_id)
            meta.update(changes)
            _write_json(self._dir(job_id) / "job.json", meta)
            return meta

    def _recover_interrupted(self) -> None:
        """A job still marked queued/reading when the app starts was cut off (app closed, PC restarted)."""
        for d in self.root.iterdir():
            try:
                meta = _read_json(d / "job.json")
            except (OSError, ValueError):
                continue
            if meta.get("status") in ("queued", "reading"):
                meta.update(status="failed", error={
                    "code": "INTERRUPTED",
                    "message": "Reading stopped before it finished (the app was closed). Press Continue to read the "
                               "rest; pages that were already read are kept."})
                _write_json(d / "job.json", meta)

    # ----------------------------------------------------------------------------------------- create / list
    def create_job(self, filename: str, content: bytes) -> dict:
        """Save an upload as a new job and queue it for reading. Raises OcrError for files that cannot be used."""
        name = filename.replace("\\", "/").split("/")[-1]
        if not pages.is_supported(name):
            raise OcrError("FILE_TYPE", f"{name or 'This file'} is not a PDF or a picture (JPG, PNG). Save or scan "
                           "it as a PDF, JPG or PNG and add it again.")
        if not content:
            raise OcrError("EMPTY_FILE", f"{name} is empty. Check the file and add it again.")
        stem = safe_name(Path(name).stem)
        original_name = f"{stem}{Path(name).suffix.lower()}"
        company = company_for(name, self.companies())
        base = f"{datetime.now():%Y-%m-%d_%H%M}_{stem}"
        with self._lock:
            job_id, n = base, 1
            while True:
                try:
                    (self.root / job_id).mkdir()
                    break
                except FileExistsError:
                    n += 1
                    job_id = f"{base}-{n}"
            d = self.root / job_id
            (d / "original").mkdir()
            (d / "original" / original_name).write_bytes(content)
            meta = {"id": job_id, "name": name, "stem": stem, "company": company,
                    "created": datetime.now().isoformat(timespec="seconds"),
                    "status": "queued", "pages_total": None, "pages_done": 0, "error": None}
            _write_json(d / "job.json", meta)
            self._enqueue(job_id)
        return meta

    def list_jobs(self) -> list[dict]:
        out = []
        for d in self.root.iterdir():
            try:
                out.append(_read_json(d / "job.json"))
            except (OSError, ValueError):
                continue
        for m in out:
            m.setdefault("company", "")                            # files added before companies existed
        return sorted(out, key=lambda m: (m.get("created", ""), m.get("id", "")), reverse=True)

    # ------------------------------------------------------------------------------------------- companies
    def companies(self) -> list[str]:
        """The client companies the user has given to files, each once (whatever the capitals or spaces)."""
        seen: dict[str, str] = {}
        for m in self.list_jobs():
            if m["company"]:
                seen.setdefault(_norm(m["company"]), m["company"])
        return sorted(seen.values(), key=str.casefold)

    def set_company(self, job_id: str, company) -> int:
        """Files this document under ``company`` ("" = none). Files that have no company yet and whose name starts with
        the same company are filed under it too (the user confirmed the company once). Returns how many others moved."""
        if not isinstance(company, str) or len(company) > 80:
            raise OcrError("BAD_COMPANY", "The company name could not be saved. Use up to 80 characters.")
        company = " ".join(company.split())
        with self._lock:
            known = {_norm(c): c for c in self.companies()}
            company = known.get(_norm(company), company)            # "maju jaya" joins the existing "MAJU JAYA"
            self._update(job_id, company=company)
            moved = 0
            if company:
                for m in self.list_jobs():
                    if not m["company"] and m["id"] != job_id and company_for(m["name"], [company]):
                        self._update(m["id"], company=company)
                        moved += 1
            return moved

    def get_job(self, job_id: str) -> dict:
        """Status and progress, plus how many cells the user still has to check."""
        meta = self._meta(job_id)
        meta["cells_to_check"] = None
        if meta["status"] == "done":
            meta["cells_to_check"] = count_to_check(merged_pages(self.load_result(job_id), self.load_edits(job_id)))
        return meta

    # ------------------------------------------------------------------------------------------ queue/worker
    def _enqueue(self, job_id: str) -> None:
        with self._lock:
            self._pending.add(job_id)
            self._queue.put(job_id)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._work, name="table-reader-worker", daemon=True)
                self._worker.start()

    def resume(self, job_id: str) -> dict:
        """Read the pages a stopped job has not read yet (plan limit reached, sign-in expired, app closed…)."""
        with self._lock:
            meta = self._meta(job_id)
            waiting = job_id in self._pending and job_id != self._current and self._cancels.get(job_id) is not None \
                and self._cancels[job_id].is_set()
            if waiting:                          # cancelled while still in the queue: its place in the queue is kept
                self._cancels.pop(job_id)
                return self._update(job_id, status="queued", error=None)
            if job_id in self._pending or meta["status"] in ("queued", "reading"):
                raise OcrError("JOB_BUSY", "Table Reader is already reading this document. Wait for it to finish.")
            if meta["status"] == "done":
                return meta
            meta = self._update(job_id, status="queued", error=None)
            self._enqueue(job_id)
            return meta

    def cancel(self, job_id: str) -> dict:
        """Stop reading a document the user no longer wants read. Pages already read are kept and the document can be
        continued later. Does nothing if it is not queued or being read."""
        with self._lock:
            meta = self._meta(job_id)
            if meta["status"] not in ("queued", "reading") or job_id not in self._pending:
                return meta
            self._cancels.setdefault(job_id, threading.Event()).set()
            return self._update(job_id, status="failed", error=_CANCELLED)

    def active_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def shutdown(self, wait: float = 10.0) -> None:
        """The app is closing: stop every document being read or waiting (they show as cancelled and can be continued
        next time) and make sure Claude's process is gone before returning."""
        with self._lock:
            active = [j for j in self._pending]
        for job_id in active:
            try:
                self.cancel(job_id)
            except OcrError:
                pass
        self.wait_idle(wait)

    def wait_idle(self, timeout: float = 60.0) -> bool:
        """Block until nothing is queued or being read (for tests and scripts). False if it timed out."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                if not self._pending:
                    return True
            time.sleep(0.02)
        return False

    def _work(self) -> None:
        while True:
            try:
                job_id = self._queue.get(timeout=2)
            except queue.Empty:
                with self._lock:
                    if self._queue.empty():
                        self._worker = None
                        return
                continue
            try:
                self._process(job_id)
            except Exception:  # noqa: BLE001 - _process reports its own failures; this keeps the worker alive
                log.exception("Unexpected error while reading %s", job_id)
            finally:
                with self._lock:
                    self._pending.discard(job_id)
                self._queue.task_done()

    def _process(self, job_id: str) -> None:
        with self._lock:
            cancel = self._cancels.get(job_id)
            if cancel is not None and cancel.is_set():       # cancelled while waiting: nothing to read
                self._cancels.pop(job_id, None)
                return
            d = self._dir(job_id)
            cancel = self._cancels.setdefault(job_id, threading.Event())
            self._current = job_id
            self._update(job_id, status="reading", error=None)
        ocr.set_cancel_event(cancel)
        try:
            self._read_pages(job_id, d, cancel)
        finally:
            ocr.set_cancel_event(None)
            with self._lock:
                self._current = None
                self._cancels.pop(job_id, None)

    def _read_pages(self, job_id: str, d: Path, cancel: threading.Event) -> None:
        try:
            original = next((d / "original").iterdir())
            page_images = pages.render_pages(original, d / "pages")
            total = len(page_images)
            self._update(job_id, pages_total=total, pages_done=self._count_readings(d))
            for number, image in enumerate(page_images, start=1):
                reading = d / "reading" / f"page-{number}.json"
                if reading.exists():
                    continue
                if cancel.is_set():
                    raise OcrError(_CANCELLED["code"], _CANCELLED["message"])
                try:
                    record = self._reader(image)
                except OcrError as exc:
                    if total > 1 and exc.code != _CANCELLED["code"]:
                        raise OcrError(exc.code, f"Page {number} of {total}: {exc.message}") from exc
                    raise
                pages.turn_page(image, int(record.get("rotated_clockwise") or 0))   # before the reading is saved
                record["page"] = number
                _write_json(reading, record)
                self._update(job_id, pages_done=self._count_readings(d))
            if not (d / "result.json").exists():
                _write_json(d / "result.json", {"source": self._meta(job_id)["name"], "pages": self._readings(d)})
            self._update(job_id, status="done", error=None, finished=datetime.now().isoformat(timespec="seconds"))
        except OcrError as exc:
            self._update(job_id, status="failed", error={"code": exc.code, "message": exc.message})
            if exc.code in STOP_QUEUE_CODES:
                self._stop_queue(exc)
        except Exception:  # noqa: BLE001
            log.exception("Reading %s failed", job_id)
            self._update(job_id, status="failed", error={
                "code": "UNEXPECTED", "message": "Something went wrong while reading this document. Press Continue "
                                                 "to try again. If it keeps happening, tell your support person."})

    def _stop_queue(self, exc: OcrError) -> None:
        """Every waiting document would fail the same way: mark them stopped so they can be continued later."""
        while True:
            try:
                other = self._queue.get_nowait()
            except queue.Empty:
                return
            cancelled = self._cancels.get(other)
            try:
                if cancelled is None or not cancelled.is_set():       # a document the user cancelled stays "cancelled"
                    self._update(other, status="failed", error={"code": exc.code, "message": exc.message})
            except OcrError:
                pass
            with self._lock:
                self._pending.discard(other)
                self._cancels.pop(other, None)
            self._queue.task_done()

    @staticmethod
    def _count_readings(d: Path) -> int:
        return len(list((d / "reading").glob("page-*.json"))) if (d / "reading").is_dir() else 0

    @staticmethod
    def _readings(d: Path) -> list[dict]:
        files = sorted((d / "reading").glob("page-*.json"), key=lambda p: int(p.stem.split("-")[1])) \
            if (d / "reading").is_dir() else []
        return [_read_json(f) for f in files]

    # -------------------------------------------------------------------------------------------- results
    def load_result(self, job_id: str) -> dict:
        """Claude's reading, exactly as read. While a job is still running this holds the pages read so far."""
        d = self._dir(job_id)
        if (d / "result.json").exists():
            return _read_json(d / "result.json")
        return {"source": self._meta(job_id)["name"], "pages": self._readings(d)}

    def load_edits(self, job_id: str) -> dict:
        path = self._dir(job_id) / "edits.json"
        return _read_json(path) if path.exists() else {"edits": []}

    def save_edits(self, job_id: str, changes: list[dict]) -> dict:
        """Merge the user's corrections into edits.json (Claude's reading is never touched).

        A cell change is {"page", "row", "column", "value"}; a form-field change is {"page", "header", "value"}
        (row / header are 0-based positions). ``value`` "" means "checked, it is really empty"; ``None`` takes the
        correction back, so Claude's reading shows again."""
        result = self.load_result(job_id)
        by_page = {p["page"]: p for p in result["pages"]}
        with self._lock:
            edits = self.load_edits(job_id)
            kept = {_edit_key(e): e for e in edits["edits"]}
            for change in changes:
                entry = _validate_edit(change, by_page)
                if entry["value"] is None:
                    kept.pop(_edit_key(entry), None)
                else:
                    kept[_edit_key(entry)] = entry
            edits = {"edits": list(kept.values())}
            _write_json(self._dir(job_id) / "edits.json", edits)
            return edits

    def page_path(self, job_id: str, number: int) -> Path:
        path = pages.page_file(self._dir(job_id) / "pages", int(number))
        if not path.is_file():
            raise OcrError("PAGE_NOT_FOUND", "That page is not available yet.")
        return path

    def write_csv(self, job_id: str) -> Path:
        """Build the CSV (Claude's reading + corrections) in the job folder and return its path."""
        meta = self._meta(job_id)
        if meta["status"] != "done":
            raise OcrError("JOB_NOT_FINISHED", "This document has not been read completely yet. Wait until it "
                           "says it is finished (or press Continue), then download.")
        text = build_csv(self.load_result(job_id), self.load_edits(job_id))
        path = self._dir(job_id) / f"{meta.get('stem') or 'table'}.csv"
        path.write_bytes(text.encode("utf-8-sig"))           # BOM: Excel opens Malay/Chinese text correctly
        return path


# ------------------------------------------------------------------------------------------------- corrections
def _edit_key(edit: dict) -> tuple:
    if "header" in edit:
        return (edit["page"], "header", edit["header"])
    return (edit["page"], "cell", edit["row"], edit["column"])


def _validate_edit(change: dict, by_page: dict[int, dict]) -> dict:
    bad = OcrError("BAD_EDIT", "That correction does not match a cell in this document. Reload the page and try again.")
    if not isinstance(change, dict):
        raise bad
    page, value = change.get("page"), change.get("value")
    if not isinstance(page, int) or isinstance(page, bool) or page not in by_page \
            or not (value is None or isinstance(value, str)):
        raise bad
    if value is not None:
        value = value.strip()
        if len(value) > MAX_EDIT_LENGTH:
            raise OcrError("EDIT_TOO_LONG", f"That entry is too long (over {MAX_EDIT_LENGTH} characters).")
    record = by_page[page]
    if "header" in change:
        idx = change["header"]
        if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < len(record["header_fields"]):
            raise bad
        return {"page": page, "header": idx, "value": value}
    row, column = change.get("row"), change.get("column")
    if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row < len(record["rows"]) \
            or column not in record["column_labels"]:
        raise bad
    return {"page": page, "row": row, "column": column, "value": value}


def merged_pages(result: dict, edits: dict) -> list[dict]:
    """Claude's reading with the user's corrections on top, as new objects (neither input is changed).

    Each cell gets ``value`` = what to use now, ``edited`` and ``needs_review`` = still unresolved: a flagged cell stays
    unresolved until the user types something (an empty string counts as "checked, it is empty")."""
    corrections = {_edit_key(e): e["value"] for e in edits.get("edits", [])}
    out = []
    for record in result["pages"]:
        number = record["page"]

        def final(cell: dict, key: tuple) -> dict:
            merged = dict(cell)
            merged["edited"] = key in corrections
            if merged["edited"]:
                merged["value"] = corrections[key]
                merged["needs_review"] = False
            merged["claude_value"] = cell["value"]
            return merged

        out.append({
            "page": number, "quality": record["quality"], "notes": list(record["notes"]),
            "rotated_clockwise": record.get("rotated_clockwise", 0), "column_labels": list(record["column_labels"]),
            "header_fields": [{"label": f["label"], "cell": final(f["cell"], (number, "header", i))}
                              for i, f in enumerate(record["header_fields"])],
            "rows": [{"cells": {col: final(cell, (number, "cell", r, col)) for col, cell in row["cells"].items()}}
                     for r, row in enumerate(record["rows"])],
        })
    return out


def count_to_check(merged: list[dict]) -> int:
    n = 0
    for p in merged:
        n += sum(f["cell"]["needs_review"] for f in p["header_fields"])
        n += sum(c["needs_review"] for r in p["rows"] for c in r["cells"].values())
    return n


# ------------------------------------------------------------------------------------------------------- CSV
def _csv_safe(text: str) -> str:
    """Stop a cell from being run as a spreadsheet formula when opened in Excel (leading = @, or +/- then a letter)."""
    if text and (text[0] in "=@" or (text[0] in "+-" and len(text) > 1 and not (text[1].isdigit() or text[1] in " .,"))):
        return "'" + text
    return text


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return out


def _note(label: str, cell: dict) -> str:
    text = f"{label}: {cell['unclear_reason']}"
    if cell.get("raw_text"):
        text += f" (marks seen: {cell['raw_text']})"
    return text


def build_csv(result: dict, edits: dict) -> str:
    """One row per table row. Columns: form fields (Name, Month…) first, then Page, then the table's columns, then
    Notes. A cell that is still uncertain is left blank and described in Notes, so nothing uncertain looks certain."""
    merged = merged_pages(result, edits)
    header_cols: list[str] = []
    table_cols: list[str] = []
    for p in merged:
        for label in _unique([f["label"] for f in p["header_fields"]]):
            if label not in header_cols:
                header_cols.append(label)
        for col in p["column_labels"]:
            if col not in table_cols:
                table_cols.append(col)
    names = _unique(header_cols + ["Page"] + table_cols + ["Notes"])
    h, t = len(header_cols), len(table_cols)

    out_rows: list[list[str]] = []
    for p in merged:
        header_values = [""] * h
        header_notes = []
        for label, field in zip(_unique([f["label"] for f in p["header_fields"]]), p["header_fields"]):
            cell = field["cell"]
            header_values[header_cols.index(label)] = cell["value"] or ""
            if cell["needs_review"]:
                header_notes.append(_note(label, cell))
        for row in p["rows"]:
            values = [""] * t
            notes = list(header_notes)
            for col, cell in row["cells"].items():
                values[table_cols.index(col)] = cell["value"] or ""
                if cell["needs_review"]:
                    notes.append(_note(col, cell))
            out_rows.append(header_values + [str(p["page"])] + values + ["; ".join(notes)])

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(names)
    for r in out_rows:
        writer.writerow([_csv_safe(v) for v in r])
    return buf.getvalue()
