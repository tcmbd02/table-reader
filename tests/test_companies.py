import companies


def result(issues, id="e1"):
    return {"id": id, "issues": [{"kind": k, "text": text, "job": None} for k, text in issues]}


def worker(id="e1", jobs=("d1",), **kw):
    return {"id": id, "emp_no": "MJ(1)", "name": "ALI", "jobs": list(jobs), **kw}


def test_issues_become_one_item_per_kind_in_a_fixed_order():
    r = result([("missing", "No entry found for day 4."), ("unclear", "Day 3 is unclear."),
                ("conflict", "Day 9 is written twice."), ("unclear", "Day 7 is unclear."),
                ("column", "No hours column.")])
    items = companies.issue_items(r, worker(jobs=("d1", "d2#p2", "d1#p1")))
    assert [i["kind"] for i in items] == ["look", "days", "column"]
    assert items[0] == {"kind": "look", "employee": "e1", "cards": ["d1", "d2"], "places": 0,
                        "texts": ["Day 3 is unclear.", "Day 7 is unclear."]}
    assert items[1]["texts"] == ["No entry found for day 4.", "Day 9 is written twice."]


def test_information_and_the_empty_employee_no_are_not_items_here():
    r = result([("leave", "The card marks leave on day 5."), ("removed", "1 time-card file was taken off."),
                ("empno", "Employee No. is empty.")])
    assert companies.issue_items(r, worker()) == []


def test_an_employee_with_no_card_and_a_text_said_twice():
    r = result([("nodocs", "No document chosen for this employee yet."), ("total", "Total differs."),
                ("total", "Total differs.")])
    items = companies.issue_items(r, worker(jobs=()))
    assert [(i["kind"], i["texts"], i["cards"]) for i in items] == [
        ("days", ["Total differs."], []), ("nocard", ["No document chosen for this employee yet."], [])]


def test_every_issue_that_makes_an_employee_incomplete_is_an_item():
    # the kinds payroll.calculate treats as "not complete" (see `complete =` there) must all map to an item
    blocking = ("unclear", "conflict", "column", "missing", "nodocs", "date", "total", "flat", "daytype")
    assert all(k in companies.ITEM_OF_ISSUE for k in blocking)


import payroll


def figures(days=26, ot=0.0, rest=0):
    return {"days_worked": {"value": days}, "ot_1_5": {"value": ot}, "ot_rest_day": {"value": rest}}


def calc(id, issues=(), **kw):
    return {**result(issues, id=id), "values": figures(**kw)}


def plan_of(*people):
    p = payroll.default_plan("2026-09")
    p["employees"] = list(people)
    return p


LISTED = [{"emp_no": "MJ(1)", "name": "ALI BIN ABU"}, {"emp_no": "MJ(2)", "name": "SITI"}]


def test_employee_no_items():
    p = plan_of(worker("e1", emp_no="MJ(1)", name="ALI"),            # in Million under a name that fits
                worker("e2", emp_no="mj(2)", name="ZUL"),            # Million has another name for it
                worker("e3", emp_no="MJ(9)", name="AMIN"),           # not in Million's list
                worker("e4", emp_no="", name="SITI"),                # Million offers a number
                worker("e5", emp_no="", name="TAN"),                 # nothing known
                worker("e6", emp_no="X1", name="LIM"), worker("e7", emp_no="x1", name="OMAR"))   # one number, two people
    offers = {"e4": {"emp_no": "MJ(2)", "name": "SITI"}}
    items = companies.emp_no_items(p, LISTED, offers)
    assert items["e1"] == []
    assert items["e2"] == [{"kind": "empno", "employee": "e2", "why": "name", "emp_no": "mj(2)", "million_name": "SITI"}]
    assert items["e3"] == [{"kind": "million_new", "employee": "e3", "emp_no": "MJ(9)"}]
    assert items["e4"] == [{"kind": "offer", "employee": "e4", "emp_no": "MJ(2)", "million_name": "SITI"}]
    assert items["e5"] == [{"kind": "empno", "employee": "e5", "why": "empty"}]
    assert items["e6"] == [{"kind": "empno", "employee": "e6", "why": "shared", "emp_no": "X1", "count": 2}]
    assert items["e7"] == [{"kind": "empno", "employee": "e7", "why": "shared", "emp_no": "x1", "count": 2}]


