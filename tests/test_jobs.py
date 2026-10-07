"""Tests for jobs.py: folders, background reading, resume, corrections, CSV. Claude is replaced by a fake reader."""
import csv
import io
import json
import threading

import pytest
from PIL import Image

import jobs
import ocr
from helpers import cell, good, make_pdf, record


class FakeReader:
    """Stands in for ocr.read_image. ``script`` maps call number (1-based) to a record or an exception."""

    def __init__(self, script=None, default=None):
        self.script = script or {}
        self.default = default or (lambda n: record([{"Date": good(str(n)), "In": good("07:30")}],
                                                    header=[("Name", good("Ali"))]))
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, image):
        with self.lock:
            self.calls.append(image.name)
            n = len(self.calls)
        item = self.script.get(n)
        if callable(item):
            item = item(n)
        if isinstance(item, BaseException):
            raise item
        return item if item is not None else self.default(n)


@pytest.fixture
def store(tmp_path):
    return jobs.Jobs(tmp_path / "jobs", reader=FakeReader())


def make(store, name="form.pdf", pages_=2, tmp_path=None):
    src = tmp_path / name
    make_pdf(src, pages_)
    return store.create_job(name, src.read_bytes())


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), "white").save(buf, "PNG")
    return buf.getvalue()


# ------------------------------------------------------------------------------------------- creating jobs
def test_create_job_makes_the_folder_layout(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    meta = s.create_job("Sept Time Card.JPG", png_bytes())
    assert s.wait_idle()
    d = tmp_path / "jobs" / meta["id"]
    assert meta["id"].endswith("_Sept Time Card") and meta["id"][4] == "-" and meta["id"][10] == "_"
    assert (d / "original" / "Sept Time Card.jpg").is_file()
    assert (d / "pages" / "page-1.png").is_file()
    assert (d / "reading" / "page-1.json").is_file() and (d / "result.json").is_file() and (d / "job.json").is_file()
    assert s.get_job(meta["id"])["status"] == "done"


def test_unsupported_and_empty_uploads_are_refused_without_leaving_a_folder(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    with pytest.raises(ocr.OcrError) as e:
        s.create_job("sheet.xlsx", b"x")
    assert e.value.code == "FILE_TYPE"
    with pytest.raises(ocr.OcrError) as e:
        s.create_job("a.pdf", b"")
    assert e.value.code == "EMPTY_FILE"
    assert s.list_jobs() == [] and not list((tmp_path / "jobs").iterdir())


def test_names_are_made_safe_but_keep_unicode(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    meta = s.create_job("..\\..\\evil:name?.png", png_bytes())
    assert s.wait_idle()
    assert ".." not in meta["id"] and all(c not in meta["id"] for c in '<>:"/\\|?*')
    assert (tmp_path / "jobs" / meta["id"]).is_dir()
    assert jobs.safe_name("Gaji 张伟 Sept") == "Gaji 张伟 Sept"
    assert jobs.safe_name("   ...  ") == "document"
    assert len(jobs.safe_name("x" * 300)) == 80


def test_two_uploads_with_the_same_name_get_separate_folders(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    a = s.create_job("same.png", png_bytes())
    b = s.create_job("same.png", png_bytes())
    assert a["id"] != b["id"] and s.wait_idle()
    assert {m["id"] for m in s.list_jobs()} == {a["id"], b["id"]}


def test_list_is_newest_first(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    first = s.create_job("one.png", png_bytes())
    s._update(first["id"], created="2020-01-01T00:00:00")
    second = s.create_job("two.png", png_bytes())
    assert s.wait_idle()
    assert [m["id"] for m in s.list_jobs()] == [second["id"], first["id"]]


@pytest.mark.parametrize("bad", ["", ".", "..", "../x", "a/b", "a\\b", "nope", None, 5])
def test_unknown_or_unsafe_job_ids_are_not_found(store, bad):
    with pytest.raises(ocr.OcrError) as e:
        store.get_job(bad)
    assert e.value.code == "JOB_NOT_FOUND"


# -------------------------------------------------------------------------------------------------- reading
def test_pdf_is_read_page_by_page_with_progress(tmp_path):
    seen_progress = []
    s = jobs.Jobs(tmp_path / "jobs")
    original = s

    def reader(image):
        meta = original.list_jobs()[0]
        seen_progress.append((meta["status"], meta["pages_total"], meta["pages_done"]))
        return record([{"Date": good("1"), "In": good("7")}])
    s._reader = reader
    meta = make(s, pages_=3, tmp_path=tmp_path)
    assert s.wait_idle()
    assert seen_progress == [("reading", 3, 0), ("reading", 3, 1), ("reading", 3, 2)]
    done = s.get_job(meta["id"])
    assert done["status"] == "done" and done["pages_done"] == 3 and done["error"] is None
    result = s.load_result(meta["id"])
    assert [p["page"] for p in result["pages"]] == [1, 2, 3]


def test_result_json_is_never_changed_by_corrections(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(default=lambda n: record(
        [{"Date": good("1"), "In": cell(None, "7:?0", 40, "faded")}])))
    meta = make(s, pages_=1, tmp_path=tmp_path)
    assert s.wait_idle()
    result_file = tmp_path / "jobs" / meta["id"] / "result.json"
    reading_file = tmp_path / "jobs" / meta["id"] / "reading" / "page-1.json"
    before = (result_file.read_bytes(), reading_file.read_bytes())
    s.save_edits(meta["id"], [{"page": 1, "row": 0, "column": "In", "value": "7:30"}])
    s.write_csv(meta["id"])
    assert (result_file.read_bytes(), reading_file.read_bytes()) == before
    assert (tmp_path / "jobs" / meta["id"] / "edits.json").is_file()
    assert s.load_result(meta["id"])["pages"][0]["rows"][0]["cells"]["In"]["value"] is None


def test_sideways_page_image_is_stored_upright(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(default=lambda n: record(
        [{"Date": good("1"), "In": good("7")}], turn=90)))
    meta = s.create_job("photo.png", png_bytes())               # stored as 60 x 40
    assert s.wait_idle()
    with Image.open(tmp_path / "jobs" / meta["id"] / "pages" / "page-1.png") as im:
        assert im.size == (40, 60)
    assert s.load_result(meta["id"])["pages"][0]["rotated_clockwise"] == 90


def test_a_stopped_job_resumes_without_rereading_finished_pages(tmp_path):
    reader = FakeReader(script={2: ocr.OcrError("CLAUDE_CLI_TIMEOUT", "Claude took too long. Try again.")})
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    meta = make(s, pages_=3, tmp_path=tmp_path)
    assert s.wait_idle()
    failed = s.get_job(meta["id"])
    assert failed["status"] == "failed" and failed["pages_done"] == 1
    assert failed["error"]["code"] == "CLAUDE_CLI_TIMEOUT" and failed["error"]["message"].startswith("Page 2 of 3:")
    s.resume(meta["id"])
    assert s.wait_idle()
    assert reader.calls == ["page-1.png", "page-2.png", "page-2.png", "page-3.png"]   # page 1 not read again
    assert s.get_job(meta["id"])["status"] == "done"
    assert [p["page"] for p in s.load_result(meta["id"])["pages"]] == [1, 2, 3]


def test_single_page_errors_have_no_page_prefix(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(script={1: ocr.OcrError("X", "Try again.")}))
    meta = s.create_job("one.png", png_bytes())
    assert s.wait_idle()
    assert s.get_job(meta["id"])["error"]["message"] == "Try again."


def test_partial_result_is_available_while_stopped(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(script={2: ocr.OcrError("X", "Try again.")}))
    meta = make(s, pages_=2, tmp_path=tmp_path)
    assert s.wait_idle()
    assert [p["page"] for p in s.load_result(meta["id"])["pages"]] == [1]
    assert not (tmp_path / "jobs" / meta["id"] / "result.json").exists()
    with pytest.raises(ocr.OcrError) as e:
        s.write_csv(meta["id"])
    assert e.value.code == "JOB_NOT_FINISHED"


def test_resume_refuses_a_job_that_is_already_being_read(tmp_path):
    gate = threading.Event()
    reader = FakeReader(script={1: lambda n: (gate.wait(5), record([{"Date": good("1"), "In": good("7")}]))[1]})
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    meta = s.create_job("one.png", png_bytes())
    with pytest.raises(ocr.OcrError) as e:
        s.resume(meta["id"])
    assert e.value.code == "JOB_BUSY"
    gate.set()
    assert s.wait_idle()
    assert s.resume(meta["id"])["status"] == "done"         # finished jobs are left alone
    assert len(reader.calls) == 1


def test_documents_are_read_one_at_a_time(tmp_path):
    active, peak = [0], [0]
    lock = threading.Lock()

    def reader(image):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        threading.Event().wait(0.03)
        with lock:
            active[0] -= 1
        return record([{"Date": good("1"), "In": good("7")}])
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    for i in range(4):
        s.create_job(f"f{i}.png", png_bytes())
    assert s.wait_idle() and peak[0] == 1
    assert all(m["status"] == "done" for m in s.list_jobs())


def test_plan_limit_stops_the_waiting_documents_too(tmp_path):
    gate = threading.Event()
    limit = ocr.OcrError("CLAUDE_PLAN_LIMIT", "Your Claude plan has reached its usage limit for now. Wait, then try again.")
    reader = FakeReader(script={1: lambda n: (gate.wait(5), limit)[1]})
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    a = s.create_job("a.png", png_bytes())
    b = s.create_job("b.png", png_bytes())
    c = s.create_job("c.png", png_bytes())
    gate.set()
    assert s.wait_idle()
    assert len(reader.calls) == 1                                      # b and c never hit Claude
    for m in (a, b, c):
        got = s.get_job(m["id"])
        assert got["status"] == "failed" and got["error"]["code"] == "CLAUDE_PLAN_LIMIT"
    reader.script.clear()
    s.resume(b["id"])
    assert s.wait_idle() and s.get_job(b["id"])["status"] == "done"


def test_other_failures_do_not_stop_the_queue(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(script={1: ocr.OcrError("CLAUDE_CLI_BAD_JSON", "Try again.")}))
    a = s.create_job("a.png", png_bytes())
    b = s.create_job("b.png", png_bytes())
    assert s.wait_idle()
    assert s.get_job(a["id"])["status"] == "failed" and s.get_job(b["id"])["status"] == "done"


def test_unexpected_crash_is_reported_plainly_and_the_worker_survives(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(script={1: ZeroDivisionError("boom")}))
    a = s.create_job("a.png", png_bytes())
    assert s.wait_idle()
    got = s.get_job(a["id"])
    assert got["status"] == "failed" and got["error"]["code"] == "UNEXPECTED" and "Continue" in got["error"]["message"]
    assert "boom" not in got["error"]["message"]
    b = s.create_job("b.png", png_bytes())
    assert s.wait_idle() and s.get_job(b["id"])["status"] == "done"


def test_damaged_upload_fails_with_a_clear_message(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    meta = s.create_job("broken.pdf", b"not a pdf")
    assert s.wait_idle()
    got = s.get_job(meta["id"])
    assert got["status"] == "failed" and got["error"]["code"] == "PDF_UNREADABLE"


def test_jobs_cut_off_by_closing_the_app_can_be_continued(tmp_path):
    root = tmp_path / "jobs"
    s = jobs.Jobs(root, reader=FakeReader(script={2: ocr.OcrError("X", "Try again.")}))
    meta = make(s, pages_=2, tmp_path=tmp_path)
    assert s.wait_idle()
    s._update(meta["id"], status="reading", error=None)                # as if the app died mid-read
    (root / "stray.txt").write_text("not a job")
    reader2 = FakeReader()
    s2 = jobs.Jobs(root, reader=reader2)                               # app restarted
    got = s2.get_job(meta["id"])
    assert got["status"] == "failed" and got["error"]["code"] == "INTERRUPTED" and "Continue" in got["error"]["message"]
    s2.resume(meta["id"])
    assert s2.wait_idle() and s2.get_job(meta["id"])["status"] == "done"
    assert reader2.calls == ["page-2.png"]


def test_page_images_can_be_found_and_missing_ones_are_reported(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    meta = s.create_job("one.png", png_bytes())
    assert s.wait_idle()
    assert s.page_path(meta["id"], 1).is_file()
    with pytest.raises(ocr.OcrError) as e:
        s.page_path(meta["id"], 2)
    assert e.value.code == "PAGE_NOT_FOUND"


# ------------------------------------------------------------------------------------------------ corrections
@pytest.fixture
def done(tmp_path):
    reader = FakeReader(default=lambda n: record(
        [{"Date": good("1"), "In": cell(None, "7:?0", 40, "faded")},
         {"Date": good("2"), "In": good("07:30")}],
        header=[("Name", good("Ali")), ("Month", cell(None, "S?pt", 30, "smudged"))]))
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    meta = make(s, pages_=1, tmp_path=tmp_path)
    assert s.wait_idle()
    return s, meta["id"]


def test_cells_to_check_counts_unresolved_cells_and_drops_when_corrected(done):
    s, jid = done
    assert s.get_job(jid)["cells_to_check"] == 2
    s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": "7:30"}])
    assert s.get_job(jid)["cells_to_check"] == 1
    s.save_edits(jid, [{"page": 1, "header": 1, "value": ""}])        # "checked, it is really empty"
    assert s.get_job(jid)["cells_to_check"] == 0


def test_edits_merge_replace_and_can_be_taken_back(done):
    s, jid = done
    s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": " 7:31 "}])
    s.save_edits(jid, [{"page": 1, "row": 1, "column": "In", "value": "08:00"}])
    edits = s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": "7:32"}])
    values = {(e["row"], e["column"]): e["value"] for e in edits["edits"]}
    assert values == {(0, "In"): "7:32", (1, "In"): "08:00"}
    edits = s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": None}])     # back to Claude's reading
    assert [e["row"] for e in edits["edits"]] == [1]
    assert s.load_edits(jid) == edits


@pytest.mark.parametrize("change", [
    {"page": 9, "row": 0, "column": "In", "value": "x"},
    {"page": 1, "row": 5, "column": "In", "value": "x"},
    {"page": 1, "row": -1, "column": "In", "value": "x"},
    {"page": 1, "row": 0, "column": "Nope", "value": "x"},
    {"page": 1, "header": 9, "value": "x"},
    {"page": True, "row": 0, "column": "In", "value": "x"},
    {"page": [1], "row": 0, "column": "In", "value": "x"},
    {"page": 1, "row": 0, "column": "In", "value": 5},
    {"row": 0, "column": "In", "value": "x"},
    "not a dict",
])
def test_corrections_that_do_not_match_a_cell_are_refused(done, change):
    s, jid = done
    with pytest.raises(ocr.OcrError) as e:
        s.save_edits(jid, [change])
    assert e.value.code == "BAD_EDIT"
    assert s.load_edits(jid) == {"edits": []}


def test_one_bad_correction_saves_nothing_from_the_batch(done):
    s, jid = done
    with pytest.raises(ocr.OcrError):
        s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": "7:30"},
                           {"page": 1, "row": 99, "column": "In", "value": "x"}])
    assert s.load_edits(jid) == {"edits": []}


def test_very_long_correction_is_refused(done):
    s, jid = done
    with pytest.raises(ocr.OcrError) as e:
        s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": "x" * 5000}])
    assert e.value.code == "EDIT_TOO_LONG"


def test_merged_pages_does_not_change_its_inputs(done):
    s, jid = done
    result, edits = s.load_result(jid), {"edits": [{"page": 1, "row": 0, "column": "In", "value": "7:30"}]}
    before = json.dumps([result, edits], sort_keys=True)
    merged = jobs.merged_pages(result, edits)
    assert json.dumps([result, edits], sort_keys=True) == before
    cell0 = merged[0]["rows"][0]["cells"]["In"]
    assert cell0["value"] == "7:30" and cell0["edited"] and not cell0["needs_review"] and cell0["claude_value"] is None
    assert cell0["raw_text"] == "7:?0"                                # Claude's marks stay visible


# ------------------------------------------------------------------------------------------------------- CSV
def read_csv(path):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                            # UTF-8 BOM so Excel shows Unicode correctly
    return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))


def test_csv_layout_form_fields_first_then_page_table_then_notes(done):
    s, jid = done
    rows = read_csv(s.write_csv(jid))
    assert rows[0] == ["Name", "Month", "Page", "Date", "In", "Notes"]
    assert rows[1][:5] == ["Ali", "", "1", "1", ""]                   # uncertain cells stay blank...
    assert "In: faded (marks seen: 7:?0)" in rows[1][5] and "Month: smudged (marks seen: S?pt)" in rows[1][5]
    assert rows[2] == ["Ali", "", "1", "2", "07:30", "Month: smudged (marks seen: S?pt)"]   # ...and are listed in Notes


def test_csv_applies_corrections_and_clears_notes_for_corrected_cells(done):
    s, jid = done
    s.save_edits(jid, [{"page": 1, "row": 0, "column": "In", "value": "7:30"},
                       {"page": 1, "header": 1, "value": "September"}])
    rows = read_csv(s.write_csv(jid))
    assert rows[1] == ["Ali", "September", "1", "1", "7:30", ""]
    assert rows[2] == ["Ali", "September", "1", "2", "07:30", ""]


def test_csv_file_is_named_after_the_document(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    meta = s.create_job("Gaji Sept.png", png_bytes())
    assert s.wait_idle()
    assert s.write_csv(meta["id"]).name == "Gaji Sept.csv"


def test_csv_for_several_pages_with_different_columns(tmp_path):
    pages_ = {1: record([{"Date": good("1"), "In": good("7")}], header=[("Name", good("Ali"))]),
              2: record([{"Date": good("2"), "Out": good("17")}], labels=("Date", "Out"),
                        header=[("Name", good("Bala")), ("Dept", good("QC"))])}
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(script=pages_))
    meta = make(s, pages_=2, tmp_path=tmp_path)
    assert s.wait_idle()
    rows = read_csv(s.write_csv(meta["id"]))
    assert rows[0] == ["Name", "Dept", "Page", "Date", "In", "Out", "Notes"]
    assert rows[1] == ["Ali", "", "1", "1", "7", "", ""]
    assert rows[2] == ["Bala", "QC", "2", "2", "", "17", ""]


def test_csv_column_names_are_made_unique(tmp_path):
    rec = record([{"Name": good("x"), "Page": good("y")}], labels=("Name", "Page"), header=[("Name", good("Ali"))])
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(default=lambda n: rec))
    meta = s.create_job("a.png", png_bytes())
    assert s.wait_idle()
    header = read_csv(s.write_csv(meta["id"]))[0]
    assert header == ["Name", "Page", "Name (2)", "Page (2)", "Notes"]


def test_csv_keeps_unicode_commas_quotes_and_newlines(tmp_path):
    tricky = 'Ahmad bin "Ali", Jr.\nL2 张伟'
    rec = record([{"Date": good(tricky), "In": good("7")}])
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(default=lambda n: rec))
    meta = s.create_job("a.png", png_bytes())
    assert s.wait_idle()
    assert read_csv(s.write_csv(meta["id"]))[1][1] == tricky


@pytest.mark.parametrize("text,expected", [
    ("=SUM(A1:A9)", "'=SUM(A1:A9)"), ("@cmd", "'@cmd"), ("+cmd|x", "'+cmd|x"), ("-cmd", "'-cmd"),
    ("-", "-"), ("-5", "-5"), ("+60123456789", "+60123456789"), ("- 5", "- 5"), ("07:30", "07:30"), ("", ""),
    ("O.T. =5", "O.T. =5"),
])
def test_csv_cells_cannot_run_as_formulas(text, expected):
    assert jobs._csv_safe(text) == expected


def test_csv_with_no_rows_still_has_a_header_line(tmp_path):
    rec = record([], header=[("Name", good("Ali"))])
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader(default=lambda n: rec))
    meta = s.create_job("a.png", png_bytes())
    assert s.wait_idle()
    assert read_csv(s.write_csv(meta["id"])) == [["Name", "Page", "Date", "In", "Notes"]]


