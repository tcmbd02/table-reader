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
    assert items[0] == {"kind": "look", "employee": "e1", "cards": ["d1", "d2"],
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
    assert out["companies"][0] == {"company": "acme", "employees": 9, "status": "needs", "needs": 5, "waiting": 0}
    # every employee in these made-up views is "ready" (an employee can be ready in a company that still needs the user)
    assert out["ready_companies"] == 2 and out["ready_employees"] == 6 + 9 + 0 + 4 + 3