def test_without_millions_list_no_number_is_checked_against_it():
    p = plan_of(worker("e1", emp_no="MJ(9)", name="AMIN"))
    assert companies.emp_no_items(p, None, {}) == {"e1": []}


def test_employee_status():
    assert companies.employee_status([]) == "ready"
    assert companies.employee_status([{"kind": "million_new"}]) == "million"
    assert companies.employee_status([{"kind": "million_new"}, {"kind": "look"}]) == "needs"


def test_a_companys_view_lists_its_items_and_only_its_employees():
    p = plan_of(worker("e1", name="ALI"), worker("e2", emp_no="MJ(9)", name="AMIN"), worker("e3", emp_no="B1", name="ZUL"))
    results = [calc("e1", [("unclear", "Day 3 is unclear.")], days=24, ot=12.0, rest=1), calc("e2"), calc("e3")]
    files = [{"kind": "unplaced", "ref": "d9", "name": "MAJU JAYA SEPT 26 (3).jpeg", "readable": True}]
    view = companies.company_view("MAJU JAYA", p, results, ["MAJU JAYA", "MAJU JAYA", "BINA"], LISTED, {}, {}, files)
    assert view["company"] == "MAJU JAYA" and view["status"] == "needs" and view["needs"] == 2 and view["waiting"] == 1
    assert [i["kind"] for i in view["items"]] == ["unplaced", "look"]          # files first, then employees in order
    assert view["employees"] == [
        {"id": "e1", "emp_no": "MJ(1)", "name": "ALI", "days_worked": 24, "ot_1_5": 12.0, "ot_rest_day": 1, "status": "needs"},
        {"id": "e2", "emp_no": "MJ(9)", "name": "AMIN", "days_worked": 26, "ot_1_5": 0.0, "ot_rest_day": 0, "status": "million"}]
    assert view["million_new"] == [{"emp_no": "MJ(9)", "name": "AMIN"}]


def test_company_status_and_the_catch_all_for_an_employee_the_month_file_holds_back():
    p = plan_of(worker("e1", name="ALI"), worker("e2", emp_no="MJ(9)", name="AMIN"))
    results = [calc("e1"), calc("e2")]
    view = companies.company_view("MAJU JAYA", p, results, ["MAJU JAYA", "MAJU JAYA"], LISTED, {}, {}, [])
    assert view["status"] == "million" and view["needs"] == 0 and view["waiting"] == 1
    view = companies.company_view("MAJU JAYA", p, results, ["MAJU JAYA", "MAJU JAYA"], None, {}, {}, [])
    assert view["status"] == "ready"                                    # no list from Million: nothing to wait for
    # the month file would hold e1 back for a reason no item names: it is shown, never silently "Ready"
    held = {"e1": ["Annual Leave is not a line of the office file."], "e2": ["Employee No. MJ(9) is not in the Million employee list."]}
    view = companies.company_view("MAJU JAYA", p, [calc("e1"), calc("e2")], ["MAJU JAYA", "MAJU JAYA"], LISTED, {}, held, [])
    assert [(i["kind"], i["employee"]) for i in view["items"]] == [("held", "e1")]        # e2's reason is its own item
    assert view["items"][0]["texts"] == ["Annual Leave is not a line of the office file."]
    assert companies.company_view("SURIA", p, [calc("e1"), calc("e2")], ["MAJU JAYA", "MAJU JAYA"], None, {}, {}, [])["status"] == "none"


