"""Tests for inbox.py: files saved into the Inbox folder are read by themselves; finished tables are kept as CSVs."""
import os
import time

from fastapi.testclient import TestClient
from PIL import Image

import app as app_module
from inbox import Inbox
from jobs import Jobs
from tests.helpers import good, record


def card(image):
    return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"))


def save_picture(path, age=60):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30), "white").save(path)
    old = time.time() - age
    os.utime(path, (old, old))
    return path


def test_files_in_the_inbox_are_read_and_filed_under_their_folders_company(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=card)
    box = Inbox(store)
    assert box.folder == tmp_path / "Inbox" and box.tables == tmp_path / "Tables" and box.take_in() == []
    save_picture(box.folder / "MAJU JAYA" / "ALI SEPT 26.png")
    save_picture(box.folder / "BINA" / "week 1" / "SITI.jpg")
    save_picture(box.folder / "loose card.png")
    taken = box.take_in()
    assert store.wait_idle()
    by_name = {m["name"]: m for m in store.list_jobs()}
    assert {m["name"] for m in taken} == set(by_name) == {"ALI SEPT 26.png", "SITI.jpg", "loose card.png"}
    assert by_name["ALI SEPT 26.png"]["company"] == "MAJU JAYA" and by_name["SITI.jpg"]["company"] == "BINA"
    assert by_name["loose card.png"]["company"] == "" and all(m["status"] == "done" for m in by_name.values())
    # taken in once: the files were moved to _Read (never deleted), so the next pass finds nothing
    assert (box.folder / "_Read" / "MAJU JAYA" / "ALI SEPT 26.png").is_file()
    assert (box.folder / "_Read" / "BINA" / "week 1" / "SITI.jpg").is_file() and (box.folder / "_Read" / "loose card.png").is_file()
    assert box.waiting() == [] and box.take_in() == [] and len(store.list_jobs()) == 3
    store.shutdown()


def test_files_still_being_copied_temporary_files_and_other_kinds_are_left_alone(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=card)
    box = Inbox(store)
    fresh = save_picture(box.folder / "ACME" / "just saved.png", age=0)          # may still be copying
    save_picture(box.folder / "ACME" / "~$notes.png")
    (box.folder / "ACME" / "notes.xlsx").write_bytes(b"not a scan")
    save_picture(box.folder / "_Read" / "old.png")                                # taken in before
    assert box.take_in() == [] and fresh.is_file() and (box.folder / "ACME" / "notes.xlsx").is_file()
    os.utime(fresh, (time.time() - 60, time.time() - 60))
    assert [m["name"] for m in box.take_in()] == ["just saved.png"]
    store.wait_idle()
    store.shutdown()


def test_a_file_that_cannot_be_used_goes_to_not_read_and_the_same_name_twice_is_kept_twice(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=card)
    box = Inbox(store)
    empty = box.folder / "ACME" / "empty.png"
    empty.parent.mkdir(parents=True)
    empty.write_bytes(b"")
    os.utime(empty, (time.time() - 60, time.time() - 60))
    assert box.take_in() == [] and (box.folder / "_Not read" / "ACME" / "empty.png").is_file() and store.list_jobs() == []
    for _ in range(2):
        save_picture(box.folder / "ACME" / "card.png")
        assert len(box.take_in()) == 1
    assert (box.folder / "_Read" / "ACME" / "card.png").is_file() and (box.folder / "_Read" / "ACME" / "card (2).png").is_file()
    store.wait_idle()
    store.shutdown()


def test_every_finished_table_is_kept_as_a_csv_and_written_again_after_a_correction(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=card)
    box = Inbox(store)
    save_picture(box.folder / "MAJU JAYA" / "ALI.png")
    job, = box.take_in()
    assert store.wait_idle() and box.export_tables() == 1
    table = box.tables / "MAJU JAYA" / f"{job['id']}.csv"
    assert "9" in table.read_text(encoding="utf-8-sig") and box.export_tables() == 0          # nothing changed: not rewritten
    time.sleep(0.05)
    store.save_edits(job["id"], [{"page": 1, "row": 0, "column": "Total", "value": "8.5"}])
    assert box.export_tables() == 1 and "8.5" in table.read_text(encoding="utf-8-sig")
    store.set_company(job["id"], "BINA")                                                     # the table moves with it
    assert box.export_tables() == 1 and not table.exists() and (box.tables / "BINA" / f"{job['id']}.csv").is_file()
    store.shutdown()


def test_the_page_can_open_the_two_folders(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(app_module.os, "startfile", opened.append, raising=False)
    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        assert c.get("/api/folders").json() == {"inbox": str(tmp_path / "Inbox"), "tables": str(tmp_path / "Tables")}
        assert c.post("/api/folders/inbox/open").status_code == 200 and c.post("/api/folders/tables/open").status_code == 200
        assert opened == [tmp_path / "Inbox", tmp_path / "Tables"] and (tmp_path / "Inbox").is_dir()
        assert c.post("/api/folders/windows/open").status_code in (400, 404)
