"""Tests for pdftext.py: pages of a computer-made PDF filled in from the PDF's own text, once Claude has read one page."""
import pypdfium2 as pdfium
import pytest

import ocr
import pdftext
from jobs import Jobs
from tests.helpers import cell, good, make_pdf, record, text_pdf

LABELS = ("Date", "Day", "In", "Out", "Shift", "Total", "OT")
X = {"Date": 40, "Day": 110, "In": 160, "Out": 200, "Shift": 226, "Total": 300, "OT": 350}   # Out and Shift nearly touch


def report(emp, name, rows, total):
    """One worker's page of a clock-system report: (x, y, text) for text_pdf. ``rows`` = [{column: text}]."""
    words = [(220, 800, "Individual Attendance Report"),
             (40, 780, "Emp Code"), (100, 780, emp), (200, 780, "Name :"), (240, 780, name),
             *[(X[c], 750, c) for c in LABELS]]
    for n, row in enumerate(rows):
        words += [(X[c], 730 - 14 * n, v) for c, v in row.items()]
    return words + [(40, 730 - 14 * len(rows) - 6, "Total"), (X["Total"], 730 - 14 * len(rows) - 6, total)]


def day(d, weekday, hours="9.00", ot=None, **more):
    if hours is None:
        return {"Date": f"{d:02d}-09-2026", "Day": weekday, "Shift": "OFF-DAY"}
    return {"Date": f"{d:02d}-09-2026", "Day": weekday, "In": "7.55", "Out": "17.02", "Shift": "N", "Total": hours,
            **({"OT": ot} if ot else {}), **more}


def claude(emp, name, rows, total, **change):
    """Claude's reading of such a page (every cell certain), as the app stores it."""
    full = [{c: good(row.get(c, "")) for c in LABELS} for row in rows]
    rec = record(full, labels=LABELS, header=[("Report", good("Individual Attendance Report")), ("Emp Code", good(emp)),
                                              ("Name", good(name)), ("Total hours", good(total))])
    rec["rotated_clockwise"] = 0
    for (row, col), value in change.get("cells", {}).items():
        rec["rows"][row]["cells"][col] = value
    return rec


PAGE1 = [day(1, "Tue"), day(2, "Wed", "10.50", "1.50"), day(6, "Sun", None)]
PAGE2 = [day(1, "Tue", "8.00"), day(2, "Wed"), day(3, "Thu", "11.25", "2.25"), day(6, "Sun", None)]


def lines_of(tmp_path, pages):
    path = tmp_path / "report.pdf"
    path.write_bytes(text_pdf(pages))
    pdf = pdfium.PdfDocument(str(path))
    assert all(pdftext.is_text_page(p) for p in pdf)
    return [pdftext.page_lines(p) for p in pdf]


def values(rec):
    return [[row["cells"][c]["value"] for c in rec["column_labels"]] for row in rec["rows"]]


def test_a_later_page_is_filled_in_from_its_own_text(tmp_path):
    first, second = lines_of(tmp_path, [report("E01", "ALI BIN ABU", PAGE1, "19.50"), report("E02", "SITI", PAGE2, "28.25")])
    layout = pdftext.learn(claude("E01", "ALI BIN ABU", PAGE1, "19.50"), first)
    assert layout is not None
    page = pdftext.apply(layout, second)
    assert page["column_labels"] == list(LABELS)                      # Claude's names for the columns and fields
    assert values(page) == [["01-09-2026", "Tue", "7.55", "17.02", "N", "8.00", None],
                            ["02-09-2026", "Wed", "7.55", "17.02", "N", "9.00", None],
                            ["03-09-2026", "Thu", "7.55", "17.02", "N", "11.25", "2.25"],
                            ["06-09-2026", "Sun", None, None, "OFF-DAY", None, None]]
    assert {f["label"]: f["cell"]["value"] for f in page["header_fields"]} == {
        "Report": "Individual Attendance Report", "Emp Code": "E02", "Name": "SITI", "Total hours": "28.25"}
    assert page["source"] == "pdf-text" and page["notes"] == [pdftext.NOTE] and page["rotated_clockwise"] == 0
    assert not any(c["needs_review"] for row in page["rows"] for c in row["cells"].values())


@pytest.mark.parametrize("change,reason", [
    ({(1, "Total"): good("10.80")}, "row 2 is not printed as Claude read it"),         # Claude read a digit differently
    ({(0, "In"): ocr.normalize_cell(cell(None, raw="7.5?", reason="faint"))}, "Claude doubted a cell"),
    ({(2, "Shift"): good("")}, "row 3 is not printed as Claude read it"),              # Claude left a printed word out
])
def test_no_layout_unless_claudes_whole_reading_is_what_is_printed(tmp_path, change, reason):
    first, = lines_of(tmp_path, [report("E01", "ALI", PAGE1, "19.50")])
    why = []
    assert pdftext.learn(claude("E01", "ALI", PAGE1, "19.50", cells=change), first, why) is None and why == [reason]


def test_a_field_claude_worded_differently_gives_no_layout(tmp_path):
    first, = lines_of(tmp_path, [report("E01", "ALI", PAGE1, "19.50")])
    rec = claude("E01", "ALI", PAGE1, "19.50")
    rec["header_fields"][3]["cell"] = pdftext._cell("19.5 hours")
    why = []
    assert pdftext.learn(rec, first, why) is None and why == ["field 4 is not printed as Claude wrote it"]