def test_the_overview_puts_companies_that_need_the_user_first_and_keeps_the_ones_without_a_company():
    def view(company, status, needs=0, waiting=0, employees=1):
        return {"company": company, "status": status, "needs": needs, "waiting": waiting,
                "employees": [{"status": "ready"}] * employees}

    out = companies.overview([view("MAJU JAYA", "ready", employees=6), view("acme", "needs", needs=5, employees=9),
                              view("", "needs", needs=1, employees=0), view("TEGUH", "million", waiting=1, employees=4),
                              view("BINA", "needs", needs=2, employees=3)], ["SURIA", "MAJU JAYA"])
    assert [(c["company"], c["status"]) for c in out["companies"]] == [
        ("acme", "needs"), ("BINA", "needs"), ("", "needs"), ("MAJU JAYA", "ready"), ("TEGUH", "million"), ("SURIA", "none")]
    assert out["companies"][0] == {"company": "acme", "employees": 9, "status": "needs", "needs": 5, "waiting": 0,
                                   "own": False}
    # every employee in these made-up views is "ready" (an employee can be ready in a company that still needs the user)
    assert out["ready_companies"] == 2 and out["ready_employees"] == 6 + 9 + 0 + 4 + 3


def card(ref, name="MAJU JAYA SEPT 26.jpeg"):
    return {"ref": ref, "name": name, "company": "MAJU JAYA", "pages": []}


def test_cards_on_no_employee():
    p = plan_of(worker("e1", jobs=("d1", "d2#p1", "d3#p1r2")))
    cands = [card("d1"), card("d2#p1"), card("d2#p2"), card("d2"), card("d3#p1r1"), card("d3#p1r2"), card("d3#p1"),
             card("d4"), card("d5#p1")]
    # d2 as a whole and d3's page 1 as a whole are covered by the parts already chosen
    assert [c["ref"] for c in companies.unplaced(p, cands)] == ["d2#p2", "d3#p1r1", "d4", "d5#p1"]
    p = plan_of(worker("e1", jobs=("d5",)), worker("e2", jobs=("d3#p1",)))
    assert [c["ref"] for c in companies.unplaced(p, cands)] == ["d1", "d2#p1", "d2#p2", "d2", "d4"]


def test_an_employee_waiting_for_million_still_shows_another_reason_the_file_holds_them_back():
    p = plan_of(worker("e1", emp_no="MJ(9)", name="AMIN"), worker("e2", emp_no="MJ(8)", name="ZUL"))
    held = {"e1": ["Zakat is not a figure of the office file."],                     # the file names this reason first
            "e2": ["Employee No. MJ(8) is not in the Million employee list."]}       # only what "New in Million" says
    view = companies.company_view("MAJU JAYA", p, [calc("e1"), calc("e2")], ["MAJU JAYA", "MAJU JAYA"], LISTED, {}, held, [])
    assert [(i["kind"], i["employee"], i["texts"]) for i in view["items"]] == [
        ("held", "e1", ["Zakat is not a figure of the office file."])]
    assert view["status"] == "needs" and view["waiting"] == 2
    assert [e["status"] for e in view["employees"]] == ["needs", "million"]


# ------------------------------------------------------------------------------------------- the one-look panel
def mcell(value, review=False, raw=None, reason=None, edited=False):
    """A cell as jobs.merged_pages gives it."""
    return {"value": value, "raw_text": value if raw is None else raw, "confidence": 30 if review else 95,
            "unclear_reason": reason, "needs_review": review, "edited": edited, "claude_value": value}


def mpage(number, labels, rows):
    return {"page": number, "column_labels": list(labels), "header_fields": [], "quality": "CLEAR", "notes": [],
            "rows": [{"cells": dict(zip(labels, row))} for row in rows]}


def at(doc, page, row, day, *columns):
    return {"doc": doc, "page": page, "row": row, "day": day, "columns": list(columns)}


def placed(kind, text, where):
    return {"kind": kind, "text": text, "job": None, "at": where}


CARD = ("Date", "Total", "OT")


