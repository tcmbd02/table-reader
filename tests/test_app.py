import pytest
import json
import xlrd
from fastapi.testclient import TestClient
from PIL import Image
from datetime import date

import app as app_module
import ocr
from jobs import Jobs
from tests.helpers import cell, good, make_pdf, record


YEAR = date.today().year                 # file names carry this year's month (a month is only taken near today)


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
    for path in ("/", "/app.js", "/payroll.js", "/companies.js", "/i18n.js", "/app.css"):
        assert client.get(path).headers["cache-control"] == "no-cache", path
    assert client.get("/api/ping").headers["cache-control"] == "no-store"


def test_the_page_has_the_company_first_screens(client):
    html = client.get("/").text
    assert 'id="month"' in html and 'id="company"' in html and "companies.js?v=" in html
    assert html.index("payroll.js") < html.index("companies.js")        # it uses the old page's helpers


def test_script_addresses_change_when_a_script_changes(client, tmp_path, monkeypatch):
    import re
    import shutil

    page = client.get("/").text
    stamped = re.findall(r'(?:src|href)="([\w.-]+)\?v=([0-9a-f]{8})"', page)
    assert [name for name, _ in stamped] == ["app.css", "i18n.js", "app.js", "payroll.js", "companies.js"]
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
        assert view["auto"] == {"added": 1, "skipped": [], "unnamed": [], "from_million": 0, "new_numbers": 1}
        emp = view["plan"]["employees"][0]
        assert emp["name"] == "ALI" and len(emp["jobs"]) == 2
        # a worker with no Employee No. anywhere gets a new one: the company's first 7 letters and the next number
        assert emp["emp_no"] == emp["emp_no_new"] == "MAJUJAY001"
        oct_view = c.post("/api/payroll/2026-10/auto", json={"company": ""}).json()
        october = {e["name"]: e for e in oct_view["plan"]["employees"]}
        assert {n: e["emp_no"] for n, e in october.items()} == {"ALI": "MAJUJAY001", "ZUL": "OTHERCO001"}
        assert "emp_no_new" not in october["ALI"] and october["ZUL"]["emp_no_new"] == "OTHERCO001"   # ALI's is remembered
        emp["emp_no"] = "MJ(1)"
        saved = c.put("/api/payroll/2026-09", json=view["plan"]).json()    # the user types the real one ...
        assert "emp_no_new" not in saved["plan"]["employees"][0]
        nov_view = c.post("/api/payroll/2026-11/auto", json={"company": "MAJU JAYA"}).json()
        assert nov_view["plan"]["employees"][0]["emp_no"] == "MJ(1)"       # ... and that is filled in next month
        # an employee already in a payroll with no number gets one when the month's page is opened, once
        plan = c.get("/api/payroll/2026-09").json()["plan"]
        plan["employees"].append({"id": "byhand1", "emp_no": "", "name": "SITI", "jobs": [], "company": "MAJU JAYA"})
        assert c.put("/api/payroll/2026-09", json=plan).json()["results"][-1]["assign"] == "MAJUJAY002"   # offered ...
        opened = c.get("/api/payroll/2026-09").json()
        assert opened["numbered"] == 1 and opened["plan"]["employees"][-1]["emp_no_new"] == "MAJUJAY002"  # ... then given
        assert c.get("/api/payroll/2026-09").json()["numbered"] == 0
        assert c.post("/api/payroll/2026-09/auto", json={"company": 5}).status_code == 400


