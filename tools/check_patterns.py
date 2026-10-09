"""Every server message the page may show must be translated (exact entry or a pattern) in static/i18n.js.

Run from the project folder:  .venv\\Scripts\\python tools\\check_patterns.py   (needs esprima, see check_i18n.py)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import esprima

import jobs
import ocr
import payroll
from helpers import cell, good, record

src = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")
tree = esprima.parseScript(src)
keys, patterns = set(), []
for decl in tree.body:
    if decl.type != "VariableDeclaration":
        continue
    for d in decl.declarations:
        if d.id.name == "MS":
            keys = {p.key.value for p in d.init.properties}
        if d.id.name == "MS_PATTERNS":
            for el in d.init.elements:
                patterns.append(re.compile(el.elements[0].regex.pattern))


def covered(msg):
    return msg in keys or any(p.search(msg) for p in patterns)


# 1) every plain sentence constant in the Python code that reaches the user
msgs = []
for f in ("ocr.py", "jobs.py", "pages.py", "app.py", "payroll.py"):
    text = (ROOT / f).read_text(encoding="utf-8")
    for m in re.finditer(r'OcrError\(\s*"[A-Z_]+",\s*((?:f?"[^"\n]*"\s*)+)\)', text):
        parts = re.findall(r'f?"([^"\n]*)"', m.group(1))
        msg = "".join(parts)
        if "{" not in msg:
            msgs.append(msg)

# 2) messages with names and numbers, built the way the code builds them
msgs += [
    "Page 2 of 3: Your Claude sign-in has expired. Press Sign in (top right), then press Continue.",
    "Claude was not sure (55% confident)",
    "Claude reported a doubt it could not place (smudge: 8?5). Check the page.",
    "Claude reported a problem: overloaded. Try this file again.",
    "Claude Code did not return a reading (boom). Try again; if it keeps happening, open Claude Code once on its own to check that it works.",
    "Claude took longer than 5 minutes on this page. Try again, or use a smaller or clearer picture.",
    "scan.pdf has 120 pages; Table Reader takes up to 100 at a time. Split the file and add the parts separately.",
    "Page 3 of scan.pdf could not be drawn. Open the file on your computer to check it, then add it again.",
    "card.jpg is larger than 150 MB. Scan it at a lower quality or split it into smaller files.",
    "card.jpg could not be saved. Check that the computer has free disk space, then add it again.",
    "card.jpg has not been read completely yet.",
    "'Food Allowance' is in the Allowance list twice. Use another name.",
]
# payroll issues from the real calculation
p = payroll.default_plan("2026-09")
rows = [{"Date": good("1"), "Total": cell(None, raw="9?", reason="smudged")},
        {"Date": good("2"), "Total": good("abc")},
        {"Date": cell(None, raw="?", reason="x"), "Total": good("9")},
        {"Date": good("5/10"), "Total": good("9")},
        {"Date": good("31"), "Total": good("9")},
        {"Date": good("zz"), "Total": good("9")},
        {"Date": good("3"), "Total": good("9")}]
rec = record(rows, labels=("Date", "Total")); rec["page"] = 1
pages_ = jobs.merged_pages({"pages": [rec]}, {"edits": []})
rec2 = record([{"Date": good("3"), "Total": good("8")}], labels=("Date", "Total")); rec2["page"] = 1
pages2 = jobs.merged_pages({"pages": [rec2]}, {"edits": []})
rec3 = record([{"Date": good("3"), "Hari": good("8")}], labels=("Date", "Hari")); rec3["page"] = 1
pages3 = jobs.merged_pages({"pages": [rec3]}, {"edits": []})
emp = {"id": "e1", "emp_no": "", "name": "", "jobs": [], "hours_column": None, "overrides": {}}
r = payroll.calculate(p, [("card A", pages_), ("card B", pages2), ("card C", pages3)], emp)
msgs += [i["text"] for i in r["issues"]]
msgs += [i["text"] for i in payroll.calculate(p, [], emp)["issues"]]

# month grids (rows = workers, a column per day)
labels = ("Name",) + tuple(str(d) for d in range(1, 32)) + ("Remark",)
marks = {str(d): good("✓") for d in range(1, 32)}
marks.update({"3": good("S"), "4": good("AL"), "16": good("PH"), "31": good("✓")})
marks["5"] = {**cell(None, raw="✓?", reason="faint")}
grid_rec = record([{"Name": good("ALI"), **marks, "Remark": good("9")}], labels=labels); grid_rec["page"] = 1
grid_pages = jobs.merged_pages({"pages": [grid_rec]}, {"edits": []})
two = record([{"Name": good(n), **{str(d): good("✓") for d in range(1, 32)}, "Remark": good("")} for n in ("A", "B")],
             labels=labels); two["page"] = 1
msgs += [i["text"] for i in payroll.calculate(p, [("grid.jpg (row 2)", grid_pages)], emp)["issues"]]
clean = record([{"Name": good("ALI"), **{str(d): good("✓" if d < 31 else "") for d in range(1, 32)}, "Remark": good("9")}],
               labels=labels); clean["page"] = 1
msgs += [i["text"] for i in payroll.calculate(p, [("grid.pdf (page 1, row 2)", jobs.merged_pages(
    {"pages": [clean]}, {"edits": []}))], emp)["issues"]]
msgs += [i["text"] for i in payroll.calculate(p, [("grid.jpg", jobs.merged_pages({"pages": [two]}, {"edits": []}))],
                                              emp)["issues"]]

# IN/OUT time cards
io_rows = [{"Date": good("1"), "IN": good("07:55"), "OUT": cell(None, raw="1?:0?", reason="smudged")},
           {"Date": good("2"), "IN": good("07:55"), "OUT": good("")},
           {"Date": good("3"), "IN": good("-"), "OUT": good("17:00")},
           {"Date": good("4"), "IN": good("7.55 AM ✓"), "OUT": good("17:00")},
           {"Date": good("7"), "IN": good("8.00"), "OUT": good("5.00")}]
io_rec = record(io_rows, labels=("Date", "IN", "OUT")); io_rec["page"] = 1
msgs += [i["text"] for i in payroll.calculate(p, [("in-out.jpg", jobs.merged_pages({"pages": [io_rec]}, {"edits": []}))],
                                              emp)["issues"]]

# Million file refusals, built by the real code
mapping = payroll.load_office_mapping(ROOT / "million" / "office-mapping.csv")
rows2 = [{"Date": good(str(d)), "Total": good("9")} for d in range(1, 31)]
rec4 = record(rows2, labels=("Date", "Total")); rec4["page"] = 1
docs = [("card", jobs.merged_pages({"pages": [rec4]}, {"edits": []}))]
emps = [dict(emp, id=f"e{k}", emp_no=no, name=f"W{k}", entries={"allowance": {"loan cleaner": 5.0}}, zakat=1.0)
        for k, no in enumerate(["", " X1", "X2", "X2"])]
res = [payroll.calculate(p, docs, e) for e in emps]
res[2]["values"]["encashing_leave"]["value"] = 2.0
res[3]["values"]["lateness"]["value"] = -1.0
res[3]["complete"] = False
for allow in (False, True):
    try:
        payroll.build_xls(p, res, mapping=mapping, allow_incomplete=allow)
    except ocr.OcrError as exc:
        msgs += exc.message.split("\n")
ok = [payroll.calculate(p, docs, dict(emp, id=f"o{k}", emp_no=f"OK{k}", name=f"W{k}")) for k in range(2)]
for r_ in ok:
    r_["complete"] = False                                       # INCOMPLETE: asks before making the file
for n in (1, 2):
    try:
        payroll.build_xls(p, ok[:n], mapping=mapping)
    except ocr.OcrError as exc:
        msgs.append(exc.message)
    try:
        payroll.build_xls(p, ok[:n], mapping=mapping, known={"zz"})   # not in employees.txt: asks too
    except ocr.OcrError as exc:
        msgs.append(exc.message)
msgs += ["Payroll 2026-09 (Million).xls could not be saved. If it is open in Excel, close it and try again.",
         "The Million column table office-mapping.csv was not found.",
         "The Million column table (C:\\x\\office-mapping.csv) could not be used: column 3 is used for both A and B. "
         "Fix it to match Million's File Format Setting, then try again."]

bad = [m for m in msgs if not covered(m)]
print(f"{len(msgs)} messages checked, {len(bad)} not translated")
for m in bad:
    print("  NOT TRANSLATED:", m)