def test_look_cards_one_card_per_document_in_card_order():
    d1 = [mpage(1, CARD, [[mcell("1"), mcell(None, True, "9?", "smudged"), mcell("0")]]),
          mpage(2, CARD, [[mcell("2"), mcell(None, True, "", "faded"), mcell("0")]])]
    d2 = [mpage(1, CARD, [[mcell("3"), mcell("abc"), mcell("0")]])]
    r = {"id": "e1", "issues": [placed("unclear", "d1 p2", at("d1", 2, 0, 2, "Date", "Total")),
                                placed("unclear", "d1 p1", at("d1", 1, 0, 1, "Date", "Total")),
                                placed("unclear", "d2", at("d2", 1, 0, 3, "Date", "Total")),
                                {"kind": "missing", "text": "No entry for day 4.", "job": None}]}
    cards = companies.look_cards(r, worker(jobs=("d2", "d1#p1", "d1#p2")), {"d1": d1, "d2": d2},
                                 {"d1": "one.pdf", "d2": "two.png"})
    assert [(c["doc"], c["name"]) for c in cards] == [("d2", "two.png"), ("d1", "one.pdf")]
    assert [(line["page"], line["row"], line["day"], line["texts"]) for line in cards[1]["lines"]] == [
        (1, 0, 1, ["d1 p1"]), (2, 0, 2, ["d1 p2"])]
    total = cards[1]["lines"][0]["cells"][1]
    assert total == {"column": "Total", "value": None, "raw_text": "9?", "needs_review": True,
                     "unclear_reason": "smudged", "edited": False}


def test_a_line_with_two_problems_is_one_line_with_both_columns_and_texts():
    d1 = [mpage(1, CARD, [[mcell("1"), mcell(None, True, "9?"), mcell(None, True, "?")]])]
    r = {"id": "e1", "issues": [placed("unclear", "hours", at("d1", 1, 0, 1, "Date", "Total")),
                                placed("unclear", "ot", at("d1", 1, 0, 1, "Date", "Total", "OT"))]}
    [card] = companies.look_cards(r, worker(), {"d1": d1}, {"d1": "one.pdf"})
    [line] = card["lines"]
    assert [c["column"] for c in line["cells"]] == ["Date", "Total", "OT"] and line["texts"] == ["hours", "ot"]


def test_two_days_of_one_grid_row_are_two_lines():
    labels = ("Name", "1", "2")
    d1 = [mpage(1, labels, [[mcell("ALI"), mcell(None, True, "?"), mcell(None, True, "?")]])]
    r = {"id": "e1", "issues": [placed("unclear", "day 1", at("d1", 1, 0, 1, "1")),
                                placed("unclear", "day 2", at("d1", 1, 0, 2, "2"))]}
    [card] = companies.look_cards(r, worker(), {"d1": d1}, {"d1": "grid.jpg"})
    assert [(line["day"], [c["column"] for c in line["cells"]]) for line in card["lines"]] == [(1, ["1"]), (2, ["2"])]


def test_look_cards_show_the_cells_as_they_are_now_and_leave_out_a_card_not_loaded():
    d1 = [mpage(1, CARD, [[mcell("1"), mcell("abc", edited=True), mcell("0")]])]
    r = {"id": "e1", "issues": [placed("unclear", "x", at("d1", 1, 0, 1, "Date", "Total")),
                                placed("unclear", "y", at("d9", 1, 0, 2, "Date", "Total"))]}
    [card] = companies.look_cards(r, worker(jobs=("d1", "d9")), {"d1": d1}, {"d1": "one.pdf"})
    assert card["lines"][0]["cells"][1]["edited"] is True and card["lines"][0]["cells"][1]["needs_review"] is False


def test_a_look_item_counts_places_and_keeps_only_unplaced_texts():
    r = {"id": "e1", "issues": [placed("unclear", "a", at("d1", 1, 0, 1, "Date", "Total")),
                                placed("unclear", "b", at("d1", 1, 0, 1, "Date", "Total", "OT")),
                                placed("unclear", "c", at("d1", 1, 3, 4, "Date", "Total")),
                                {"kind": "unclear", "text": "unplaced", "job": None},
                                placed("date", "day 32", at("d1", 1, 5, None, "Date", "Total")),
                                {"kind": "missing", "text": "No entry for day 4.", "job": None}]}
    look, days = companies.issue_items(r, worker())
    assert (look["places"], look["texts"]) == (2, ["unplaced"])
    assert (days["places"], days["texts"]) == (1, ["No entry for day 4."])
    only = companies.issue_items({"id": "e1", "issues": r["issues"][:1]}, worker())
    assert [(i["kind"], i["places"], i["texts"]) for i in only] == [("look", 1, [])]