def test_a_month_grid_with_several_workers_gives_one_employee_per_row(tmp_path):
    labels = ("Name",) + tuple(str(d) for d in range(1, 32)) + ("Remark",)
    marks = {str(d): good("" if d in (6, 13, 20, 27, 31) else "✓") for d in range(1, 32)}

    def sheet(image):
        return record([{"Name": good(n), **marks, "Remark": good("26")} for n in ("ALI", "AMIN", "ZUL")],
                      labels=labels, header=[("CLEANER NAME", good("ALI"))])

    store = Jobs(tmp_path / "jobs", reader=sheet)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR}.png")
        store.wait_idle()
        view = c.get(f"/api/payroll/{YEAR}-09").json()           # read after the app started: added by itself
        doc = view["documents"][0]
        assert [(p["row"], p["label"]) for p in doc["parts"]] == [(1, "ALI"), (2, "AMIN"), (3, "ZUL")]
        assert doc["parts"][1]["ref"] == doc["id"] + "#p1r2"
        assert view["added_by_themselves"]["added"] == [{"name": n, "cards": 1} for n in ("ALI", "AMIN", "ZUL")]
        assert c.post(f"/api/payroll/{YEAR}-09/auto", json={"company": ""}).json()["auto"]["added"] == 0
        view = c.get(f"/api/payroll/{YEAR}-09").json()
        assert view["added_by_themselves"] is None                 # once only
        assert [e["name"] for e in view["plan"]["employees"]] == ["ALI", "AMIN", "ZUL"]
        assert [r["values"]["days_worked"]["value"] for r in view["results"]] == [26, 26, 26]
        assert all(r["complete"] or {i["kind"] for i in r["issues"]} == {"empno"} for r in view["results"])


# ------------------------------------------------------------------------- files added to their month by themselves
def nine_hour_card(image):
    return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"))


def test_two_cards_of_one_worker_become_one_employee_when_the_month_is_opened(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=nine_hour_card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR} (ALI) (1).png")
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR} (ALI) (2).png")
        upload(c, tmp_path, name="MAJU JAYA ZUL.png")                      # no month anywhere
        store.wait_idle()
        assert c.get(f"/api/payroll/{YEAR}-10").json()["plan"]["employees"] == []      # another month: nothing
        view = c.get(f"/api/payroll/{YEAR}-09").json()
        assert [(e["name"], len(e["jobs"])) for e in view["plan"]["employees"]] == [("MAJU JAYA ALI", 2)]
        added = view["added_by_themselves"]
        assert added["added"] == [{"name": "MAJU JAYA ALI", "cards": 2}] and added["joined"] == []
        assert added["no_month"] == [{"name": "MAJU JAYA ZUL.png",
                                      "why": "no month was found in the file name or on the card"}]
        assert view["results"][0]["values"]["days_worked"]["value"] == 1


def test_a_new_worker_named_on_the_card_gets_millions_employee_no_and_the_mark_goes_when_it_is_changed(tmp_path):
    from tests.helpers import million_listing

    def named_card(image):
        return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"), header=[("Name", good("Ali bin Abu"))])

    store = Jobs(tmp_path / "jobs", reader=named_card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        listing = million_listing([("MJ(1)", "ALI BIN ABU"), ("MJ(2)", "SITI")])
        c.post("/api/million/employees", files={"file": ("rptempepmlist.xls", listing, "application/vnd.ms-excel")})
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR} (1).png")
        store.wait_idle()
        view = c.get(f"/api/payroll/{YEAR}-09").json()
        assert view["added_by_themselves"]["from_million"] == 1
        worker = view["plan"]["employees"][0]
        assert (worker["name"], worker["emp_no"], worker["emp_no_million"]) == ("Ali bin Abu", "MJ(1)", "MJ(1)")
        assert c.get(f"/api/payroll/{YEAR}-09").json()["plan"]["employees"][0]["emp_no_million"] == "MJ(1)"   # saved
        worker["emp_no"] = "MJ(2)"                                          # the user types another number
        saved = c.put(f"/api/payroll/{YEAR}-09", json=view["plan"]).json()
        assert "emp_no_million" not in saved["plan"]["employees"][0]