def test_default_root_uses_documents_folder_or_override(monkeypatch, tmp_path):
    monkeypatch.setenv("TABLE_READER_HOME", str(tmp_path / "x"))
    assert jobs.default_root() == tmp_path / "x" / "jobs"
    monkeypatch.delenv("TABLE_READER_HOME")
    assert jobs.default_root().parts[-2:] == ("Table Reader", "jobs")
    assert jobs.default_root().parent.parent == jobs.documents_dir()
    assert jobs.documents_dir().is_dir()


# ------------------------------------------------------------------------------------------------------- cancel
class BlockingReader:
    """Reads page 1 normally; page 2 waits until Cancel is pressed (like the real CLI runner does)."""

    def __init__(self):
        self.started = threading.Event()
        self.calls = []

    def __call__(self, image):
        self.calls.append(image.name)
        if image.name == "page-2.png":
            self.started.set()
            event = ocr._cancel.event
            assert event.wait(20), "cancel never reached the reader"
            raise ocr.OcrError("CANCELLED", "cancelled")
        return record([{"Date": good("1/9"), "In": good("07:30")}])


def test_cancel_while_reading_keeps_finished_pages_and_can_continue(tmp_path):
    reader = BlockingReader()
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    meta = make(s, pages_=3, tmp_path=tmp_path)
    assert reader.started.wait(20)
    assert s.cancel(meta["id"])["status"] == "failed"
    assert s.wait_idle()
    job = s.get_job(meta["id"])
    assert job["status"] == "failed" and job["error"]["code"] == "CANCELLED"
    assert "Page 2 of 3" not in job["error"]["message"] and job["pages_done"] == 1
    assert len(s.load_result(meta["id"])["pages"]) == 1                          # page 1 kept
    s.resume(meta["id"])                                                         # cancel can be undone with Continue
    reader.started.clear()
    assert reader.started.wait(20)
    s.cancel(meta["id"])
    assert s.wait_idle()


