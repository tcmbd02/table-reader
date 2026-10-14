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
    for path in ("/", "/app.js", "/paycommon.js", "/companies.js", "/employee.js", "/paytable.js", "/settings.js",
                 "/look.js", "/i18n.js", "/app.css"):
        assert client.get(path).headers["cache-control"] == "no-cache", path
    assert client.get("/api/ping").headers["cache-control"] == "no-store"


def test_the_page_has_the_company_first_screens(client):
    html = client.get("/").text
    assert 'id="month"' in html and 'id="company"' in html and "companies.js?v=" in html
    assert 'id="payroll"' not in html and "payroll.js" not in html     # the old payroll page is gone
    assert "Old payroll page" not in html and 'id="mo-old"' not in html
    assert 'id="look"' in html and html.index("companies.js") < html.index("look.js?v=")     # the one-look panel
    assert html.index("companies.js") < html.index("settings.js?v=") < html.index("look.js")  # month / company settings
    assert 'id="mo-settings"' in html and 'id="co-settings"' in html
    assert 'id="co-million"' in html and 'id="co-million-open"' in html                # New in Million
    assert 'id="mo-csv"' in html and 'id="co-csv"' in html                              # payroll CSV on both screens
    assert 'id="layout"' in html and html.index("companies.js") < html.index("layout.js?v=")   # card layouts
    # the employee view, with the helpers it shares with the company screens loaded before both
    assert 'id="employee"' in html and html.index("app.js?v=") < html.index("paycommon.js") < html.index("companies.js")
    assert html.index("companies.js") < html.index("employee.js?v=")
    # the company screen's Pay preview tab and Add employee
    assert 'id="co-pay"' in html and 'id="co-tab-pay"' in html and 'id="co-add"' in html
    assert html.index("employee.js") < html.index("paytable.js?v=")


def test_the_company_chooser_for_files_is_on_the_start_page_only(client):
    html = client.get("/").text
    at = html.index('id="company-box"')
    assert html.index('<main id="home"') < at < html.index('<main id="doc"')    # with Recent files, which it filters
    assert 'id="pr-company-box"' not in html                            # the old payroll page (and its chooser) is gone


