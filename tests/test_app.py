import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as app_module
import ocr
from jobs import Jobs
from tests.helpers import cell, good, make_pdf, record


def png_bytes(tmp_path):
    p = tmp_path / "x.png"
    Image.new("RGB", (60, 40), "white").save(p)
    return p.read_bytes()


def page_reader(image):
    return record([{"Date": good("1/9"), "In": cell(None, "07?6", 40, "smudged")}], header=[("Name", good("Ali"))])


@pytest.fixture
def client(tmp_path):
    jobs = Jobs(tmp_path / "jobs", reader=page_reader)
    with TestClient(app_module.create_app(jobs), base_url="http://localhost") as c:
        c.jobs = jobs
        yield c


def upload(client, tmp_path, name="scan.png", content=None):
    content = content if content is not None else png_bytes(tmp_path)
    return client.post("/api/jobs", files=[("files", (name, content, "application/octet-stream"))])


def test_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Table Reader" in r.text
    assert client.get("/app.js").status_code == 200 and client.get("/app.css").status_code == 200


def test_upload_read_edit_download(client, tmp_path):
    r = upload(client, tmp_path)
    assert r.status_code == 200 and not r.json()["rejected"]
    job_id = r.json()["created"][0]["id"]
    assert client.jobs.wait_idle(30)

    doc = client.get(f"/api/jobs/{job_id}").json()
    assert doc["status"] == "done" and doc["cells_to_check"] == 1
    flagged = doc["pages"][0]["rows"][0]["cells"]["In"]
    assert flagged["needs_review"] and flagged["raw_text"] == "07?6" and flagged["value"] is None

    r = client.put(f"/api/jobs/{job_id}/cells", json={"changes": [{"page": 1, "row": 0, "column": "In", "value": "07:26"}]})
    assert r.status_code == 200 and r.json()["cells_to_check"] == 0
    assert r.json()["pages"][0]["rows"][0]["cells"]["In"]["edited"]

    csv = client.get(f"/api/jobs/{job_id}/csv")
    assert csv.status_code == 200 and csv.content.startswith(b"\xef\xbb\xbf") and b"07:26" in csv.content
    assert client.get(f"/api/jobs/{job_id}/pages/1").headers["content-type"] == "image/png"
    assert [j["id"] for j in client.get("/api/jobs").json()] == [job_id]


def test_unusable_file_is_reported_and_others_still_added(client, tmp_path):
    files = [("files", ("notes.docx", b"abc", "x")), ("files", ("ok.png", png_bytes(tmp_path), "x"))]
    r = client.post("/api/jobs", files=files).json()
    assert len(r["created"]) == 1 and r["rejected"][0]["code"] == "FILE_TYPE"
    assert "not a PDF or a picture" in r["rejected"][0]["message"]
    client.jobs.wait_idle(30)


def test_plain_errors_with_codes(client, tmp_path):
    r = client.get("/api/jobs/does-not-exist")
    assert r.status_code == 404 and r.json()["code"] == "JOB_NOT_FOUND"
    assert client.put("/api/jobs/x/cells", content="not json").status_code == 400
    job_id = upload(client, tmp_path).json()["created"][0]["id"]
    client.jobs.wait_idle(30)
    bad = client.put(f"/api/jobs/{job_id}/cells", json={"changes": [{"page": 1, "row": 99, "column": "In", "value": "x"}]})
    assert bad.status_code == 400 and bad.json()["code"] == "BAD_EDIT"
    assert client.get(f"/api/jobs/{job_id}/pages/9").status_code == 404


def test_csv_refused_until_finished(tmp_path):
    def failing(image):
        raise ocr.OcrError("CLAUDE_PLAN_LIMIT", "Plan limit reached.")
    jobs = Jobs(tmp_path / "jobs", reader=failing)
    with TestClient(app_module.create_app(jobs), base_url="http://localhost") as c:
        job_id = upload(c, tmp_path).json()["created"][0]["id"]
        jobs.wait_idle(30)
        r = c.get(f"/api/jobs/{job_id}/csv")
        assert r.status_code == 409 and r.json()["code"] == "JOB_NOT_FINISHED"
        doc = c.get(f"/api/jobs/{job_id}").json()
        assert doc["status"] == "failed" and doc["error"]["code"] == "CLAUDE_PLAN_LIMIT"


def test_other_websites_cannot_use_the_app(client, tmp_path):
    assert client.get("/api/jobs", headers={"host": "evil.example"}).status_code == 403
    r = client.post("/api/login", headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/jobs", headers={"origin": "https://evil.example"},
                    files=[("files", ("a.png", png_bytes(tmp_path), "x"))])
    assert r.status_code == 403 and client.get("/api/jobs").json() == []


def test_status_and_login_use_ocr_module(client, monkeypatch):
    monkeypatch.setattr(ocr, "auth_status", lambda: {"installed": True, "logged_in": True, "email": "a@b.c",
                                                      "plan": "pro", "message": None})
    started = []
    monkeypatch.setattr(ocr, "start_login", lambda: started.append(1))
    assert client.get("/api/status").json()["email"] == "a@b.c"
    assert client.post("/api/login").json() == {"started": True} and started == [1]