def test_cancel_a_waiting_document_means_it_is_never_read(tmp_path):
    reader = BlockingReader()
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    first = make(s, name="a.pdf", pages_=2, tmp_path=tmp_path)
    second = make(s, name="b.pdf", pages_=1, tmp_path=tmp_path)
    assert reader.started.wait(20)                                   # worker is busy with the first document
    assert s.cancel(second["id"])["error"]["code"] == "CANCELLED"
    s.cancel(first["id"])
    assert s.wait_idle()
    assert s.get_job(second["id"])["status"] == "failed" and s.get_job(second["id"])["error"]["code"] == "CANCELLED"
    assert reader.calls == ["page-1.png", "page-2.png"]              # nothing of the second document was read


def test_cancelled_waiting_document_can_be_continued_before_its_turn(tmp_path):
    reader = BlockingReader()
    s = jobs.Jobs(tmp_path / "jobs", reader=reader)
    make(s, name="a.pdf", pages_=2, tmp_path=tmp_path)
    second = make(s, name="b.pdf", pages_=1, tmp_path=tmp_path)
    assert reader.started.wait(20)
    s.cancel(second["id"])
    assert s.resume(second["id"])["status"] == "queued"              # no "already reading" error; keeps its place
    for j in s.list_jobs():
        s.cancel(j["id"])
    assert s.wait_idle()


def test_cancel_on_a_finished_document_does_nothing(tmp_path):
    s = jobs.Jobs(tmp_path / "jobs", reader=FakeReader())
    meta = make(s, pages_=1, tmp_path=tmp_path)
    assert s.wait_idle()
    assert s.cancel(meta["id"])["status"] == "done"