def test_script_addresses_change_when_a_script_changes(client, tmp_path, monkeypatch):
    import re
    import shutil

    page = client.get("/").text
    stamped = re.findall(r'(?:src|href)="([\w.-]+)\?v=([0-9a-f]{8})"', page)
    assert [name for name, _ in stamped] == ["app.css", "i18n.js", "app.js", "paycommon.js", "companies.js", "employee.js",
                                             "paytable.js", "settings.js", "look.js", "layout.js"]
    assert client.get("/index.html").text == page
    assert all(client.get(f"/{name}?v={v}").status_code == 200 for name, v in stamped)

    copy = tmp_path / "static"
    shutil.copytree(app_module.static_dir(), copy)
    (copy / "companies.js").write_text("// an update\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "static_dir", lambda: copy)
    after = dict(re.findall(r'(?:src|href)="([\w.-]+)\?v=([0-9a-f]{8})"', app_module.page_html()))
    before = dict(stamped)
    assert after["companies.js"] != before["companies.js"] and after["app.js"] == before["app.js"]


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
    store = Jobs(tmp_path / "jobs", reader=card_reader)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name=f"MAJU JAYA TEST SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "MAJU JAYA", "MAJU JAYA")
        month = f"{YEAR}-09"
        default = c.get(f"/api/payroll/{month}/companies").json()["settings"]      # opened: the card joins by itself
        assert default["day_types"]["6"] == "rest"
        default["day_types"]["16"] = "holiday"
        assert c.put(f"/api/payroll/{month}/settings", json=default).json() == {"ok": True}
        who = employee_named(c, month, "TEST")["id"]
        view = change(c, month, who, emp_no="AF(1)", overrides={"lateness": 2}).json()
        r = view["result"]
        assert r["columns"] == ["Date", "Total"] and r["complete"]
        assert [f["key"] for f in view["fields"]][:3] == ["working_days", "public_holiday", "days_worked"]
        assert r["values"]["working_days"]["value"] == 25 and r["values"]["days_worked"]["value"] == 25
        assert r["values"]["ot_holiday"]["value"] == 1 and r["values"]["lateness"]["edited"]

        assert c.get(f"/api/payroll/{month}/companies").json()["settings"]["day_types"]["16"] == "holiday"   # persisted
        csv = c.get(f"/api/payroll/{month}/csv")
        assert csv.status_code == 200 and csv.content.startswith(b"\xef\xbb\xbfEmployee No.,Name,Month End Pay")
        assert b"AF(1),TEST" in csv.content and b"25.00" in csv.content


def test_payroll_api_refuses_bad_input(client, tmp_path):
    assert client.get("/api/payroll/nonsense/companies").status_code == 400
    assert client.get("/api/payroll/2026-09/csv").json()["code"] == "PAYROLL_EMPTY"
    new = client.post("/api/payroll/2026-09/employee", json={"company": ""}).json()["employee"]
    assert client.put(f"/api/payroll/2026-09/employee/{new}", content="x").status_code == 400
    assert client.put(f"/api/payroll/2026-09/employee/{new}", json={"changes": {"name": "X"}},
                      headers={"origin": "https://evil.example"}).status_code == 403


def test_company_can_be_set_and_is_listed(client, tmp_path):
    job = upload(client, tmp_path, name="MAJU JAYA ALI SEPT 26.png").json()["created"][0]
    r = client.put(f"/api/jobs/{job['id']}/company", json={"company": "MAJU JAYA"})
    assert r.status_code == 200 and r.json() == {"moved": 0}
    assert client.get("/api/jobs").json()[0]["company"] == "MAJU JAYA"
    assert client.put(f"/api/jobs/{job['id']}/company", json={"company": 5}).status_code == 400
    assert client.put("/api/jobs/nope/company", json={"company": "X"}).status_code == 404


def test_a_card_no_longer_in_recent_files_is_taken_off_and_saving_still_works(tmp_path):
    """History reset / deleted document: the old card must not block every later save (it is taken off, not an
    error)."""
    import shutil

    store, client = company_client(tmp_path, month_card)
    with client as c:
        for name in (f"MAJU JAYA SEPT {YEAR} (ALI) (1).png", f"MAJU JAYA SEPT {YEAR} (ALI) (2).png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        month = f"{YEAR}-09"
        ali = employee_named(c, month, "MAJU JAYA ALI")["id"]
        jobs = c.get(f"/api/payroll/{month}/employee/{ali}").json()["employee"]["jobs"]
        assert len(jobs) == 2
        shutil.rmtree(store.root / jobs[0])                               # the document is gone
        assert c.get(f"/api/payroll/{month}/companies").status_code == 200
        saved = change(c, month, ali, emp_no="MJ(1)")
        assert saved.status_code == 200 and saved.json()["employee"]["jobs"] == [jobs[1]]


def test_payroll_uses_only_the_chosen_workers_page_of_a_report(tmp_path):
    def two_workers(image):
        n = two_workers.calls = getattr(two_workers, "calls", 0) + 1
        return record([{"Date": good(f"01-09-{YEAR}"), "Shift Details / Actual": good("8.00"),
                        "OverTime / 1.5": good("1.50" if n == 1 else "3.00")}],
                      labels=("Date", "Shift Details / Actual", "OverTime / 1.5"),
                      header=[("Emp Code", good(f"E0{n}")), ("Name", good(f"W{n}"))])

    store = Jobs(tmp_path / "jobs", reader=two_workers)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        src = tmp_path / "report.pdf"
        make_pdf(src, 2)
        name = f"MAJU JAYA REPORT SEPT {YEAR}.pdf"
        job = c.post("/api/jobs", files=[("files", (name, src.read_bytes(), "application/pdf"))]).json()["created"][0]
        store.wait_idle()
        month = f"{YEAR}-09"
        w2 = employee_named(c, month, "W2")                               # each worker's page is its own employee
        view = c.get(f"/api/payroll/{month}/employee/{w2['id']}").json()
        assert view["employee"]["jobs"] == [job["id"] + "#p2"]
        values = view["result"]["values"]
        assert values["ot_1_5"]["value"] == 3.0 and values["days_worked"]["value"] == 1


def test_new_workers_get_employee_nos_that_are_remembered_for_next_month(tmp_path):
    store, client = company_client(tmp_path, nine_hour_card)
    with client as c:
        for name in (f"MAJU JAYA ALI SEPT {YEAR}.png", f"MAJU JAYA ALI SEPT {YEAR} 2.png",
                     f"OTHER CO ZUL SEPT {YEAR}.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        for j in c.get("/api/jobs").json():
            c.put(f"/api/jobs/{j['id']}/company", json={"company": "MAJU JAYA" if j["name"].startswith("MAJU") else "OTHER CO"})
        sept, octo, nov = f"{YEAR}-09", f"{YEAR}-10", f"{YEAR}-11"
        added = c.get(f"/api/payroll/{sept}/companies").json()["added_by_themselves"]
        assert added["new_numbers"] == 2 and added["from_million"] == 0
        ali = employee_named(c, sept, "ALI")
        emp = c.get(f"/api/payroll/{sept}/employee/{ali['id']}").json()["employee"]
        assert len(emp["jobs"]) == 2
        # a worker with no Employee No. anywhere gets a new one: the company's first 7 letters and the next number
        assert emp["emp_no"] == emp["emp_no_new"] == "MAJUJAY001"
        assert employee_named(c, sept, "ZUL")["emp_no"] == "OTHERCO001"
        upload(c, tmp_path, name=f"MAJU JAYA ALI OCT {YEAR}.png")
        store.wait_idle()
        set_company(c, "MAJU JAYA ALI OCT", "MAJU JAYA")
        october = c.get(f"/api/payroll/{octo}/employee/{employee_named(c, octo, 'ALI')['id']}").json()["employee"]
        assert october["emp_no"] == "MAJUJAY001" and "emp_no_new" not in october          # remembered
        assert "emp_no_new" not in change(c, sept, ali["id"], emp_no="MJ(1)").json()["employee"]   # the user types it
        upload(c, tmp_path, name=f"MAJU JAYA ALI NOV {YEAR}.png")
        store.wait_idle()
        set_company(c, "MAJU JAYA ALI NOV", "MAJU JAYA")
        assert employee_named(c, nov, "ALI")["emp_no"] == "MJ(1)"         # ... and that is filled in next month
        # an employee already in a payroll with no number gets one when the month is opened, once
        change(c, sept, ali["id"], emp_no="")
        opened = c.get(f"/api/payroll/{sept}/companies").json()
        given = c.get(f"/api/payroll/{sept}/employee/{ali['id']}").json()["employee"]
        assert opened["numbered"] == 1 and given["emp_no"].startswith("MAJUJAY")
        assert given["emp_no_new"] == given["emp_no"]
        assert c.get(f"/api/payroll/{sept}/companies").json()["numbered"] == 0


def test_a_month_grid_with_several_workers_gives_one_employee_per_row(tmp_path):
    labels = ("Name",) + tuple(str(d) for d in range(1, 32)) + ("Remark",)
    marks = {str(d): good("" if d in (6, 13, 20, 27, 31) else "✓") for d in range(1, 32)}

    def sheet(image):
        return record([{"Name": good(n), **marks, "Remark": good("26")} for n in ("ALI", "AMIN", "ZUL")],
                      labels=labels, header=[("CLEANER NAME", good("ALI"))])

    store = Jobs(tmp_path / "jobs", reader=sheet)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        job = upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR}.png").json()["created"][0]
        store.wait_idle()
        month = f"{YEAR}-09"
        over = c.get(f"/api/payroll/{month}/companies").json()           # read after the app started: added by itself
        assert over["added_by_themselves"]["added"] == [{"name": n, "cards": 1} for n in ("ALI", "AMIN", "ZUL")]
        assert c.get(f"/api/payroll/{month}/companies").json()["added_by_themselves"] is None     # once only
        people = c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()["employees"]
        assert [e["name"] for e in people] == ["ALI", "AMIN", "ZUL"]
        for row, e in enumerate(people, 1):
            view = c.get(f"/api/payroll/{month}/employee/{e['id']}").json()
            assert view["employee"]["jobs"] == [f"{job['id']}#p1r{row}"]
            assert view["result"]["values"]["days_worked"]["value"] == 26
            assert view["result"]["complete"] or {i["kind"] for i in view["result"]["issues"]} == {"empno"}


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
        october = c.get(f"/api/payroll/{YEAR}-10/companies").json()          # another month: nothing
        assert all(r["employees"] == 0 for r in october["companies"])
        over = c.get(f"/api/payroll/{YEAR}-09/companies").json()
        added = over["added_by_themselves"]
        assert added["added"] == [{"name": "MAJU JAYA ALI", "cards": 2}] and added["joined"] == []
        assert added["no_month"] == [{"name": "MAJU JAYA ZUL.png",
                                      "why": "no month was found in the file name or on the card"}]
        [ali] = c.get(f"/api/payroll/{YEAR}-09/company", params={"name": ""}).json()["employees"]
        view = c.get(f"/api/payroll/{YEAR}-09/employee/{ali['id']}").json()
        assert (view["employee"]["name"], len(view["employee"]["jobs"])) == ("MAJU JAYA ALI", 2)
        assert view["result"]["values"]["days_worked"]["value"] == 1


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
        month = f"{YEAR}-09"
        assert c.get(f"/api/payroll/{month}/companies").json()["added_by_themselves"]["from_million"] == 1
        who = employee_named(c, month, "Ali bin Abu")["id"]
        worker = c.get(f"/api/payroll/{month}/employee/{who}").json()["employee"]           # saved
        assert (worker["name"], worker["emp_no"], worker["emp_no_million"]) == ("Ali bin Abu", "MJ(1)", "MJ(1)")
        saved = change(c, month, who, emp_no="MJ(2)").json()["employee"]   # the user types another number
        assert "emp_no_million" not in saved


def test_a_later_card_joins_its_worker_and_a_removed_card_is_not_added_again(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=nine_hour_card)
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR} (ALI) (1).png")
        store.wait_idle()
        month = f"{YEAR}-09"
        ali = employee_named(c, month, "MAJU JAYA ALI")["id"]
        jobs = lambda: c.get(f"/api/payroll/{month}/employee/{ali}").json()["employee"]["jobs"]   # noqa: E731
        assert len(jobs()) == 1
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR} (ALI) (2).png")
        store.wait_idle()
        over = c.get(f"/api/payroll/{month}/companies").json()
        assert over["added_by_themselves"]["joined"] == [{"name": "MAJU JAYA ALI", "cards": 1}] and len(jobs()) == 2
        assert c.post(f"/api/payroll/{month}/take-off", json={"ref": jobs()[1]}).json() == {"ok": True}   # taken off
        over = c.get(f"/api/payroll/{month}/companies").json()
        assert over["added_by_themselves"] is None and len(jobs()) == 1


