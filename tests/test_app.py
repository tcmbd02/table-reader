import pytest
import xlrd
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


def test_browser_must_not_keep_an_old_script_after_an_update(client):
    for path in ("/", "/app.js", "/payroll.js", "/i18n.js", "/app.css"):
        assert client.get(path).headers["cache-control"] == "no-cache", path
    assert client.get("/api/ping").headers["cache-control"] == "no-store"


def test_script_addresses_change_when_a_script_changes(client, tmp_path, monkeypatch):
    import re
    import shutil

    page = client.get("/").text
    stamped = re.findall(r'(?:src|href)="([\w.-]+)\?v=([0-9a-f]{8})"', page)
    assert [name for name, _ in stamped] == ["app.css", "i18n.js", "app.js", "payroll.js"]
    assert client.get("/index.html").text == page
    assert all(client.get(f"/{name}?v={v}").status_code == 200 for name, v in stamped)

    copy = tmp_path / "static"
    shutil.copytree(app_module.static_dir(), copy)
    (copy / "payroll.js").write_text("// an update\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "static_dir", lambda: copy)
    after = dict(re.findall(r'(?:src|href)="([\w.-]+)\?v=([0-9a-f]{8})"', app_module.page_html()))
    before = dict(stamped)
    assert after["payroll.js"] != before["payroll.js"] and after["app.js"] == before["app.js"]


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


# ------------------------------------------------------------------------------------------------------- payroll
def card_reader(image):
    rows = [{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31) if d not in (6, 13, 20, 27)]
    return record(rows, labels=("Date", "Total"))


def test_payroll_screen_api_end_to_end(tmp_path):
    jobs = Jobs(tmp_path / "jobs", reader=card_reader)
    with TestClient(app_module.create_app(jobs), base_url="http://localhost") as c:
        job_id = upload(c, tmp_path, name="card.png").json()["created"][0]["id"]
        jobs.wait_idle(30)

        view = c.get("/api/payroll/2026-09").json()                      # nothing saved yet: defaults
        assert view["plan"]["day_types"]["6"] == "rest" and view["plan"]["employees"] == []
        assert [d["id"] for d in view["documents"]] == [job_id]
        assert [f["key"] for f in view["fields"]][:3] == ["working_days", "public_holiday", "days_worked"]

        plan = view["plan"]
        plan["day_types"]["16"] = "holiday"
        plan["employees"] = [{"id": "e1", "emp_no": "AF(1)", "name": "Test", "jobs": [job_id], "hours_column": None,
                              "overrides": {"lateness": 2}}]
        saved = c.put("/api/payroll/2026-09", json=plan).json()
        r = saved["results"][0]
        assert r["columns"] == ["Date", "Total"] and r["complete"]
        assert r["values"]["working_days"]["value"] == 25 and r["values"]["days_worked"]["value"] == 25
        assert r["values"]["ot_holiday"]["value"] == 1 and r["values"]["lateness"]["edited"]

        assert c.get("/api/payroll/2026-09").json()["plan"]["day_types"]["16"] == "holiday"     # persisted
        csv = c.get("/api/payroll/2026-09/csv")
        assert csv.status_code == 200 and csv.content.startswith(b"\xef\xbb\xbfEmployee No.,Name,Month End Pay")
        assert b"AF(1),Test" in csv.content and b"25.00" in csv.content


def test_payroll_api_refuses_bad_input(client, tmp_path):
    assert client.get("/api/payroll/nonsense").status_code == 400
    plan = client.get("/api/payroll/2026-09").json()["plan"]
    assert client.get("/api/payroll/2026-09/csv").json()["code"] == "PAYROLL_EMPTY"
    plan["employees"] = [{"id": "e1", "emp_no": "1", "name": "", "jobs": ["does-not-exist"]}]
    r = client.put("/api/payroll/2026-09", json=plan)                 # a gone document is taken off, not an error
    assert r.status_code == 200 and r.json()["plan"]["employees"][0]["jobs"] == []
    assert client.put("/api/payroll/2026-09", content="x").status_code == 400
    assert client.put("/api/payroll/2026-09", json=plan, headers={"origin": "https://evil.example"}).status_code == 403


def test_company_can_be_set_and_is_listed(client, tmp_path):
    job = upload(client, tmp_path, name="MAJU JAYA ALI SEPT 26.png").json()["created"][0]
    r = client.put(f"/api/jobs/{job['id']}/company", json={"company": "MAJU JAYA"})
    assert r.status_code == 200 and r.json() == {"moved": 0}
    assert client.get("/api/jobs").json()[0]["company"] == "MAJU JAYA"
    assert client.put(f"/api/jobs/{job['id']}/company", json={"company": 5}).status_code == 400
    assert client.put("/api/jobs/nope/company", json={"company": "X"}).status_code == 404


def test_payroll_file_picker_gets_the_company_of_each_file(client, tmp_path):
    job = upload(client, tmp_path, name="MAJU JAYA ALI SEPT 26.png").json()["created"][0]
    client.put(f"/api/jobs/{job['id']}/company", json={"company": "MAJU JAYA"})
    client.app.state.jobs.wait_idle()
    docs = client.get("/api/payroll/2026-09").json()["documents"]
    assert [d["company"] for d in docs if d["id"] == job["id"]] == ["MAJU JAYA"]


def test_payroll_saves_even_when_a_ticked_time_card_no_longer_exists(client, tmp_path):
    """History reset / deleted document: the old tick must not block every later save."""
    job = upload(client, tmp_path, name="card.png").json()["created"][0]
    client.app.state.jobs.wait_idle()
    plan = client.get("/api/payroll/2026-09").json()["plan"]
    plan["employees"] = [{"id": "e1", "emp_no": "MJ(1)", "name": "", "jobs": ["gone-job", job["id"]],
                          "hours_column": None, "overrides": {}}]
    r = client.put("/api/payroll/2026-09", json=plan)
    assert r.status_code == 200
    view = r.json()
    assert view["plan"]["employees"][0]["jobs"] == [job["id"]]
    assert view["results"][0]["issues"][0]["kind"] == "removed"
    assert "no longer in Recent files" in view["results"][0]["issues"][0]["text"]


def test_payroll_uses_only_the_chosen_workers_page_of_a_report(tmp_path):
    def two_workers(image):
        n = two_workers.calls = getattr(two_workers, "calls", 0) + 1
        return record([{"Date": good("01-09-2026"), "Shift Details / Actual": good("8.00"),
                        "OverTime / 1.5": good("1.50" if n == 1 else "3.00")}],
                      labels=("Date", "Shift Details / Actual", "OverTime / 1.5"),
                      header=[("Emp Code", good(f"E0{n}")), ("Name", good(f"W{n}"))])

    store = Jobs(tmp_path / "jobs", reader=two_workers)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        src = tmp_path / "report.pdf"
        make_pdf(src, 2)
        job = c.post("/api/jobs", files=[("files", ("report.pdf", src.read_bytes(), "application/pdf"))]).json()["created"][0]
        store.wait_idle()
        view = c.get("/api/payroll/2026-09").json()
        doc = [d for d in view["documents"] if d["id"] == job["id"]][0]
        assert [p["label"] for p in doc["parts"]] == ["E01 W1", "E02 W2"]
        plan = view["plan"]
        plan["employees"] = [{"id": "e1", "emp_no": "1", "name": "", "jobs": [doc["parts"][1]["ref"]],
                              "hours_column": None, "overrides": {}}]
        r = c.put("/api/payroll/2026-09", json=plan).json()["results"][0]
        assert r["values"]["ot_1_5"]["value"] == 3.0 and r["values"]["days_worked"]["value"] == 1


def test_add_employees_from_files_of_a_company(tmp_path):
    def card(image):
        return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"))

    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        for name in ("MAJU JAYA ALI SEPT 26.png", "MAJU JAYA ALI SEPT 26 2.png", "OTHER CO ZUL SEPT 26.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        for j in c.get("/api/jobs").json():
            c.put(f"/api/jobs/{j['id']}/company", json={"company": "MAJU JAYA" if j["name"].startswith("MAJU") else "OTHER CO"})
        view = c.post("/api/payroll/2026-09/auto", json={"company": "MAJU JAYA"}).json()
        assert view["auto"] == {"added": 1, "skipped": [], "unnamed": []}
        emp = view["plan"]["employees"][0]
        assert emp["name"] == "ALI" and len(emp["jobs"]) == 2 and emp["emp_no"] == ""
        emp["emp_no"] = "MJ(1)"
        c.put("/api/payroll/2026-09", json=view["plan"])                  # typed once ...
        oct_view = c.post("/api/payroll/2026-10/auto", json={"company": "MAJU JAYA"}).json()
        assert oct_view["plan"]["employees"][0]["emp_no"] == "MJ(1)"       # ... filled in next month
        assert c.post("/api/payroll/2026-09/auto", json={"company": 5}).status_code == 400


def test_a_month_grid_with_several_workers_gives_one_employee_per_row(tmp_path):
    labels = ("Name",) + tuple(str(d) for d in range(1, 32)) + ("Remark",)
    marks = {str(d): good("" if d in (6, 13, 20, 27, 31) else "✓") for d in range(1, 32)}

    def sheet(image):
        return record([{"Name": good(n), **marks, "Remark": good("26")} for n in ("ALI", "AMIN", "ZUL")],
                      labels=labels, header=[("CLEANER NAME", good("ALI"))])

    store = Jobs(tmp_path / "jobs", reader=sheet)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name="MAJU JAYA SEPT 26.png")
        store.wait_idle()
        doc = c.get("/api/payroll/2026-09").json()["documents"][0]
        assert [(p["row"], p["label"]) for p in doc["parts"]] == [(1, "ALI"), (2, "AMIN"), (3, "ZUL")]
        assert doc["parts"][1]["ref"] == doc["id"] + "#p1r2"
        view = c.post("/api/payroll/2026-09/auto", json={"company": ""}).json()
        assert view["auto"]["added"] == 3
        assert [e["name"] for e in view["plan"]["employees"]] == ["ALI", "AMIN", "ZUL"]
        assert [r["values"]["days_worked"]["value"] for r in view["results"]] == [26, 26, 26]
        assert all(r["complete"] or {i["kind"] for i in r["issues"]} == {"empno"} for r in view["results"])


def test_million_xls_download_refuses_then_allows_incomplete(tmp_path):
    def card(image):
        return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"))

    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name="MAJU JAYA ALI SEPT 26.png")
        store.wait_idle()
        view = c.post("/api/payroll/2026-09/auto", json={"company": ""}).json()
        r = c.get("/api/payroll/2026-09/xls")
        assert r.status_code == 400 and r.json()["code"] == "MILLION_REFUSED"            # no Employee No. yet
        assert "ALI: Employee No. is empty" in r.json()["message"]
        view["plan"]["employees"][0]["emp_no"] = "MJ(1)"
        c.put("/api/payroll/2026-09", json=view["plan"])
        r = c.get("/api/payroll/2026-09/xls")                             # one card: most days have no entry
        assert r.status_code == 400 and r.json()["code"] == "MILLION_INCOMPLETE"
        r = c.get("/api/payroll/2026-09/xls", params={"allow_incomplete": "true"})
        assert r.status_code == 200 and r.headers["content-type"] == "application/vnd.ms-excel"
        assert "Payroll%202026-09%20%28Million%29.xls" in r.headers["content-disposition"]
        sheet = xlrd.open_workbook(file_contents=r.content).sheet_by_index(0)
        assert sheet.cell_value(1, 0) == "MJ(1)" and sheet.cell_value(1, 51).startswith("INCOMPLETE")
        saved = tmp_path / "payroll" / "Payroll 2026-09 (Million).xls"
        assert saved.read_bytes() == r.content                              # a copy is kept in the payroll folder