def test_a_later_card_joins_its_worker_and_a_removed_card_is_not_added_again(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=nine_hour_card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR} (ALI) (1).png")
        store.wait_idle()
        plan = c.get(f"/api/payroll/{YEAR}-09").json()["plan"]
        assert [(e["name"], len(e["jobs"])) for e in plan["employees"]] == [("MAJU JAYA ALI", 1)]
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR} (ALI) (2).png")
        store.wait_idle()
        view = c.get(f"/api/payroll/{YEAR}-09").json()
        assert view["added_by_themselves"]["joined"] == [{"name": "MAJU JAYA ALI", "cards": 1}]
        assert [(e["name"], len(e["jobs"])) for e in view["plan"]["employees"]] == [("MAJU JAYA ALI", 2)]
        plan = view["plan"]
        plan["employees"][0]["jobs"] = plan["employees"][0]["jobs"][:1]   # the user takes a card off
        assert c.put(f"/api/payroll/{YEAR}-09", json=plan).status_code == 200
        view = c.get(f"/api/payroll/{YEAR}-09").json()
        assert view["added_by_themselves"] is None and len(view["plan"]["employees"][0]["jobs"]) == 1


def test_files_already_there_when_the_app_starts_are_left_as_they_are(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=nine_hour_card)
    store.create_job(f"MAJU JAYA SEPT {YEAR} (ALI).png", png_bytes(tmp_path))
    store.wait_idle()
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        view = c.get(f"/api/payroll/{YEAR}-09").json()
        assert view["plan"]["employees"] == [] and view["added_by_themselves"] is None


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
        assert "employee list: MJ(1) MAJU JAYA ALI." in r.json()["message"]
        r = c.get("/api/payroll/2026-09/xls", params={"allow_incomplete": "true", "allow_unknown": "true"})
        assert r.status_code == 200
        listed.write_text("MJ(7)\nmj(1)\n", encoding="utf-8")                # added to the list: no question
        assert c.get("/api/payroll/2026-09/xls", params={"allow_incomplete": "true"}).status_code == 200


def test_millions_employee_list_is_imported_offered_and_checked_before_download(tmp_path):
    from tests.helpers import million_listing

    def card(image):
        return record([{"Date": good("1"), "Total": good("9")}], labels=("Date", "Total"))

    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        assert c.get("/api/payroll/2026-09").json()["million"] is None
        r = c.post("/api/million/employees", files={"file": ("notes.xls", b"hello", "application/vnd.ms-excel")})
        assert r.status_code == 400 and r.json()["code"] == "MILLION_LIST"
        listing = million_listing([("MJ(1)", "SITI"), ("MJ(2)", "ALI")])
        r = c.post("/api/million/employees", files={"file": ("rptempepmlist.xls", listing, "application/vnd.ms-excel")})
        assert r.status_code == 200 and [(e["emp_no"], e["name"]) for e in r.json()["employees"]] == [("MJ(1)", "SITI"),
                                                                                                      ("MJ(2)", "ALI")]
        assert c.get("/api/payroll/2026-09").json()["million"]["source"] == "rptempepmlist.xls"
        saved = json.loads((tmp_path / "payroll" / "million-employees.json").read_text(encoding="utf-8"))
        assert set(saved) == {"imported", "source", "employees"} and set(saved["employees"][0]) == {"emp_no", "name", "basic_rate"}

        upload(c, tmp_path, name="MAJU JAYA ALI SEPT 26.png")
        store.wait_idle()
        view = c.post("/api/payroll/2026-09/auto", json={"company": ""}).json()
        ok = {"allow_incomplete": "true"}
        for emp_no, code in (("MJ(7)", "MILLION_UNKNOWN"), ("MJ(1)", "MILLION_NAME")):     # not in Million / someone else
            view["plan"]["employees"][0]["emp_no"] = emp_no
            c.put("/api/payroll/2026-09", json=view["plan"])
            r = c.get("/api/payroll/2026-09/xls", params=ok)
            assert r.status_code == 400 and r.json()["code"] == code, r.json()
        assert "MJ(1) MAJU JAYA ALI (in Million: SITI)" in r.json()["message"]
        assert c.get("/api/payroll/2026-09/xls", params={**ok, "allow_names": "true"}).status_code == 200
        view["plan"]["employees"][0]["emp_no"] = "mj(2)"                 # the right person: no question
        c.put("/api/payroll/2026-09", json=view["plan"])
        assert c.get("/api/payroll/2026-09/xls", params=ok).status_code == 200