@pytest.mark.parametrize("rows,total,what", [
    ([day(1, "Tue", extra="x")], "9.00", "a word in no known column"),
    ([day(1, "Tue"), {"Date": "02-09-2026", "Day": "Wed", "Total": "ABSENT"}], "9.00", "a shape never seen in that column"),
    ([day(1, "Tue"), {"Day": "Wed", "Total": "9.00"}, day(3, "Thu")], "27.00", "a row without its date"),
])
def test_a_page_that_does_not_fit_the_layout_goes_to_claude(tmp_path, rows, total, what):
    X["extra"] = 420
    try:
        first, other = lines_of(tmp_path, [report("E01", "ALI", PAGE1, "19.50"), report("E02", "SITI", rows, total)])
    finally:
        del X["extra"]
    layout = pdftext.learn(claude("E01", "ALI", PAGE1, "19.50"), first)
    assert layout is not None and pdftext.apply(layout, other) is None, what


def test_other_wording_above_the_table_goes_to_claude(tmp_path):
    words = report("E02", "SITI", PAGE2, "28.25")
    extra_line = words + [(40, 765, "Resigned on 20-09-2026")]
    moved = [(x, y, "Staff No" if t == "Emp Code" else t) for x, y, t in words]
    first, a, b = lines_of(tmp_path, [report("E01", "ALI", PAGE1, "19.50"), extra_line, moved])
    layout = pdftext.learn(claude("E01", "ALI", PAGE1, "19.50"), first)
    assert pdftext.apply(layout, a) is None and pdftext.apply(layout, b) is None


def test_pictures_and_turned_pages_are_never_read_this_way(tmp_path):
    blank = tmp_path / "scan.pdf"
    make_pdf(blank, count=1)                                           # no text at all: a scan
    doc = pdftext.Document(blank)
    assert doc.read(1) is None and doc.learn(1, claude("E01", "ALI", PAGE1, "19.50")) is False
    doc.close()
    picture = pdftext.Document(tmp_path / "photo.png")                # not a PDF
    assert picture.read(1) is None
    rec = claude("E01", "ALI", PAGE1, "19.50")
    rec["rotated_clockwise"] = 90
    first, = lines_of(tmp_path, [report("E01", "ALI", PAGE1, "19.50")])
    assert pdftext.learn(rec, first) is None


# ------------------------------------------------------------------------------------------------ in the app
def reader_for(readings, calls):
    def read(image):
        number = int(image.stem.split("-")[1])
        calls.append(number)
        return readings[number]()
    return read


def test_claude_reads_one_page_and_the_rest_come_from_the_pdf(tmp_path):
    pdf = text_pdf([report("E01", "ALI", PAGE1, "19.50"), report("E02", "SITI", PAGE2, "28.25"),
                    report("E03", "ZUL", PAGE1, "19.50")])
    calls = []
    store = Jobs(tmp_path / "jobs", reader=reader_for({1: lambda: claude("E01", "ALI", PAGE1, "19.50")}, calls))
    job = store.create_job("MAJU JAYA SEPT 26.pdf", pdf)
    assert store.wait_idle()
    assert store.get_job(job["id"])["status"] == "done" and calls == [1]            # Claude was asked once, not three times
    pages = store.load_result(job["id"])["pages"]
    assert [p.get("source") for p in pages] == [None, "pdf-text", "pdf-text"] and [p["page"] for p in pages] == [1, 2, 3]
    assert [f["cell"]["value"] for f in pages[2]["header_fields"]] == ["Individual Attendance Report", "E03", "ZUL", "19.50"]
    assert pages[1]["rows"][2]["cells"]["OT"]["value"] == "2.25" and pdftext.NOTE in pages[1]["notes"]
    store.shutdown()


def test_when_claudes_page_gives_no_layout_claude_reads_every_page(tmp_path):
    pdf = text_pdf([report("E01", "ALI", PAGE1, "19.50"), report("E02", "SITI", PAGE2, "28.25")])
    calls = []
    wrong = lambda: claude("E01", "ALI", PAGE1, "19.50", cells={(0, "Out"): good("17.07")})     # noqa: E731
    store = Jobs(tmp_path / "jobs", reader=reader_for({1: wrong, 2: lambda: claude("E02", "SITI", PAGE2, "28.25")}, calls))
    job = store.create_job("report.pdf", pdf)
    assert store.wait_idle()
    assert calls == [1, 2] and all("source" not in p for p in store.load_result(job["id"])["pages"])
    store.shutdown()


def test_a_page_that_does_not_fit_is_read_by_claude_and_teaches_a_second_layout(tmp_path):
    late = [day(1, "Tue", late="0.25"), day(2, "Wed")]                # a column the first page never used
    X["late"] = 420
    try:
        pdf = text_pdf([report("E01", "ALI", PAGE1, "19.50"), report("E02", "SITI", late, "18.00"),
                        report("E03", "ZUL", late, "18.00")])
    finally:
        del X["late"]
    labels = LABELS + ("Late",)

    def with_late():
        rec = record([{**{c: good(r.get(c, "")) for c in LABELS}, "Late": good(r.get("late", ""))} for r in late],
                     labels=labels, header=[("Report", good("Individual Attendance Report")), ("Emp Code", good("E02")),
                                            ("Name", good("SITI")), ("Total hours", good("18.00"))])
        rec["rotated_clockwise"] = 0
        return rec

    calls = []
    store = Jobs(tmp_path / "jobs", reader=reader_for({1: lambda: claude("E01", "ALI", PAGE1, "19.50"), 2: with_late}, calls))
    job = store.create_job("report.pdf", pdf)
    assert store.wait_idle()
    pages = store.load_result(job["id"])["pages"]
    assert calls == [1, 2] and pages[2]["source"] == "pdf-text" and pages[2]["column_labels"] == list(labels)
    assert pages[2]["rows"][0]["cells"]["Late"]["value"] == "0.25" and pages[2]["header_fields"][1]["cell"]["value"] == "E03"
    store.shutdown()