def test_files_already_there_when_the_app_starts_are_left_as_they_are(tmp_path):
    store = Jobs(tmp_path / "jobs", reader=nine_hour_card)
    store.create_job(f"MAJU JAYA SEPT {YEAR} (ALI).png", png_bytes(tmp_path))
    store.wait_idle()
    with TestClient(app_module.create_app(store), base_url="http://localhost") as c:
        over = c.get(f"/api/payroll/{YEAR}-09/companies").json()
        assert all(r["employees"] == 0 for r in over["companies"]) and over["added_by_themselves"] is None


def test_the_month_file_asks_about_an_employee_no_that_is_not_in_employees_txt(tmp_path, monkeypatch):
    listed = tmp_path / "employees.txt"
    listed.write_text("MJ(7)\n", encoding="utf-8")
    monkeypatch.setenv("TABLE_READER_MILLION_EMPLOYEES", str(listed))
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"MAJU JAYA ALI SEPT {YEAR}.png")
        store.wait_idle()
        month = f"{YEAR}-09"
        change(c, month, employee_named(c, month, "MAJU JAYA ALI")["id"], emp_no="MJ(1)")
        run = c.get(f"/api/payroll/{month}/run").json()
        assert run["ready"] == 0 and run["checked_with_million"] is False
        [held] = [h for comp in run["companies"] for h in comp["held"]]
        assert "Million" in " ".join(held["reasons"])
        listed.write_text("MJ(7)\nmj(1)\n", encoding="utf-8")                # added to the list: it goes in
        assert c.get(f"/api/payroll/{month}/run").json()["ready"] == 1


def test_millions_employee_list_is_imported_and_checked_before_the_month_file(tmp_path):
    from tests.helpers import million_listing

    store, client = company_client(tmp_path, month_card)
    with client as c:
        month = f"{YEAR}-09"
        assert c.get(f"/api/payroll/{month}/companies").json()["checked_with_million"] is False
        r = c.post("/api/million/employees", files={"file": ("notes.xls", b"hello", "application/vnd.ms-excel")})
        assert r.status_code == 400 and r.json()["code"] == "MILLION_LIST"
        listing = million_listing([("MJ(1)", "SITI"), ("MJ(2)", "ALI")])
        r = c.post("/api/million/employees", files={"file": ("rptempepmlist.xls", listing, "application/vnd.ms-excel")})
        assert r.status_code == 200 and [(e["emp_no"], e["name"]) for e in r.json()["employees"]] == [("MJ(1)", "SITI"),
                                                                                                      ("MJ(2)", "ALI")]
        assert c.get(f"/api/payroll/{month}/companies").json()["checked_with_million"] is True
        saved = json.loads((tmp_path / "payroll" / "million-employees.json").read_text(encoding="utf-8"))
        assert set(saved) == {"imported", "source", "employees"} and set(saved["employees"][0]) == {"emp_no", "name", "basic_rate"}

        upload(c, tmp_path, name=f"MAJU JAYA ALI SEPT {YEAR}.png")
        store.wait_idle()
        ali = employee_named(c, month, "MAJU JAYA ALI")["id"]
        for emp_no, why in (("MJ(7)", "not in"), ("MJ(1)", "SITI")):          # not in Million / someone else there
            change(c, month, ali, emp_no=emp_no)
            run = c.get(f"/api/payroll/{month}/run").json()
            [held] = [h for comp in run["companies"] for h in comp["held"]]
            assert run["ready"] == 0 and why in " ".join(held["reasons"]), held
        change(c, month, ali, emp_no="mj(2)")                              # the right person: it goes in
        assert c.get(f"/api/payroll/{month}/run").json()["ready"] == 1