def test_million_xls_download_asks_about_an_employee_no_that_is_not_in_employees_txt(tmp_path, monkeypatch):
    def card(image):
        return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"))

    listed = tmp_path / "employees.txt"
    listed.write_text("MJ(7)\n", encoding="utf-8")
    monkeypatch.setenv("TABLE_READER_MILLION_EMPLOYEES", str(listed))
    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name="MAJU JAYA ALI SEPT 26.png")
        store.wait_idle()
        view = c.post("/api/payroll/2026-09/auto", json={"company": ""}).json()
        view["plan"]["employees"][0]["emp_no"] = "MJ(1)"
        c.put("/api/payroll/2026-09", json=view["plan"])
        r = c.get("/api/payroll/2026-09/xls", params={"allow_incomplete": "true"})
        assert r.status_code == 400 and r.json()["code"] == "MILLION_UNKNOWN"
        assert "(employees.txt): MJ(1) MAJU JAYA ALI." in r.json()["message"]
        r = c.get("/api/payroll/2026-09/xls", params={"allow_incomplete": "true", "allow_unknown": "true"})
        assert r.status_code == 200
        listed.write_text("MJ(7)\nmj(1)\n", encoding="utf-8")                # added to the list: no question
        assert c.get("/api/payroll/2026-09/xls", params={"allow_incomplete": "true"}).status_code == 200


def test_payroll_csv_for_one_company(tmp_path):
    def card(image):
        return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"))

    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        for name in ("MAJU JAYA ALI SEPT 26.png", "OTHER CO ZUL SEPT 26.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        for j in c.get("/api/jobs").json():
            c.put(f"/api/jobs/{j['id']}/company", json={"company": " ".join(j["name"].split()[:2])})
        c.post("/api/payroll/2026-09/auto", json={"company": ""})            # both companies
        everyone = c.get("/api/payroll/2026-09/csv").content.decode("utf-8-sig").splitlines()
        one = c.get("/api/payroll/2026-09/csv", params={"company": "MAJU JAYA"})
        lines = one.content.decode("utf-8-sig").splitlines()
        assert len(everyone) == 3 and len(lines) == 2 and ",ALI," in lines[1]
        assert "Payroll%202026-09%20MAJU%20JAYA.csv" in one.headers["content-disposition"]
        assert c.get("/api/payroll/2026-09/csv", params={"company": "NOBODY"}).json()["code"] == "PAYROLL_EMPTY"
