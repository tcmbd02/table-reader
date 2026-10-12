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
