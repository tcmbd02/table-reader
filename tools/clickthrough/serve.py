"""Server for click-throughs, on made-up data: MAJU JAYA (ALI, SITI on day cards; ZUL on a confirmed card layout; AMIN
on an August card) and A & B (M) (SITI). With SLOW_FILE set, one more file is added after the start and takes a few
seconds to read.

python serve.py <repo> <home> <port>   (a fresh <home> is seeded first)"""
import io
import os
import sys
import threading
import time
from pathlib import Path

repo, home, port = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
os.environ["TABLE_READER_HOME"] = str(home)
os.environ["TABLE_READER_MILLION_EMPLOYEES"] = str(home / "no-employees.txt")
sys.path.insert(0, str(repo))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import app as app_module  # noqa: E402
from jobs import Jobs, default_root  # noqa: E402
from tests.test_app import month_card, report_2_card, report_2_map, YEAR  # noqa: E402

mode = {"card": month_card, "slow": False}


def reader(image):
    if mode["slow"]:
        time.sleep(10)
    return mode["card"](image)


def png():
    b = io.BytesIO()
    Image.new("RGB", (60, 40), "white").save(b, "PNG")
    return b.getvalue()


def add(c, store, name):
    c.post("/api/jobs", files=[("files", (name, png(), "application/octet-stream"))])
    store.wait_idle()


fresh = not (home / "jobs").exists()
store = Jobs(default_root(), reader=reader)
application = app_module.create_app(store)
if fresh:
    with TestClient(application, base_url="http://localhost") as c:
        for name in (f"MAJU JAYA ALI SEPT {YEAR}.png", f"MAJU JAYA SITI SEPT {YEAR}.png", f"MAJU JAYA AMIN AUG {YEAR}.png"):
            add(c, store, name)
        mode["card"] = report_2_card
        add(c, store, f"MAJU JAYA ZUL SEPT {YEAR}.png")
        mode["card"] = month_card
        add(c, store, f"A & B (M) SITI SEPT {YEAR}.png")
        for j in c.get("/api/jobs").json():
            c.put(f"/api/jobs/{j['id']}/company", json={"company": "A & B (M)" if j["name"].startswith("A & B") else "MAJU JAYA"})
        month = f"{YEAR}-09"
        files = c.get(f"/api/payroll/{month}/files").json()          # opening the month: the cards join
        for items in files["files"].values():
            for item in items:
                if item["kind"] == "layout":
                    print("layout saved:", c.put("/api/layouts", json={"doc": item["doc"], "page": item["page"],
                                                                        "columns": report_2_map()}).status_code)
        people = c.get(f"/api/payroll/{month}/people").json()
        print("employees:", sum(len(r["employees"]) for r in people["companies"]))
    store = Jobs(default_root(), reader=reader)
    application = app_module.create_app(store)

if os.environ.get("SLOW_FILE"):
    def slow():
        mode["slow"] = True
        store.create_job(f"MAJU JAYA SLOW SEPT {YEAR}.png", png())
    threading.Timer(2, slow).start()

import uvicorn  # noqa: E402

uvicorn.run(application, host="127.0.0.1", port=port, log_level="warning")