# ------------------------------------------------------------------------------------------------ Phase 4: failures
def test_limit_message_that_mentions_login_is_still_a_plan_limit():
    out = '{"is_error": true, "result": "Session limit reached - resets 5pm. Please run /login to switch."}'
    with pytest.raises(ocr.OcrError) as e:
        ocr.parse_cli_output(out)
    assert e.value.code == "CLAUDE_PLAN_LIMIT" and "Continue" in e.value.message


def test_blurry_page_gets_its_own_message(tmp_path):
    def blurry(image):
        rec = record([])
        rec["quality"] = "ILLEGIBLE"
        return rec
    jobs = Jobs(tmp_path / "jobs", reader=blurry)
    with TestClient(app_module.create_app(jobs), base_url="http://localhost") as c:
        job_id = upload(c, tmp_path).json()["created"][0]["id"]
        jobs.wait_idle(30)
        doc = c.get(f"/api/jobs/{job_id}").json()
        assert doc["status"] == "done" and "blurry" in doc["pages"][0]["problem"]


def test_damaged_file_cannot_be_continued_but_plan_limit_can(tmp_path):
    def reader(image):
        raise ocr.OcrError("CLAUDE_PLAN_LIMIT", "limit")
    jobs = Jobs(tmp_path / "jobs", reader=reader)
    with TestClient(app_module.create_app(jobs), base_url="http://localhost") as c:
        bad_id = upload(c, tmp_path, name="broken.pdf", content=b"%PDF-1.4 not really").json()["created"][0]["id"]
        jobs.wait_idle(30)              # (a plan-limit stop would also mark documents still waiting, so run this first)
        good_id = upload(c, tmp_path).json()["created"][0]["id"]
        jobs.wait_idle(30)
        assert c.get(f"/api/jobs/{good_id}").json()["can_continue"] is True
        bad = c.get(f"/api/jobs/{bad_id}").json()
        assert bad["status"] == "failed" and bad["error"]["code"] == "PDF_UNREADABLE" and bad["can_continue"] is False


def test_unexpected_server_error_is_plain_json(tmp_path, monkeypatch):
    jobs = Jobs(tmp_path / "jobs", reader=page_reader)
    monkeypatch.setattr(jobs, "list_jobs", lambda: 1 / 0)
    with TestClient(app_module.create_app(jobs), base_url="http://localhost", raise_server_exceptions=False) as c:
        r = c.get("/api/jobs")
        assert r.status_code == 500 and r.json()["code"] == "UNEXPECTED" and "Traceback" not in r.text


def test_disk_full_on_upload_is_reported(client, tmp_path, monkeypatch):
    def boom(name, content):
        raise OSError("disk full")
    monkeypatch.setattr(client.jobs, "create_job", boom)
    r = upload(client, tmp_path).json()
    assert r["created"] == [] and r["rejected"][0]["code"] == "SAVE_FAILED" and "disk space" in r["rejected"][0]["message"]


def test_cancel_endpoint(tmp_path):
    import threading
    started = threading.Event()

    def slow(image):
        started.set()
        assert ocr._cancel.event.wait(20)
        raise ocr.OcrError("CANCELLED", "cancelled")
    jobs = Jobs(tmp_path / "jobs", reader=slow)
    with TestClient(app_module.create_app(jobs), base_url="http://localhost") as c:
        job_id = upload(c, tmp_path).json()["created"][0]["id"]
        assert started.wait(20)
        assert c.post(f"/api/jobs/{job_id}/cancel").json()["status"] == "failed"
        jobs.wait_idle(30)
        doc = c.get(f"/api/jobs/{job_id}").json()
        assert doc["error"]["code"] == "CANCELLED" and doc["can_continue"] is True
        assert c.post("/api/jobs/nope/cancel").status_code == 404


def test_quit_cancels_active_reading_and_calls_the_exit_hook(tmp_path):
    import threading
    started = threading.Event()

    def slow(image):
        started.set()
        assert ocr._cancel.event.wait(20)
        raise ocr.OcrError("CANCELLED", "cancelled")
    jobs = Jobs(tmp_path / "jobs", reader=slow)
    app = app_module.create_app(jobs)
    closed = []
    app.state.on_quit = lambda: closed.append(1)
    with TestClient(app, base_url="http://localhost") as c:
        job_id = upload(c, tmp_path).json()["created"][0]["id"]
        assert started.wait(20)
        assert c.get("/api/activity").json() == {"active": 1}
        assert c.post("/api/quit").json() == {"quit": True} and closed == [1]
        assert c.get(f"/api/jobs/{job_id}").json()["error"]["code"] == "CANCELLED"
        assert c.get("/api/activity").json() == {"active": 0}


def test_quit_is_refused_from_other_websites(client):
    assert client.post("/api/quit", headers={"origin": "https://evil.example"}).status_code == 403