# ------------------------------------------------------------------------------------------- company settings
def test_a_changed_default_is_an_item_of_a_company_with_own_settings():
    p = plan_of(worker("e1", name="ALI"))
    settings = {"own": True, "default_changed": True}
    view = companies.company_view("MAJU JAYA", p, [calc("e1")], ["MAJU JAYA"], LISTED, {}, {}, [], settings)
    assert view["items"] == [{"kind": "settings", "company": "MAJU JAYA"}] and view["status"] == "needs"
    assert view["settings"] is settings
    calm = companies.company_view("MAJU JAYA", p, [calc("e1")], ["MAJU JAYA"], LISTED, {}, {}, [],
                                  {"own": True, "default_changed": False})
    assert calm["items"] == [] and calm["status"] == "ready"


def test_the_overview_marks_own_settings():
    views = [{"company": "BINA", "status": "ready", "needs": 0, "waiting": 0, "employees": [], "settings": {"own": True}},
             {"company": "ACME", "status": "ready", "needs": 0, "waiting": 0, "employees": []}]
    rows = {r["company"]: r["own"] for r in companies.overview(views, [])["companies"]}
    assert rows == {"BINA": True, "ACME": False}


# ------------------------------------------------------------------- a card layout Table Reader does not know
import jobs as _jobs                                                           # noqa: E402
import payroll as _payroll                                                     # noqa: E402
from helpers import good, record                                              # noqa: E402

REPORT_2 = ("NO.", "DATE", "WHrs", "OT", "LIn(Min)", "E/Out(Min)", "SIGNATURE")


def card_page(labels=REPORT_2, rows=3, values=None):
    values = values or {"NO.": "1", "DATE": "{d}", "WHrs": "8", "OT": "2", "LIn(Min)": "15", "E/Out(Min)": "0",
                        "SIGNATURE": "ok"}
    rec = record([{c: good(values.get(c, "").format(d=d)) for c in labels} for d in range(1, rows + 1)], labels=labels)
    rec["page"] = 1
    return _jobs.merged_pages({"pages": [rec]}, {"edits": []})[0]


def layout_card(doc, page, name="card.jpg"):
    return {"doc": doc, "name": name, "page": page, "hours_column": None}


def test_an_unknown_layout_with_figures_is_an_item_once():
    items = companies.unknown_layouts([layout_card("d1", card_page()), layout_card("d2", card_page())], {})
    assert len(items) == 1
    assert items[0] == {"kind": "layout", "signature": _payroll.layout_signature(list(REPORT_2)), "doc": "d1",
                        "page": 1, "name": "card.jpg", "columns": ["OT", "LIn(Min)", "E/Out(Min)"]}


def test_row_numbers_text_and_few_figures_are_not_an_item():
    plain = card_page(labels=("No.", "Date", "Total", "Signature"), values={"No.": "{d}", "Date": "{d}", "Total": "8",
                                                                           "Signature": "ALI"})
    few = card_page(rows=2)                                                  # figures in fewer than 3 rows
    assert companies.unknown_layouts([layout_card("d1", plain), layout_card("d2", few)], {}) == []


def test_a_confirmed_layout_or_a_known_report_is_not_an_item():
    page = card_page()
    confirmed = {_payroll.layout_signature(list(REPORT_2)): {"columns": _payroll.map_as_read(list(REPORT_2), None)}}
    assert companies.unknown_layouts([layout_card("d1", page)], confirmed) == []
    labels = ("Date", "Shift Details / Normal", "Shift Details / Actual", "OverTime / 1.5")
    report = card_page(labels=labels, values={"Date": "{d}", "Shift Details / Normal": "8",
                                              "Shift Details / Actual": "9", "OverTime / 1.5": "1"})
    assert companies.unknown_layouts([layout_card("d2", report)], {}) == []