def test_the_month_run_makes_one_file_and_lists_who_is_held_back(tmp_path):
    from tests.helpers import million_listing

    def card(image):
        return record([{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)], labels=("Date", "Total"))

    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        assert c.post("/api/payroll/2026-09/run").json()["code"] == "PAYROLL_EMPTY"
        listing = million_listing([("MJ(1)", "ALI"), ("MJ(2)", "SITI")])
        c.post("/api/million/employees", files={"file": ("rptempepmlist.xls", listing, "application/vnd.ms-excel")})
        for name in ("MAJU JAYA ALI SEPT 26.png", "BINA SITI SEPT 26.png", "BINA ZUL SEPT 26.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        view = c.post("/api/payroll/2026-09/auto", json={"company": ""}).json()
        suggested = {r["name"]: r["suggest"] for r in view["results"]}
        assert suggested["MAJU JAYA ALI"] == {"emp_no": "MJ(1)", "name": "ALI"} and suggested["BINA ZUL"] is None
        for e in view["plan"]["employees"]:                              # the user accepts the two suggestions
            e["emp_no"] = (suggested[e["name"]] or {}).get("emp_no", "")
        saved = c.put("/api/payroll/2026-09", json=view["plan"]).json()
        assert all(r["suggest"] is None for r in saved["results"])        # nothing left to offer
        run = c.post("/api/payroll/2026-09/run").json()
        assert run["file"] == "Payroll 2026-09 (Million).xls" and run["ready"] == 2 and run["held"] == 1
        assert run["checked_with_million"] is True and len(run["companies"]) >= 1
        held = [h for comp in run["companies"] for h in comp["held"]]
        assert held == [{"emp_no": "", "name": "BINA ZUL",
                         "reasons": ["Employee No. is empty. Type it exactly as in Million Payroll."]}]
        sheet = xlrd.open_workbook(str(tmp_path / "payroll" / run["file"])).sheet_by_index(0)
        assert [sheet.cell_value(r, 0) for r in range(1, sheet.nrows)] == ["MJ(1)", "MJ(2)"]


def test_basic_pay_table_download(tmp_path):
    def card(image):
        return record([{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)], labels=("Date", "Total"))

    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name="MAJU JAYA ALI SEPT 26.png")
        store.wait_idle()
        view = c.post("/api/payroll/2026-09/auto", json={"company": ""}).json()
        view["plan"]["employees"][0].update(emp_no="MJ(1)", pay_basis="daily", basic_rate=70)
        saved = c.put("/api/payroll/2026-09", json=view["plan"]).json()
        days = saved["results"][0]["values"]["days_worked"]["value"]
        assert saved["plan"]["employees"][0]["basic_rate"] == 70.0 and saved["results"][0]["pay"]["basic"] == 70 * days
        r = c.get("/api/payroll/2026-09/basic-pay")
        assert r.status_code == 200 and "Basic%20pay%202026-09.csv" in r.headers["content-disposition"]
        lines = r.content.decode("utf-8-sig").splitlines()
        assert lines[1].split(",")[1:8] == ["MJ(1)", "MAJU JAYA ALI", "Daily", "70.00", "Table Reader", f"{days:.2f}", f"{70 * days:.2f}"]
        assert (tmp_path / "payroll" / "Basic pay 2026-09.csv").is_file()


