"""No clicks: files saved into the Inbox folder are read by themselves, and every finished table is kept as a CSV.

<Documents>\\Table Reader\\Inbox\\<company>\\<file>   a file saved here is taken in like a file dropped on the page; the
                                                   folder it is in (one folder per company) becomes its company
<Documents>\\Table Reader\\Inbox\\_Read\\…           where the file is moved once it has been taken in (never deleted)
<Documents>\\Table Reader\\Inbox\\_Not read\\…       files Table Reader cannot use (empty, damaged, too large)
<Documents>\\Table Reader\\Tables\\<company>\\<file>.csv   each finished document's table (the reading with the user's
                                                   corrections), written again whenever a cell is corrected

Reading still goes through the same queue, so the "never guess" rules and the yellow cells are exactly the same. Only
the dragging in and the pressing of Download are gone.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import pages
from jobs import Jobs, _read_json, _write_json, build_csv, safe_name
from ocr import OcrError

log = logging.getLogger("table_reader.inbox")
SETTLE_SECONDS = 5            # a file is taken once it has not changed for this long (it may still be copying)
MAX_BYTES = 150 * 1024 * 1024
READ, NOT_READ = "_Read", "_Not read"
NO_COMPANY = "No company"


class Inbox:
    def __init__(self, store: Jobs, folder: Path | None = None, tables: Path | None = None, interval: float = 5.0):
        self.store = store
        self.folder = Path(folder) if folder else store.root.parent / "Inbox"
        self.tables = Path(tables) if tables else store.root.parent / "Tables"
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------------------------------------ taking files in
    def waiting(self) -> list[Path]:
        """The files in the Inbox that can be taken in now: a kind Table Reader reads, not a temporary or hidden file,
        not in a folder whose name starts with "_", and unchanged for a few seconds."""
        if not self.folder.is_dir():
            return []
        now = time.time()
        found = []
        for path in sorted(self.folder.rglob("*")):
            parts = path.relative_to(self.folder).parts
            if not path.is_file() or any(p.startswith(("_", ".", "~$")) for p in parts) or not pages.is_supported(path.name):
                continue
            try:
                if now - path.stat().st_mtime >= SETTLE_SECONDS:
                    found.append(path)
            except OSError:
                continue
        return found

    def _move(self, path: Path, into: str) -> None:
        target = self.folder / into / path.relative_to(self.folder)
        target.parent.mkdir(parents=True, exist_ok=True)
        n = 1
        while target.exists():                                      # the same name was taken in before: keep both
            n += 1
            target = target.with_name(f"{path.stem} ({n}){path.suffix}")
        path.replace(target)

    def take_in(self) -> list[dict]:
        """One pass over the Inbox. Returns the documents that were queued for reading."""
        created = []
        for path in self.waiting():
            parts = path.relative_to(self.folder).parts
            try:
                if path.stat().st_size > MAX_BYTES:
                    raise OcrError("FILE_TOO_BIG", "larger than 150 MB")
                content = path.read_bytes()
            except OcrError:
                self._move(path, NOT_READ)
                continue
            except OSError:
                continue                                            # still being written, or open elsewhere: next pass
            try:
                job = self.store.create_job(path.name, content)
                if len(parts) > 1:
                    self.store.set_company(job["id"], parts[0])     # the folder it was saved in
                created.append(job)
                self._move(path, READ)
            except OcrError as exc:
                log.warning("Inbox: %s was not taken in (%s)", path.name, exc.code)
                self._move(path, NOT_READ)
            except OSError:
                log.exception("Inbox: %s could not be moved", path.name)
        return created

    # ------------------------------------------------------------------------------------------------- tables as CSV
    def export_tables(self) -> int:
        """Write the CSV of every finished document that has none yet, or whose reading, corrections or company changed
        since it was written. Returns how many were written. A CSV that is open in Excel is tried again next time."""
        index_path = self.tables / ".written.json"
        try:
            index = _read_json(index_path) if index_path.exists() else {}
        except (OSError, ValueError):
            index = {}
        written = 0
        for meta in self.store.list_jobs():
            if meta["status"] != "done":
                continue
            d = self.store.root / meta["id"]
            changed = max((p.stat().st_mtime for p in (d / "result.json", d / "edits.json") if p.exists()), default=0.0)
            target = self.tables / safe_name(meta.get("company") or NO_COMPANY) / f"{safe_name(meta['id'])}.csv"
            before = index.get(meta["id"]) or {}
            if before.get("path") == str(target) and before.get("changed") == changed and target.exists():
                continue
            try:
                text = build_csv(self.store.load_result(meta["id"]), self.store.load_edits(meta["id"]))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(text.encode("utf-8-sig"))
                old = before.get("path")
                if old and old != str(target) and Path(old).is_file() and self.tables in Path(old).parents:
                    Path(old).unlink()                              # the company changed: the table moved with it
            except (OSError, OcrError, ValueError):
                continue
            index[meta["id"]] = {"path": str(target), "changed": changed}
            written += 1
        if written:
            try:
                _write_json(index_path, index)
            except OSError:
                pass
        return written

    # ------------------------------------------------------------------------------------------------------ running
    def run_once(self) -> tuple[int, int]:
        return len(self.take_in()), self.export_tables()

    def start(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)

        def loop():
            while not self._stop.wait(self.interval):
                try:
                    self.run_once()
                except Exception:  # noqa: BLE001 - the watcher must never stop the app
                    log.exception("Inbox pass failed")

        self._thread = threading.Thread(target=loop, name="inbox", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