def test_the_month_run_makes_one_file_and_lists_who_is_held_back(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        month = f"{YEAR}-09"
        assert c.post(f"/api/payroll/{month}/run").json()["code"] == "PAYROLL_EMPTY"
        import_million(c, ("MJ(1)", "ALI"), ("MJ(2)", "SITI"))
        for name in (f"MAJU JAYA ALI SEPT {YEAR}.png", f"BINA SITI SEPT {YEAR}.png", f"BINA ZUL SEPT {YEAR}.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        offers = {i["emp_no"] for i in c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()["items"]
                  if i["kind"] == "offer"}
        assert offers == {"MJ(1)", "MJ(2)"}                                 # ZUL: nobody of that name in Million
        accept_offers(c, month, "")                                        # the user accepts the two offers
        assert not [i for i in c.get(f"/api/payroll/{month}/company", params={"name": ""}).json()["items"]
                    if i["kind"] == "offer"]                               # nothing left to offer
        run = c.post(f"/api/payroll/{month}/run").json()
        assert run["file"] == f"Payroll {month} (Million).xls" and run["ready"] == 2 and run["held"] == 1
        assert run["checked_with_million"] is True and len(run["companies"]) >= 1
        held = [h for comp in run["companies"] for h in comp["held"]]
        assert held == [{"emp_no": "", "name": "BINA ZUL",
                         "reasons": ["Employee No. is empty. Type it exactly as in Million Payroll."]}]
        sheet = xlrd.open_workbook(str(tmp_path / "payroll" / run["file"])).sheet_by_index(0)
        assert [sheet.cell_value(r, 0) for r in range(1, sheet.nrows)] == ["MJ(1)", "MJ(2)"]


def test_basic_pay_table_download(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        upload(c, tmp_path, name=f"MAJU JAYA ALI SEPT {YEAR}.png")
        store.wait_idle()
        month = f"{YEAR}-09"
        ali = employee_named(c, month, "MAJU JAYA ALI")["id"]
        saved = change(c, month, ali, emp_no="MJ(1)", pay_basis="daily", basic_rate=70).json()
        days = saved["result"]["values"]["days_worked"]["value"]
        assert saved["employee"]["basic_rate"] == 70.0 and saved["result"]["pay"]["basic"] == 70 * days
        r = c.get(f"/api/payroll/{month}/basic-pay")
        assert r.status_code == 200 and f"Basic%20pay%20{month}.csv" in r.headers["content-disposition"]
        lines = r.content.decode("utf-8-sig").splitlines()
        assert lines[1].split(",")[1:8] == ["MJ(1)", "MAJU JAYA ALI", "Daily", "70.00", "Table Reader", f"{days:.2f}", f"{70 * days:.2f}"]
        assert (tmp_path / "payroll" / f"Basic pay {month}.csv").is_file()


def test_pay_basis_and_rate_come_from_millions_report_until_typed(tmp_path):
    from tests.helpers import million_listing

    store, client = company_client(tmp_path, month_card)
    with client as c:
        listing = million_listing([("MJ(1)", "ALI", "MAJU JAYA", "Daily", 60.0)], title_col=1)
        c.post("/api/million/employees", files={"file": ("rptemppsnlist.xls", listing, "application/vnd.ms-excel")})
        upload(c, tmp_path, name=f"MAJU JAYA ALI SEPT {YEAR}.png")
        store.wait_idle()
        month = f"{YEAR}-09"
        ali = employee_named(c, month, "MAJU JAYA ALI")["id"]
        assert c.get(f"/api/payroll/{month}/employee/{ali}").json()["result"]["rate_source"] is None   # no Employee No.
        r = change(c, month, ali, emp_no="mj(1)").json()["result"]
        assert (r["pay_basis"], r["basic_rate"], r["rate_source"]) == ("daily", 60.0, "million")
        assert r["pay"]["basic"] == 60.0 * r["values"]["days_worked"]["value"] and r["million"]["branch"] == "MAJU JAYA"
        r = change(c, month, ali, pay_basis="monthly", basic_rate=1500).json()["result"]
        assert (r["pay_basis"], r["rate_source"], r["pay"]["basic"]) == ("monthly", "typed", 1500.0)


def test_payroll_csv_for_one_company(tmp_path):
    store, client = company_client(tmp_path, nine_hour_card)
    with client as c:
        for name in (f"MAJU JAYA ALI SEPT {YEAR}.png", f"OTHER CO ZUL SEPT {YEAR}.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        for j in c.get("/api/jobs").json():
            c.put(f"/api/jobs/{j['id']}/company", json={"company": " ".join(j["name"].split()[:2])})
        month = f"{YEAR}-09"
        c.get(f"/api/payroll/{month}/companies")                           # opened: both companies' cards join
        everyone = c.get(f"/api/payroll/{month}/csv").content.decode("utf-8-sig").splitlines()
        one = c.get(f"/api/payroll/{month}/csv", params={"company": "MAJU JAYA"})
        lines = one.content.decode("utf-8-sig").splitlines()
        assert len(everyone) == 3 and len(lines) == 2 and ",ALI," in lines[1]
        assert f"Payroll%20{month}%20MAJU%20JAYA.csv" in one.headers["content-disposition"]
        assert c.get(f"/api/payroll/{month}/csv", params={"company": "NOBODY"}).json()["code"] == "PAYROLL_EMPTY"


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
        ref = c.get(f"/api/payroll/{month}/employee/{siti['id']}").json()["employee"]["jobs"][0]
        c.post(f"/api/payroll/{month}/take-off", json={"ref": ref})       # the user takes the card off
        items = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"]
        assert [(i["kind"], i.get("ref")) for i in items if i["kind"] == "unplaced"] == [("unplaced", ref)]
        assert c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": None}).json()["ok"] is True
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert len(view["employees"]) == 2 and not [i for i in view["items"] if i["kind"] == "unplaced"]
        # placed on the new employee already: putting it on SITI as well is refused and changes nothing
        r = c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti["id"]})
        assert r.status_code == 400 and "one employee only" in r.json()["message"]
        assert c.get(f"/api/payroll/{month}/employee/{siti['id']}").json()["employee"]["jobs"] == []
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
        assert c.get(f"/api/payroll/{month}/employee/twin1").status_code == 200    # the employee view, to put it right
        # nothing was added to the plan that cannot be saved, and no number was remembered for someone not in it
        assert len(json.loads(path.read_text(encoding="utf-8"))["employees"]) == 2
        remembered = json.loads((tmp_path / "payroll" / "employees.json").read_text(encoding="utf-8"))
        assert not [k for k in remembered if "zul" in k]
        # once the plan is put right (the twin removed), the waiting file joins by itself
        assert c.delete(f"/api/payroll/{month}/employee/twin1").json() == {"ok": True}
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
        siti = employee_named(c, month, "SITI")
        ref = c.get(f"/api/payroll/{month}/employee/{siti['id']}").json()["employee"]["jobs"][0]
        c.post(f"/api/payroll/{month}/take-off", json={"ref": ref})       # the user takes SITI's card off
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
        siti = employee_named(c, month, "SITI")
        c.delete(f"/api/payroll/{month}/employee/{siti['id']}")        # the employee is removed: the card is nobody's
        item = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"][0]
        assert item["kind"] == "unplaced" and item["doc"] == item["ref"]
        assert c.post("/api/payroll/file-month", json={"id": item["doc"], "month": "none"}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert view["items"] == [] and view["employees"] == []           # and it does not come back by itself


# ------------------------------------------------------------------------------------------- the one-look panel
def day_9_unclear(image):
    rows = [{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)]
    rows[8]["Total"] = cell(None, "9?", 30, "smudged")
    return record(rows, labels=("Date", "Total"))


def employee_named(c, month, name):
    """The employee of that name, as the company screens list them (opening the month first)."""
    for row in c.get(f"/api/payroll/{month}/companies").json()["companies"]:
        for e in c.get(f"/api/payroll/{month}/company", params={"name": row["company"]}).json()["employees"]:
            if e["name"] == name:
                return e
    raise AssertionError(f"no employee {name}")


def test_the_look_panel_lists_the_yellow_lines_and_accepting_clears_them(tmp_path):
    store, client = company_client(tmp_path, day_9_unclear)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        siti = employee_named(c, month, "SITI")
        look = c.get(f"/api/payroll/{month}/look", params={"employee": siti["id"]}).json()
        assert (look["name"], look["company"], look["month"]) == ("SITI", "BINA", month)
        [card] = look["cards"]
        [line] = card["lines"]
        assert (line["page"], line["row"], line["day"]) == (1, 8, 9)
        total = next(x for x in line["cells"] if x["column"] == "Total")
        assert total["needs_review"] and total["raw_text"] == "9?"
        item = next(i for i in c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"]
                    if i["kind"] == "look")
        assert item["places"] == 1
        change = {"page": 1, "row": 8, "column": "Total", "value": "9", "via": "look"}
        assert c.put(f"/api/jobs/{card['doc']}/cells", json={"changes": [change]}).status_code == 200
        assert c.get(f"/api/payroll/{month}/look", params={"employee": siti["id"]}).json()["cards"] == []
        # a second window still showing the yellow cell cannot save over what was just saved
        stale = {**change, "value": "8", "seen": {"edited": False, "value": None}}
        r = c.put(f"/api/jobs/{card['doc']}/cells", json={"changes": [stale]})
        assert r.status_code == 409 and r.json()["code"] == "CELL_CHANGED"
        items = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["items"]
        assert "look" not in [i["kind"] for i in items]


def test_the_look_panel_points_at_the_documents_row_of_a_grid(tmp_path):
    labels = ("Name",) + tuple(str(d) for d in range(1, 32)) + ("Remark",)
    marks = {str(d): good("" if d in (6, 13, 20, 27, 31) else "✓") for d in range(1, 32)}

    def sheet(image):
        rows = [{"Name": good(n), **marks, "Remark": good("26")} for n in ("ALI", "AMIN", "ZUL")]
        rows[2]["2"] = cell(None, "?", 20, "smudged")
        return record(rows, labels=labels, header=[("CLEANER NAME", good("ALI"))])

    store, client = company_client(tmp_path, sheet)
    with client as c:
        upload(c, tmp_path, name=f"MAJU JAYA SEPT {YEAR}.png")
        store.wait_idle()
        month = f"{YEAR}-09"
        zul = employee_named(c, month, "ZUL")
        [card] = c.get(f"/api/payroll/{month}/look", params={"employee": zul["id"]}).json()["cards"]
        assert [(line["row"], line["day"], [x["column"] for x in line["cells"]]) for line in card["lines"]] == [
            (2, 2, ["2"])]


def test_the_look_panel_for_an_unknown_employee_says_so(tmp_path):
    store, client = company_client(tmp_path, day_9_unclear)
    with client as c:
        r = c.get(f"/api/payroll/{YEAR}-09/look", params={"employee": "e-gone"})
        assert r.status_code == 404 and r.json()["code"] == "EMPLOYEE_NOT_FOUND"


def test_the_look_panel_leaves_out_a_card_that_cannot_be_opened(tmp_path):
    store, client = company_client(tmp_path, day_9_unclear)
    with client as c:
        upload(c, tmp_path, name=f"BINA SITI SEPT {YEAR}.png")
        upload(c, tmp_path, name=f"BINA SITI 2 SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        people = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["employees"]
        siti = next(e for e in people if e["name"] == "SITI")
        for other in (e for e in people if e is not siti):                 # every card on SITI, the others removed
            for ref in c.get(f"/api/payroll/{month}/employee/{other['id']}").json()["employee"]["jobs"]:
                c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti["id"], "move": True})
            assert c.delete(f"/api/payroll/{month}/employee/{other['id']}").json() == {"ok": True}
        jobs = sorted(c.get(f"/api/payroll/{month}/employee/{siti['id']}").json()["employee"]["jobs"])
        assert len(jobs) == 2
        (store.root / jobs[0] / "result.json").write_text("{ damaged", encoding="utf-8")
        r = c.get(f"/api/payroll/{month}/look", params={"employee": siti["id"]})
        assert r.status_code == 200
        assert [card["doc"] for card in r.json()["cards"]] == [jobs[1]]


# ------------------------------------------------------------------------------------- month and company settings
def ali_of_a_and_b(tmp_path):
    """A & B (M) with one worker, ALI, whose card has 9 hours on every day of September."""
    store, client = company_client(tmp_path, month_card)
    return store, client, f"{YEAR}-09"


def company_figures(c, month, company):
    view = c.get(f"/api/payroll/{month}/company", params={"name": company}).json()
    return view, {e["name"]: (e["ot_1_5"], e["days_worked"]) for e in view["employees"]}


def test_company_settings_change_its_employees_figures_and_back(tmp_path):
    store, client, month = ali_of_a_and_b(tmp_path)
    with client as c:
        upload(c, tmp_path, name=f"A & B (M) ALI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "A & B", "A & B (M)")
        view, before = company_figures(c, month, "A & B (M)")
        assert before == {"ALI": (26.0, 26.0)} and view["settings"]["own"] is False
        r = c.put(f"/api/payroll/{month}/company-settings", json={"company": "A & B (M)", "own": True, "normal_hours": 9,
                                                                  "keep": True})
        assert r.json() == {"ok": True}
        view, own = company_figures(c, month, "A & B (M)")
        assert own == {"ALI": (0.0, 26.0)}
        assert view["settings"]["own"] is True and view["settings"]["keep"] is True and view["settings"]["normal_hours"] == 9
        rows = {r["company"]: r for r in c.get(f"/api/payroll/{month}/companies").json()["companies"]}
        assert rows["A & B (M)"]["own"] is True
        c.put(f"/api/payroll/{month}/company-settings", json={"company": "A & B (M)", "own": False})
        assert company_figures(c, month, "A & B (M)")[1] == before


def test_month_settings_apply_to_companies_that_follow_them(tmp_path):
    store, client, month = ali_of_a_and_b(tmp_path)
    with client as c:
        upload(c, tmp_path, name=f"A & B (M) ALI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "A & B", "A & B (M)")
        default = c.get(f"/api/payroll/{month}/companies").json()["settings"]
        assert default["normal_hours"] == 8 and default["day_types"]["6"] == "rest"
        r = c.put(f"/api/payroll/{month}/settings", json={**default, "normal_hours": 9})
        assert r.json() == {"ok": True}
        assert company_figures(c, month, "A & B (M)")[1] == {"ALI": (0.0, 26.0)}


def test_a_month_default_changed_after_own_settings_gives_an_item_until_saved_again(tmp_path):
    store, client, month = ali_of_a_and_b(tmp_path)
    with client as c:
        upload(c, tmp_path, name=f"A & B (M) ALI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "A & B", "A & B (M)")
        c.put(f"/api/payroll/{month}/company-settings", json={"company": "A & B (M)", "own": True})   # a copy
        default = c.get(f"/api/payroll/{month}/companies").json()["settings"]
        default["day_types"]["16"] = "holiday"
        c.put(f"/api/payroll/{month}/settings", json=default)
        view = c.get(f"/api/payroll/{month}/company", params={"name": "A & B (M)"}).json()
        assert view["items"][0] == {"kind": "settings", "company": "A & B (M)"}
        assert view["settings"]["default_changed"] is True and view["settings"]["day_types"]["16"] == "work"
        assert view["settings"]["default"]["day_types"]["16"] == "holiday"
        own = view["settings"]
        c.put(f"/api/payroll/{month}/company-settings", json={"company": "A & B (M)", "own": True, "keep": own["keep"],
              **{k: own[k] for k in ("normal_hours", "break_hours", "day_types")}})                  # "It is right"
        view = c.get(f"/api/payroll/{month}/company", params={"name": "A & B (M)"}).json()
        assert [i["kind"] for i in view["items"]] == [] and view["settings"]["default_changed"] is False


def test_an_employee_change_keeps_the_company_settings(tmp_path):
    """The old page's save guard: a change from the employee view, opened before the company's settings were changed,
    keeps them (only the key sent is changed)."""
    store, client, month = ali_of_a_and_b(tmp_path)
    with client as c:
        upload(c, tmp_path, name=f"A & B (M) ALI SEPT {YEAR}.png")
        store.wait_idle()
        set_company(c, "A & B", "A & B (M)")
        ali = employee_named(c, month, "ALI")["id"]
        c.get(f"/api/payroll/{month}/employee/{ali}")                      # "Open employee": the view in a new tab
        c.put(f"/api/payroll/{month}/company-settings", json={"company": "A & B (M)", "own": True, "normal_hours": 9})
        assert change(c, month, ali, message="typed in the other tab").status_code == 200
        view = c.get(f"/api/payroll/{month}/company", params={"name": "A & B (M)"}).json()
        assert view["settings"]["own"] is True and view["settings"]["normal_hours"] == 9
        assert c.get(f"/api/payroll/{month}/employee/{ali}").json()["employee"]["message"] == "typed in the other tab"


def test_bad_settings_are_refused(tmp_path):
    store, client, month = ali_of_a_and_b(tmp_path)
    with client as c:
        r = c.put(f"/api/payroll/{month}/company-settings", json={"company": "", "own": True})
        assert r.status_code == 400 and r.json()["message"] == "Choose the company first."
        r = c.put(f"/api/payroll/{month}/company-settings", json={"company": "BINA", "own": True, "normal_hours": 25})
        assert r.json()["message"] == "Normal hours per day must be a number from 1 to 24."
        r = c.put(f"/api/payroll/{month}/settings", json={"normal_hours": 8, "break_hours": 1, "day_types": {"1": "work"}})
        assert r.json()["code"] == "BAD_PAYROLL"
        r = c.put(f"/api/payroll/{month}/settings", json=["not", "settings"])
        assert r.json()["code"] == "BAD_PAYROLL"


# ------------------------------------------------------------------------------------ the month's Million file
def three_workers(c, store, tmp_path):
    """MAJU JAYA: ALI; BINA: SITI and ZUL. Million knows ALI and SITI; ZUL gets a new number Million does not have."""
    import_million(c, ("MJ1", "ALI"), ("BN1", "SITI"))
    for name in (f"MAJU JAYA ALI SEPT {YEAR}.png", f"BINA SITI SEPT {YEAR}.png", f"BINA ZUL SEPT {YEAR}.png"):
        upload(c, tmp_path, name=name)
    store.wait_idle()
    set_company(c, "MAJU JAYA", "MAJU JAYA")
    set_company(c, "BINA", "BINA")
    month = f"{YEAR}-09"
    c.get(f"/api/payroll/{month}/companies")                        # opening the month: the files join by themselves
    accept_offers(c, month, "MAJU JAYA")
    accept_offers(c, month, "BINA")
    return month


def test_the_summary_lists_who_goes_in_and_writes_no_file(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        month = three_workers(c, store, tmp_path)
        run = c.get(f"/api/payroll/{month}/run").json()
        assert run["made"] is False and run["file"] is None and run["ready"] == 2 and run["held"] == 1
        bina = next(comp for comp in run["companies"] if comp["company"] == "BINA")
        assert bina["ready_people"] == [{"emp_no": "BN1", "name": "SITI"}]           # only ZUL is held back
        assert len(bina["held"]) == 1 and bina["held"][0]["name"] == "ZUL"
        assert "is not in the Million employee list" in " ".join(bina["held"][0]["reasons"])
        assert list((tmp_path / "payroll").glob("*.xls")) == []


def test_the_file_is_worked_out_again_when_it_is_made(tmp_path):
    store, client = company_client(tmp_path, month_card)
    with client as c:
        month = three_workers(c, store, tmp_path)
        assert c.get(f"/api/payroll/{month}/run").json()["held"] == 1
        zul = next(e for e in c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()["employees"]
                   if e["name"] == "ZUL")
        import_million(c, ("MJ1", "ALI"), ("BN1", "SITI"), (zul["emp_no"], "ZUL"))     # created in Million since
        run = c.post(f"/api/payroll/{month}/run").json()
        assert run["made"] is True and run["ready"] == 3 and run["held"] == 0
        assert (tmp_path / "payroll" / run["file"]).exists()


# ------------------------------------------------------------------- a card layout Table Reader does not know
LAYOUT_2 = ("NO.", "DATE", "WHrs", "OT", "LIn(Min)", "E/Out(Min)")


def report_2_card(image):
    return record([{"NO.": good(str(d)), "DATE": good(str(d)), "WHrs": good("8"), "OT": good("2"),
                    "LIn(Min)": good("15"), "E/Out(Min)": good("0")} for d in range(1, 31)], labels=LAYOUT_2)


def layout_month(c, store, tmp_path):
    upload(c, tmp_path, name=f"MAJU JAYA ALI SEPT {YEAR}.png")
    store.wait_idle()
    set_company(c, "MAJU JAYA", "MAJU JAYA")
    month = f"{YEAR}-09"
    view = c.get(f"/api/payroll/{month}/company", params={"name": "MAJU JAYA"}).json()   # opening: the card joins
    return month, view


def report_2_map(**change):
    roles = {"NO.": ("ignore", "none"), "DATE": ("date", "none"), "WHrs": ("hours", "hours"), "OT": ("ot_1_5", "hours"),
             "LIn(Min)": ("lateness", "minutes"), "E/Out(Min)": ("early_departure", "minutes"), **change}
    return {c: {"role": r, "unit": u} for c, (r, u) in roles.items()}


def test_confirming_a_layout_changes_the_figures(tmp_path):
    store, client = company_client(tmp_path, report_2_card)
    with client as c:
        month, view = layout_month(c, store, tmp_path)
        [item] = [i for i in view["items"] if i["kind"] == "layout"]
        assert item["columns"] == ["OT", "LIn(Min)", "E/Out(Min)"] and view["employees"][0]["ot_1_5"] == 0
        where = {"doc": item["doc"], "page": item["page"]}
        assert c.put("/api/layouts", json={**where, "columns": report_2_map()}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": "MAJU JAYA"}).json()
        assert not [i for i in view["items"] if i["kind"] == "layout"]
        assert view["employees"][0]["ot_1_5"] == 60.0                         # the OT column: 2 hours on 30 days
        got = c.get("/api/layouts", params={"doc": item["doc"], "page": item["page"]}).json()
        assert got["saved"] == report_2_map() and got["labels"] == list(LAYOUT_2)


def test_it_is_right_as_it_is_ignores_the_rest(tmp_path):
    store, client = company_client(tmp_path, report_2_card)
    with client as c:
        month, view = layout_month(c, store, tmp_path)
        [item] = [i for i in view["items"] if i["kind"] == "layout"]
        before = view["employees"]
        where = {"doc": item["doc"], "page": item["page"]}
        assert c.put("/api/layouts", json={**where, "as_is": True}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": "MAJU JAYA"}).json()
        assert not [i for i in view["items"] if i["kind"] == "layout"] and view["employees"] == before


def test_a_bad_map_is_refused_and_nothing_saved(tmp_path):
    store, client = company_client(tmp_path, report_2_card)
    with client as c:
        month, view = layout_month(c, store, tmp_path)
        [item] = [i for i in view["items"] if i["kind"] == "layout"]
        r = c.put("/api/layouts", json={"doc": item["doc"], "page": item["page"],
                                        "columns": report_2_map(OT=("salary", "hours"))})
        assert r.status_code == 400 and r.json()["code"] == "BAD_LAYOUT"
        assert c.get("/api/layouts", params={"doc": item["doc"], "page": item["page"]}).json()["saved"] is None
        assert c.put("/api/layouts", json={"doc": "nope", "page": 1, "as_is": True}).status_code == 404


def test_opening_the_panel_does_not_ask_claude(tmp_path, monkeypatch):
    asked = []

    def fake_ask(prompt, schema, **kw):
        asked.append(prompt)
        return {"columns": [{"label": c, **v} for c, v in report_2_map().items()]}

    monkeypatch.setattr(ocr, "ask_text", fake_ask)
    store, client = company_client(tmp_path, report_2_card)
    with client as c:
        month, view = layout_month(c, store, tmp_path)
        [item] = [i for i in view["items"] if i["kind"] == "layout"]
        got = c.get("/api/layouts", params={"doc": item["doc"], "page": item["page"]}).json()
        assert asked == [] and got["suggestion"] is None
        assert got["as_read"]["WHrs"] == {"role": "hours", "unit": "hours"}
        assert len(got["shapes"]) == 5 and got["shapes"][0]["WHrs"] == "9"
        got = c.get("/api/layouts", params={"doc": item["doc"], "page": item["page"], "ask": "true"}).json()
        assert len(asked) == 1 and got["suggestion"] == report_2_map() and got["error"] is None


def test_claude_failing_is_shown_not_a_crash(tmp_path, monkeypatch):
    def failing(prompt, schema, **kw):
        raise ocr.OcrError("CLAUDE_PLAN_LIMIT", "Your Claude plan has reached its usage limit for now.")

    monkeypatch.setattr(ocr, "ask_text", failing)
    store, client = company_client(tmp_path, report_2_card)
    with client as c:
        month, view = layout_month(c, store, tmp_path)
        [item] = [i for i in view["items"] if i["kind"] == "layout"]
        got = c.get("/api/layouts", params={"doc": item["doc"], "page": item["page"], "ask": "true"}).json()
        assert got["suggestion"] is None and "usage limit" in got["error"]


def test_it_is_right_as_it_is_keeps_the_hours_column_the_user_chose(tmp_path):
    store, client = company_client(tmp_path, report_2_card)
    with client as c:
        month, view = layout_month(c, store, tmp_path)
        [item] = [i for i in view["items"] if i["kind"] == "layout"]
        where = {"doc": item["doc"], "page": item["page"]}
        assert c.put("/api/layouts", json={**where, "as_is": True, "hours_column": "OT"}).json() == {"ok": True}
        assert c.get("/api/layouts", params=where).json()["saved"]["OT"] == {"role": "hours", "unit": "hours"}
        r = c.put("/api/layouts", json={**where, "as_is": True, "hours_column": "NOT A COLUMN"})
        assert r.status_code == 400 and r.json()["code"] == "BAD_LAYOUT"
        got = c.get("/api/layouts", params={**where, "hours": "WHrs"}).json()
        assert got["as_read"]["WHrs"]["role"] == "hours"


# ------------------------------------------------------------------------------- the employee view (stage 4 B)
@pytest.fixture
def maju_jaya(tmp_path):
    """MAJU JAYA with ALI and SITI, one 30-day card each, placed by opening the month. (client, month, ALI's id,
    SITI's id, ALI's card ref)"""
    store, client = company_client(tmp_path, month_card)
    with client as c:
        for name in (f"MAJU JAYA ALI SEPT {YEAR}.png", f"MAJU JAYA SITI SEPT {YEAR}.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        set_company(c, "MAJU JAYA", "MAJU JAYA")
        month = f"{YEAR}-09"
        view = c.get(f"/api/payroll/{month}/company", params={"name": "MAJU JAYA"}).json()
        people = {e["name"]: e["id"] for e in view["employees"]}
        ref = c.get(f"/api/payroll/{month}/employee/{people['ALI']}").json()["employee"]["jobs"][0]
        yield c, month, people["ALI"], people["SITI"], ref


def change(c, month, who, **changes):
    return c.put(f"/api/payroll/{month}/employee/{who}", json={"changes": changes})


def test_the_employee_view_shows_figures_cards_and_colleagues(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    view = c.get(f"/api/payroll/{month}/employee/{ali}").json()
    assert view["month"] == month and view["company"] == "MAJU JAYA" and view["employee"]["name"] == "ALI"
    assert view["result"]["values"]["days_worked"]["value"] == 26                # September's 4 Sundays are rest days
    assert view["result"]["columns"] == ["Date", "Total"]
    assert [(k["ref"], k["doc"]) for k in view["cards"]] == [(ref, ref)] and "ALI" in view["cards"][0]["name"]
    assert [(o["id"], o["name"]) for o in view["others"]] == [(siti, "SITI")]
    assert "allowance" in view["lists"] and view["fields"] and "allowance" in view["list_heads"]
    assert view["million"] is None


def test_an_override_is_saved_and_returned(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    r = change(c, month, ali, overrides={"ot_1_5": 4})
    assert r.json()["result"]["values"]["ot_1_5"] == {"value": 4, "computed": 26.0, "edited": True}   # 1 h a day
    back = change(c, month, ali, overrides={}).json()["result"]["values"]["ot_1_5"]
    assert back["edited"] is False and back["value"] == back["computed"]
    assert change(c, month, ali, overrides={"ot_1_5": -1}).status_code == 400
    assert change(c, month, ali, jobs=[]).status_code == 400                 # cards move through /place and /take-off
    assert c.put(f"/api/payroll/{month}/employee/{ali}", json={"name": "X"}).status_code == 400     # no "changes"


def test_saving_one_field_keeps_what_another_tab_changed(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    assert c.put(f"/api/payroll/{month}/employees/{ali}", json={"emp_no": "MJ9"}).json() == {"ok": True}
    saved = change(c, month, ali, name="ALI B").json()["employee"]
    assert (saved["emp_no"], saved["name"]) == ("MJ9", "ALI B")


def test_an_employee_removed_elsewhere_says_so(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    assert c.delete(f"/api/payroll/{month}/employee/{ali}").json() == {"ok": True}
    for r in (c.get(f"/api/payroll/{month}/employee/{ali}"), change(c, month, ali, name="X"),
              c.delete(f"/api/payroll/{month}/employee/{ali}"),
              c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": ali})):
        assert r.json()["code"] == "EMPLOYEE_NOT_FOUND"
        assert r.json()["message"].startswith("This employee is no longer in the payroll of this month")


def test_moving_a_card_takes_it_off_its_employee(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    r = c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti})
    assert r.status_code == 400 and "one employee only" in r.json()["message"]     # without "move": refused
    assert c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti, "move": True}).json()["ok"] is True
    assert c.get(f"/api/payroll/{month}/employee/{ali}").json()["employee"]["jobs"] == []
    assert ref in c.get(f"/api/payroll/{month}/employee/{siti}").json()["employee"]["jobs"]
    items = c.get(f"/api/payroll/{month}/company", params={"name": "MAJU JAYA"}).json()["items"]
    assert [i["kind"] for i in items if i.get("employee") == ali] == ["nocard"]
    assert c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": ali, "move": "yes"}).status_code == 400


def test_a_card_taken_off_is_whose_card_again(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    assert c.post(f"/api/payroll/{month}/take-off", json={"ref": ref}).json() == {"ok": True}
    items = c.get(f"/api/payroll/{month}/company", params={"name": "MAJU JAYA"}).json()["items"]
    assert [i["ref"] for i in items if i["kind"] == "unplaced"] == [ref]
    again = c.post(f"/api/payroll/{month}/take-off", json={"ref": ref}).json()
    assert again["code"] == "BAD_PAYROLL" and "not on any employee" in again["message"]
    assert c.post(f"/api/payroll/{month}/take-off", json={"ref": 5}).status_code == 400


def test_add_employee_by_hand_gets_a_number(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    new = c.post(f"/api/payroll/{month}/employee", json={"company": "MAJU JAYA"}).json()["employee"]
    view = c.get(f"/api/payroll/{month}/employee/{new}").json()
    assert view["employee"]["emp_no"].startswith("MAJUJAY") and view["company"] == "MAJU JAYA"
    assert view["employee"]["emp_no"] not in {o["emp_no"] for o in view["others"]}
    assert c.post(f"/api/payroll/{month}/employee", json={"company": 5}).status_code == 400


def test_one_line_is_added_or_removed_at_a_time(maju_jaya):
    """The lines are the same for every employee: a view opened before another tab added a line does not take it
    away (nor the figures on it) when it adds or removes another one."""
    c, month, ali, siti, ref = maju_jaya
    lines = lambda: c.get(f"/api/payroll/{month}/employee/{ali}").json()["lists"]["allowance"]   # noqa: E731
    url = f"/api/payroll/{month}/lists"
    assert c.put(url, json={"kind": "allowance", "add": {"name": "Transport", "type": "Fixed"}}).json() == {"ok": True}
    change(c, month, siti, entries={"allowance": {"Transport": 50}})
    assert c.put(url, json={"kind": "allowance", "add": {"name": "Meal", "type": ""}}).json() == {"ok": True}  # ALI's tab
    names = [line["name"] for line in lines()]
    assert "Transport" in names and "Meal" in names
    assert c.get(f"/api/payroll/{month}/employee/{siti}").json()["employee"]["entries"]["allowance"] == {"Transport": 50}
    r = c.put(url, json={"kind": "allowance", "add": {"name": "transport", "type": ""}})
    assert r.status_code == 400 and "twice" in r.json()["message"]
    assert c.put(url, json={"kind": "allowance", "remove": "Transport"}).json() == {"ok": True}
    assert c.get(f"/api/payroll/{month}/employee/{siti}").json()["employee"]["entries"]["allowance"] == {}
    assert c.put(url, json={"kind": "allowance", "remove": "Transport"}).json() == {"ok": True}   # gone already: nothing
    for bad in ({"lists": {}}, {"kind": "nope", "remove": "Meal"}, {"kind": "allowance"}, {"kind": "allowance", "add": "x"},
                {"kind": "allowance", "remove": 5}):
        assert c.put(url, json=bad).status_code == 400, bad
    assert "Meal" in [line["name"] for line in lines()]


def test_a_stale_view_cannot_take_a_card_off_someone_else(maju_jaya):
    """Tab A shows ALI's card; tab B moves it to SITI. Take off or Move in tab A then says so and changes nothing."""
    c, month, ali, siti, ref = maju_jaya
    place = f"/api/payroll/{month}/place"
    assert c.post(place, json={"ref": ref, "employee": siti, "move": True, "from": ali}).json()["ok"] is True   # tab B
    for r in (c.post(f"/api/payroll/{month}/take-off", json={"ref": ref, "from": ali}),
              c.post(place, json={"ref": ref, "employee": None, "move": True, "from": ali})):
        assert r.status_code == 400 and "no longer on this employee" in r.json()["message"]
    assert ref in c.get(f"/api/payroll/{month}/employee/{siti}").json()["employee"]["jobs"]
    assert len(c.get(f"/api/payroll/{month}/company", params={"name": "MAJU JAYA"}).json()["employees"]) == 2
    assert c.post(f"/api/payroll/{month}/take-off", json={"ref": ref, "from": 5}).status_code == 400
    assert c.post(f"/api/payroll/{month}/take-off", json={"ref": ref, "from": siti}).json() == {"ok": True}


def test_moving_a_card_to_a_removed_employee_leaves_it_where_it_was(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    c.delete(f"/api/payroll/{month}/employee/{siti}")
    r = c.post(f"/api/payroll/{month}/place", json={"ref": ref, "employee": siti, "move": True, "from": ali})
    assert r.json()["code"] == "EMPLOYEE_NOT_FOUND"
    assert c.get(f"/api/payroll/{month}/employee/{ali}").json()["employee"]["jobs"] == [ref]


def test_figures_that_are_not_figures_are_refused_not_a_crash(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    for changes in ({"overrides": "x"}, {"overrides": [1]}, {"entries": "x"}, {"entries": {"allowance": 5}}):
        r = change(c, month, ali, **changes)
        assert r.status_code == 400 and r.json()["code"] == "BAD_PAYROLL", changes


def test_other_files_of_a_company_can_be_taken_into_the_month(tmp_path):
    """A file set aside as "Not a time card", or read as another month and on nobody there, is listed (not as
    something that needs the user) and can be taken into this month."""
    store, client = company_client(tmp_path, month_card)
    with client as c:
        for name in (f"BINA SITI SEPT {YEAR}.png", f"BINA ZUL AUG {YEAR}.png", "BINA NOTICE.png"):
            upload(c, tmp_path, name=name)
        store.wait_idle()
        set_company(c, "BINA", "BINA")
        month = f"{YEAR}-09"
        notice = next(j["id"] for j in c.get("/api/jobs").json() if "NOTICE" in j["name"])
        zul = next(j["id"] for j in c.get("/api/jobs").json() if "ZUL" in j["name"])
        c.post("/api/payroll/file-month", json={"id": notice, "month": "none"})
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert view["items"] == [] and view["status"] != "needs"
        assert sorted((f["doc"], f["month"]) for f in view["other_files"]) == sorted([(zul, f"{YEAR}-08"), (notice, "none")])
        assert c.post("/api/payroll/file-month", json={"id": zul, "month": month}).json() == {"ok": True}
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert [f["doc"] for f in view["other_files"]] == [notice]
        placed = [i["ref"] for i in view["items"] if i["kind"] == "unplaced"]
        cards = [r for e in view["employees"] for r in c.get(f"/api/payroll/{month}/employee/{e['id']}").json()["employee"]["jobs"]]
        assert zul in placed + cards
        # a file of another month that is on an employee there is not offered
        c.post("/api/payroll/file-month", json={"id": zul, "month": f"{YEAR}-08"})
        c.get(f"/api/payroll/{YEAR}-08/company", params={"name": "BINA"})
        august = c.get(f"/api/payroll/{YEAR}-08/company", params={"name": "BINA"}).json()
        unplaced = [i for i in august["items"] if i["kind"] == "unplaced"]
        if unplaced:
            c.post(f"/api/payroll/{YEAR}-08/place", json={"ref": unplaced[0]["ref"], "employee": None})
        view = c.get(f"/api/payroll/{month}/company", params={"name": "BINA"}).json()
        assert [f["doc"] for f in view["other_files"]] == [notice]


def test_the_pay_table_of_one_company(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    change(c, month, ali, pay_basis="daily", basic_rate=80)
    rows = {r["name"]: r for r in c.get(f"/api/payroll/{month}/pay", params={"company": "MAJU JAYA"}).json()["rows"]}
    assert set(rows) == {"ALI", "SITI"}
    assert (rows["ALI"]["typed_basis"], rows["ALI"]["typed_rate"], rows["ALI"]["rate_source"]) == ("daily", 80, "typed")
    assert rows["ALI"]["pay"]["basic"] == 80 * 26 and rows["ALI"]["days_worked"] == 26
    assert rows["ALI"]["id"] == ali and "complete" in rows["ALI"] and "emp_no" in rows["ALI"]


def test_the_employee_view_refuses_other_websites(maju_jaya):
    c, month, ali, siti, ref = maju_jaya
    r = c.put(f"/api/payroll/{month}/employee/{ali}", json={"changes": {"name": "X"}},
              headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_the_employee_view_says_which_cards_follow_a_confirmed_layout(tmp_path):
    """On such a card the map says which column holds the hours, so the view says the Hours column list does not
    apply to it."""
    store, client = company_client(tmp_path, report_2_card)
    with client as c:
        month, view = layout_month(c, store, tmp_path)
        who = view["employees"][0]["id"]
        [item] = [i for i in view["items"] if i["kind"] == "layout"]
        assert [k["mapped"] for k in c.get(f"/api/payroll/{month}/employee/{who}").json()["cards"]] == [False]
        c.put("/api/layouts", json={"doc": item["doc"], "page": item["page"], "columns": report_2_map()})
        assert [k["mapped"] for k in c.get(f"/api/payroll/{month}/employee/{who}").json()["cards"]] == [True]