def test_pay_basis_and_rate_come_from_millions_report_until_typed(tmp_path):
    from tests.helpers import million_listing

    def card(image):
        return record([{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)], labels=("Date", "Total"))

    store = Jobs(tmp_path / "jobs", reader=card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        listing = million_listing([("MJ(1)", "ALI", "MAJU JAYA", "Daily", 60.0)], title_col=1)
        c.post("/api/million/employees", files={"file": ("rptemppsnlist.xls", listing, "application/vnd.ms-excel")})
        upload(c, tmp_path, name="MAJU JAYA ALI SEPT 26.png")
        store.wait_idle()
        view = c.post("/api/payroll/2026-09/auto", json={"company": ""}).json()
        assert view["results"][0]["rate_source"] is None                 # no Employee No. yet: nobody to look up
        view["plan"]["employees"][0]["emp_no"] = "mj(1)"
        r = c.put("/api/payroll/2026-09", json=view["plan"]).json()["results"][0]
        assert (r["pay_basis"], r["basic_rate"], r["rate_source"]) == ("daily", 60.0, "million")
        assert r["pay"]["basic"] == 60.0 * r["values"]["days_worked"]["value"] and r["million"]["branch"] == "MAJU JAYA"
        view["plan"]["employees"][0].update(pay_basis="monthly", basic_rate=1500)
        r = c.put("/api/payroll/2026-09", json=view["plan"]).json()["results"][0]
        assert (r["pay_basis"], r["rate_source"], r["pay"]["basic"]) == ("monthly", "typed", 1500.0)


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


# ------------------------------------------------------------------------------------ payroll by company
def company_client(tmp_path, reader):
    store = Jobs(tmp_path / "jobs", reader=reader)
    return store, TestClient(app_module.create_app(store), base_url="http://localhost")


def set_company(c, starts, company):
    for j in c.get("/api/jobs").json():
        if j["name"].startswith(starts):
            c.put(f"/api/jobs/{j['id']}/company", json={"company": company})


def month_card(image):
    return record([{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)], labels=("Date", "Total"))


def import_million(c, *people):
    """Million's employee list with these (Employee No., name): the numbers Table Reader makes are then known."""
    from tests.helpers import million_listing

    listing = million_listing(list(people))
    assert c.post("/api/million/employees",
                  files={"file": ("rptempepmlist.xls", listing, "application/vnd.ms-excel")}).status_code == 200


def accept_offers(c, month, company):
    """The user presses "Use ..." on every Employee No. that Million's list offers in this company."""
    view = c.get(f"/api/payroll/{month}/company", params={"name": company}).json()
    for item in view["items"]:
        if item["kind"] == "offer":
            url = f"/api/payroll/{month}/employees/{item['employee']}"
            assert c.put(url, json={"emp_no": item["emp_no"]}).json() == {"ok": True}


def test_the_overview_and_a_company_screen(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        import_million(c, ("ABM001", "ALI"), ("BINA001", "SITI"))
        for name in (f"A & B (M) ALI SEPT {YEAR}.png", f"BINA SITI SEPT {YEAR}.png", "BINA ZUL.png", "LOOSE.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        set_company(c, "A & B", "A & B (M)")
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        rows = {r["company"]: r for r in c.get(f"/api/payroll/{month}/companies").json()["companies"]}
        assert rows["A & B (M)"]["status"] == "needs"                  # Million's list offers a number: one click
        accept_offers(c, month, "A & B (M)")
        accept_offers(c, month, "BINA")
        over = c.get(f"/api/payroll/{month}/companies").json()
        rows = {r["company"]: r for r in over["companies"]}
        assert set(rows) == {"A & B (M)", "BINA", ""}
        assert rows["A & B (M)"]["employees"] == 1 and rows["A & B (M)"]["status"] == "ready"
        assert rows["BINA"]["employees"] == 1 and rows["BINA"]["status"] == "needs"     # a file of BINA has no month
        assert rows[""]["status"] == "needs" and rows[""]["employees"] == 0     # a file with no company is not lost
        assert over["checked_with_million"] is True
        # a company name with signs opens through the query string
        view = c.get(f"/api/payroll/{month}/company", params={"name": "A & B (M)"}).json()
        assert view["company"] == "A & B (M)" and view["month"] == month
        assert [(e["name"], e["emp_no"], e["status"]) for e in view["employees"]] == [("ALI", "ABM001", "ready")]
        assert view["items"] == [] and isinstance(view["employees"][0]["days_worked"], (int, float))
        bina = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert [i["kind"] for i in bina["items"]] == ["month"]
        assert bina["items"][0]["name"] == "BINA ZUL.png" and "why" in bina["items"][0]
        loose = c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()
        assert [f["name"] for f in loose["files"]] == ["LOOSE.png"]


def test_a_file_gets_its_month_and_its_card_is_placed(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        import_million(c, ("BINA001", "SITI"), ("BINA002", "ZUL"))
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        upload(c, tmp_path, name="BINA ZUL.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        item = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"][0]
        assert c.post("/api/payroll/file-month", json={"id": item["doc"], "month": "2026-13"}).status_code == 400
        assert c.post("/api/payroll/file-month", json={"id": "nope", "month": month}).status_code in (400, 404)
        assert c.post("/api/payroll/file-month", json={"id": item["doc"], "month": month}).json() == {"ok": True}
        accept_offers(c, month, "BINA")
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        # read after the app started and now of this month: it joined by itself, as its own employee
        assert sorted(e["name"] for e in view["employees"]) == ["SITI", "ZUL"] and view["items"] == []
        # "not a time card": never asked about again, in any month
        upload(c, tmp_path, name="BINA NOTICE.png")
        store.wait_idle()
        set_company(c, "BINA NOTICE", "BINA")
        item = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"][0]
        assert item["kind"] == "month" and item["name"] == "BINA NOTICE.png"
        c.post("/api/payroll/file-month", json={"id": item["doc"], "month": "none"})
        assert c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"] == []
        assert c.get(f"/api/payroll/{YEAR}-10/company", params={"name": "BINA"}).json()["items"] == []


def test_placing_a_card_and_refusing_one_that_is_taken(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        siti = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["employees"][0]
        plan = c.get(f"/api/payroll/{month}").json()["plan"]
        ref = plan["employees"][0]["jobs"][0]
        plan["employees"][0]["jobs"] = []                                # the user takes the card off
        c.put(f"/api/payroll/{month}", json=plan)
        items = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"]
        assert [(i["kind"], i.get("ref")) for i in items if i["kind"] == "unplaced"] == [("unplaced", ref)]
        assert c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": None}).json()["ok"] is True
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert len(view["employees"]) == 2 and not [i for i in view["items"] if i["kind"] == "unplaced"]
        # placed on the new employee already: putting it on SITI as well is refused and changes nothing
        r = c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti["id"]})
        assert r.status_code == 400 and "one employee only" in r.json()["message"]
        assert c.get(f"/api/payroll/{month}").json()["plan"]["employees"][0]["jobs"] == []
        assert c.post(f"/api/payroll/{month}/place", json={"ref": "nope", "employee": None}).status_code in (400, 404)
        assert c.post(f"/api/payroll/{month}/place", json={"ref": ref}).status_code == 400          # no "employee" key


def test_an_offered_employee_no_is_set_with_one_call(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        import_million(c, ("MJ(1)", "ALI"), ("MJ(2)", "SITI"))
        upload(c, tmp_path, name=f"MAJU JAYA ALI SEPT {YEAR}.png")
        store.wait_idle()
        month = f"{YEAR}-09"                                             # no company: no new number is made
        view = c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()
        offer = [i for i in view["items"] if i["kind"] == "offer"][0]
        assert offer["emp_no"] == "MJ(1)" and offer["million_name"] == "ALI"
        url = f"/api/payroll/{month}/employees/{offer['employee']}"
        assert c.put(url, json={"emp_no": 5}).status_code == 400
        assert c.put(f"/api/payroll/{month}/employees/nobody", json={"emp_no": "MJ(1)"}).status_code == 400
        assert c.put(url, json={"emp_no": "MJ(1)"}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()
        assert view["employees"][0]["emp_no"] == "MJ(1)" and view["employees"][0]["status"] == "ready"
        assert c.get(f"/api/payroll/{month}/companies").json()["checked_with_million"] is True


def test_the_overview_opens_when_a_file_is_being_read_or_its_reading_is_gone(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        upload(c, tmp_path, name=f"BINA ZUL SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        assert c.get(f"/api/payroll/{month}/companies").json()["companies"][0]["employees"] == 2
        gone = [j for j in c.get("/api/jobs").json() if "ZUL" in j["name"]][0]
        (store.root / gone["id"] / "result.json").write_text("{ damaged", encoding="utf-8")   # cannot be loaded any more
        over = c.get(f"/api/payroll/{month}/companies")
        assert over.status_code == 200 and over.json()["companies"][0]["company"] == "BINA"
        assert c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).status_code == 200


def test_the_overview_opens_on_a_month_whose_stored_plan_cannot_be_saved_as_it_is(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        c.get(f"/api/payroll/{month}/companies")
        path = tmp_path / "payroll" / f"{month}.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["employees"].append(dict(plan["employees"][0], id="twin1"))    # one card on two employees: old, bad data
        path.write_text(json.dumps(plan), encoding="utf-8")
        over = c.get(f"/api/payroll/{month}/companies")
        assert over.status_code == 200 and over.json()["companies"][0]["employees"] == 2


def test_an_old_bad_plan_is_left_alone_when_a_new_file_of_the_month_arrives(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        c.get(f"/api/payroll/{month}/companies")
        path = tmp_path / "payroll" / f"{month}.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["employees"].append(dict(plan["employees"][0], id="twin1"))    # one card on two employees: old, bad data
        path.write_text(json.dumps(plan), encoding="utf-8")
        upload(c, tmp_path, name=f"BINA ZUL SEPT {YEAR}.png")               # and now a new file of the month is read
        store.wait_idle()
        set_company(c, "BINA ZUL", "BINA")
        over = c.get(f"/api/payroll/{month}/companies")
        assert over.status_code == 200, over.json()
        assert c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).status_code == 200
        assert c.get(f"/api/payroll/{month}").status_code == 200           # the old page, where it can be put right
        # nothing was added to the plan that cannot be saved, and no number was remembered for someone not in it
        assert len(json.loads(path.read_text(encoding="utf-8"))["employees"]) == 2
        remembered = json.loads((tmp_path / "payroll" / "employees.json").read_text(encoding="utf-8"))
        assert not [k for k in remembered if "zul" in k]
        # once the plan is put right, the waiting file joins by itself
        plan = c.get(f"/api/payroll/{month}").json()["plan"]
        plan["employees"] = plan["employees"][:1]
        assert c.put(f"/api/payroll/{month}", json=plan).status_code == 200
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert sorted(e["name"] for e in view["employees"]) == ["SITI", "ZUL"]


def test_placing_a_card_works_while_another_reading_is_damaged(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        upload(c, tmp_path, name=f"BINA ZUL SEPT {YEAR}.png")
        upload(c, tmp_path, name=f"BINA AMIN SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        plan = c.get(f"/api/payroll/{month}").json()["plan"]
        siti = next(e for e in plan["employees"] if e["name"] == "SITI")
        ref, siti["jobs"] = siti["jobs"][0], []                           # the user takes SITI's card off
        c.put(f"/api/payroll/{month}", json=plan)
        for j in c.get("/api/jobs").json():                               # every other reading is damaged
            if "SITI" not in j["name"]:
                (store.root / j["id"] / "result.json").write_text("{ damaged", encoding="utf-8")
        r = c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti["id"]})
        assert r.status_code == 200 and r.json()["ok"] is True, r.json()
        damaged = next(j["id"] for j in c.get("/api/jobs").json() if "ZUL" in j["name"])
        r = c.post(f"/api/payroll/{month}/place", json={"ref": damaged, "employee": siti["id"]})
        assert r.status_code in (400, 404) and "could not be opened" in r.json()["message"]


def test_a_card_that_is_nobodys_can_be_set_aside_as_not_a_time_card(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        plan = c.get(f"/api/payroll/{month}").json()["plan"]
        plan["employees"] = []                                            # the employee is removed: the card is nobody's
        c.put(f"/api/payroll/{month}", json=plan)
        item = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"][0]
        assert item["kind"] == "unplaced" and item["doc"] == item["ref"]
        assert c.post("/api/payroll/file-month", json={"id": item["doc"], "month": "none"}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert view["items"] == [] and view["employees"] == []           # and it does not come back by itself
