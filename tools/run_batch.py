r"""Read a folder of scans/photos through the RUNNING Table Reader (port 8765), one document per file, then save each
file's CSV and one merged CSV ("File" column first). Progress (counts and statuses only, no contents) goes to stdout.

    .venv\Scripts\python -I tools\run_batch.py <source folder> <output folder> [first letters, default: all] [merged name]
    e.g.  ... "...\9. SEPTEMBER 2026" "%USERPROFILE%\Documents\Table Reader\September 2026 E-H" EFGH "September 2026 E-H"

Only names starting with one of the letters are read (case-insensitive). Excel files are skipped (not scans).
Takes ~40 s per page of the user's Claude plan. Keep Table Reader open until it finishes."""
import csv
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:8765"
SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
LETTERS = sys.argv[3].upper() if len(sys.argv) > 3 else ""
MERGED_NAME = sys.argv[4] if len(sys.argv) > 4 else "All files"
READABLE = {".pdf", ".jpg", ".jpeg", ".png"}


def call(method, path, body=None, headers=None, raw=False):
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        data = e.read()
        raise RuntimeError(f"{e.code}: {data[:300]!r}")
    return data if raw else json.loads(data)


def upload(path: Path) -> dict:
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{path.name}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
    body = head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return call("POST", "/api/jobs", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


files = sorted(p for p in SRC.iterdir() if p.is_file() and (not LETTERS or p.name[:1].upper() in LETTERS))
todo = [p for p in files if p.suffix.lower() in READABLE]
skipped = [p.name for p in files if p.suffix.lower() not in READABLE]
log(f"already in Recent files: {len(call('GET', '/api/jobs'))}")
log(f"{len(todo)} files to read, {len(skipped)} skipped (not a scan/photo)")

ids = {}
for p in todo:                                   # one upload per file: each becomes its own document
    r = upload(p)
    for c in r["created"]:
        ids[c["id"]] = p.name
    for x in r["rejected"]:
        log("REJECTED:", x["code"])
log(f"uploaded {len(ids)}")

last = None
while True:
    jobs = [j for j in call("GET", "/api/jobs") if j["id"] in ids]
    states = {}
    for j in jobs:
        states[j["status"]] = states.get(j["status"], 0) + 1
    pages = sum(j["pages_done"] or 0 for j in jobs)
    line = f"{states} pages read: {pages}"
    if line != last:
        log(line)
        last = line
    if not any(j["status"] in ("queued", "reading") for j in jobs):
        break
    time.sleep(20)

# per-file CSVs, then one merged CSV (columns = all columns seen, in first-seen order, with the file name first)
OUT.mkdir(parents=True, exist_ok=True)
merged_cols, merged_rows, done, failed = ["File"], [], 0, []
for job_id, name in ids.items():
    meta = call("GET", f"/api/jobs/{urllib.parse.quote(job_id)}")
    if meta["status"] != "done" or not any(p["rows"] for p in meta["pages"]):
        failed.append((name, meta["status"], (meta.get("error") or {}).get("code") or "NO_TABLE"))
        continue
    data = call("GET", f"/api/jobs/{urllib.parse.quote(job_id)}/csv", raw=True)
    (OUT / (Path(name).stem + ".csv")).write_bytes(data)
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    if not rows:
        continue
    header = rows[0]
    for col in header:
        if col not in merged_cols:
            merged_cols.append(col)
    for row in rows[1:]:
        rec = dict(zip(header, row))
        rec["File"] = name
        merged_rows.append(rec)
    done += 1

merged = OUT / f"{MERGED_NAME} (all files).csv"
with merged.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, lineterminator="\r\n")
    w.writerow(merged_cols)
    for rec in merged_rows:
        w.writerow([rec.get(c, "") for c in merged_cols])

to_check = sum(call("GET", f"/api/jobs/{urllib.parse.quote(i)}").get("cells_to_check") or 0 for i in ids)
log(f"DONE. files with a table: {done}, merged rows: {len(merged_rows)}, merged columns: {len(merged_cols)}, "
    f"cells still to check: {to_check}")
log(f"not finished / no table: {len(failed)}")
for name, status, code in failed:
    log("  ", status, code, "|", name.split(" SEPT")[0].split(" SEP")[0][:20])
log("skipped (Excel):", len(skipped))
