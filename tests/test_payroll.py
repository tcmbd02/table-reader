"""Tests for payroll.py: the calculation from confirmed cells, the issues it must raise, and the payroll file."""
import csv
import io
from pathlib import Path

import pytest
import xlrd

import jobs
import ocr
import payroll
from helpers import cell, good, million_listing, record


def merged(rows, labels=("Date", "Total")):
    """What the app feeds the calculation: Claude's reading with the user's corrections applied (jobs.merged_pages)."""
    rec = record(rows, labels=labels)
    rec["page"] = 1
    return jobs.merged_pages({"pages": [rec]}, {"edits": []})


def day(n, total):
    return {"Date": good(str(n)), "Total": good(total)}


def card(first, last, not_worked=()):
    return merged([day(d, "-" if d in not_worked else "9") for d in range(first, last + 1)])


def plan_for(month="2026-09", **kw):
    p = payroll.default_plan(month)
    p.update(kw)
    return p


def employee(**kw):
    return {"id": "e1", "emp_no": "MJ(1)", "name": "Test", "jobs": [], "hours_column": None, "overrides": {}, **kw}


def values(result):
    return {k: v["value"] for k, v in result["values"].items()}


# --------------------------------------------------------------------------------------- the worked example (two cards)
def test_default_month_has_sundays_as_rest_days():
    p = payroll.default_plan("2026-09")
    assert [d for d, t in p["day_types"].items() if t == "rest"] == ["6", "13", "20", "27"]
    assert len(p["day_types"]) == 30


def test_two_half_month_cards_give_the_figures_on_the_edit_payroll_screen():
    p = plan_for()
    p["day_types"]["16"] = "holiday"                                 # Malaysia Day, worked
    docs = [("card 1", card(1, 15, not_worked={6, 13})), ("card 2", card(16, 30, not_worked={20, 27}))]
    r = payroll.calculate(p, docs, employee())
    v = values(r)
    assert v["working_days"] == 25 and v["days_worked"] == 25 and v["public_holiday"] == 0
    assert v["ot_1_5"] == 25 and v["ot_holiday"] == 1 and v["ot_rest_day"] == 0
    assert r["complete"] and not [i for i in r["issues"] if i["kind"] != "empno"]


def test_work_on_a_rest_day_is_counted_in_days_and_not_as_overtime_hours():
    p = plan_for()
    docs = [("c", merged([day(6, "9"), day(7, "9")]))]
    v = values(payroll.calculate(p, docs, employee()))
    assert v["ot_rest_day"] == 1 and v["days_worked"] == 1 and v["ot_1_5"] == 1


def test_a_public_holiday_not_worked_is_counted_as_public_holiday():
    p = plan_for()
    p["day_types"]["16"] = "holiday"
    v = values(payroll.calculate(p, [("c", merged([day(16, "-")]))], employee()))
    assert v["public_holiday"] == 1 and v["ot_holiday"] == 0


def test_hours_below_normal_are_a_day_worked_without_overtime():
    v = values(payroll.calculate(plan_for(), [("c", merged([day(1, "8"), day(2, "6.5"), day(3, "9.5")]))], employee()))
    assert v["days_worked"] == 3 and v["ot_1_5"] == 1.5


def test_normal_hours_can_be_changed():
    p = plan_for(normal_hours=9.0)
    v = values(payroll.calculate(p, [("c", merged([day(1, "9"), day(2, "10")]))], employee()))
    assert v["ot_1_5"] == 1


# --------------------------------------------------------------------------------------------------- never guess
def test_an_unclear_total_is_left_out_and_reported_not_assumed():
    rows = [day(1, "9"), {"Date": good("2"), "Total": cell(None, "?", 20, "smudged")}]
    r = payroll.calculate(plan_for(), [("c", merged(rows))], employee())
    assert values(r)["days_worked"] == 1 and not r["complete"]
    assert any(i["kind"] == "unclear" and "day 2" in i["text"] for i in r["issues"])
    assert [d for d in r["days"] if d["day"] == 2][0]["status"] == "unclear"


def test_a_correction_in_the_document_resolves_the_unclear_total():
    rec = record([day(1, "9"), {"Date": good("2"), "Total": cell(None, "9?", 30, "smudged")}], labels=("Date", "Total"))
    rec["page"] = 1
    edited = jobs.merged_pages({"pages": [rec]}, {"edits": [{"page": 1, "row": 1, "column": "Total", "value": "9"}]})
    r = payroll.calculate(plan_for(), [("c", edited)], employee())
    assert values(r)["days_worked"] == 2 and not [i for i in r["issues"] if i["kind"] == "unclear"]


def test_days_with_no_entry_are_reported_as_missing_not_silently_zero():
    r = payroll.calculate(plan_for(), [("card 1", card(1, 15))], employee())
    assert not r["complete"]
    issue = next(i for i in r["issues"] if i["kind"] == "missing")
    assert "16-19" in issue["text"] and "21-26" in issue["text"] and "20" not in issue["text"].split("day ")[1][:3]


def test_same_day_on_two_cards_with_different_hours_is_a_conflict():
    docs = [("a", merged([day(1, "9")])), ("b", merged([day(1, "8")]))]
    r = payroll.calculate(plan_for(), docs, employee())
    assert values(r)["days_worked"] == 0 and any(i["kind"] == "conflict" for i in r["issues"])


def test_same_day_on_two_cards_with_the_same_hours_counts_once():
    docs = [("a", merged([day(1, "9")])), ("b", merged([day(1, "9")]))]
    assert values(payroll.calculate(plan_for(), docs, employee()))["days_worked"] == 1


def test_a_date_for_another_month_is_not_used():
    rows = [{"Date": good("5/8"), "Total": good("9")}, day(1, "9")]
    r = payroll.calculate(plan_for(), [("c", merged(rows))], employee())
    assert values(r)["days_worked"] == 1 and any(i["kind"] == "date" for i in r["issues"])


def test_hours_that_are_not_numbers_are_reported():
    r = payroll.calculate(plan_for(), [("c", merged([day(1, "nine")]))], employee())
    assert values(r)["days_worked"] == 0 and any("not a number" in i["text"] for i in r["issues"])


def test_no_hours_column_is_reported():
    docs = [("c", merged([{"Date": good("1"), "Note": good("x")}], labels=("Date", "Note")))]
    r = payroll.calculate(plan_for(), docs, employee())
    assert any(i["kind"] == "column" for i in r["issues"]) and not r["complete"]


def test_the_hours_column_can_be_chosen():
    docs = [("c", merged([{"Date": good("1"), "Hrs A": good("9"), "Hrs B": good("12")}], labels=("Date", "Hrs A", "Hrs B")))]
    assert values(payroll.calculate(plan_for(), docs, employee(hours_column="Hrs A")))["ot_1_5"] == 1
    assert values(payroll.calculate(plan_for(), docs, employee(hours_column="Hrs B")))["ot_1_5"] == 4


def test_overrides_replace_a_figure_and_are_marked():
    r = payroll.calculate(plan_for(), [("c", card(1, 5))], employee(overrides={"lateness": 2.5}))
    assert r["values"]["lateness"] == {"value": 2.5, "computed": 0.0, "edited": True}
    assert r["values"]["days_worked"]["edited"] is False


@pytest.mark.parametrize("text,expected", [("9", 9.0), (" 8.5 ", 8.5), ("8,5", 8.5), ("9h", 9.0), ("8:30", 8.5), ("-", 0.0),
                                           ("—", 0.0), ("", 0.0), (None, 0.0), ("0", 0.0), ("nine", None), ("9 ??", None)])
def test_parse_hours(text, expected):
    assert payroll.parse_hours(text) == expected


# ------------------------------------------------------------------------------------------------------ plan checks
def test_plan_validation_accepts_a_good_plan_and_rejects_bad_ones():
    p = plan_for()
    p["employees"] = [{"id": "e1", "emp_no": " AF(1) ", "name": "X", "jobs": ["j1"], "overrides": {"lateness": 1}}]
    clean = payroll.validate_plan(p, {"j1"})
    assert clean["employees"][0]["emp_no"] == "AF(1)" and clean["employees"][0]["hours_column"] is None
    for mutate in (lambda q: q.update(normal_hours=0), lambda q: q["day_types"].update({"3": "party"}),
                   lambda q: q["day_types"].pop("30"), lambda q: q["employees"][0]["overrides"].update(nope=1),
                   lambda q: q["employees"][0]["overrides"].update(lateness=-1),
                   lambda q: q["employees"][0].update(id="bad id!"), lambda q: q.update(month="2026-13")):
        bad = plan_for()
        bad["employees"] = [{"id": "e1", "emp_no": "A", "name": "", "jobs": [], "overrides": {}}]
        mutate(bad)
        with pytest.raises(ocr.OcrError):
            payroll.validate_plan(bad, {"j1"})


def test_a_document_can_belong_to_one_employee_only_and_must_exist():
    p = plan_for()
    p["employees"] = [{"id": "a", "emp_no": "1", "name": "", "jobs": ["j1"]}, {"id": "b", "emp_no": "2", "name": "", "jobs": ["j1"]}]
    with pytest.raises(ocr.OcrError) as e:
        payroll.validate_plan(p, {"j1"})
    assert "one employee only" in e.value.message
    p["employees"] = [{"id": "a", "emp_no": "1", "name": "", "jobs": ["nope"]}]
    with pytest.raises(ocr.OcrError) as e:
        payroll.validate_plan(p, {"j1"})
    assert e.value.code == "JOB_NOT_FOUND"


# ------------------------------------------------------------------------------------------------------ the file
def test_csv_has_screen_names_and_flags_incomplete_rows():
    p = plan_for()
    docs = [("card 1", card(1, 15))]
    full = payroll.calculate(p, docs, employee())
    text = payroll.build_csv(p, [full])
    header, line = text.split("\r\n")[:2]
    assert header.startswith("Employee No.,Name,Month End Pay,Working Days,Public Holiday,Days Worked")
    assert header.endswith("Notes")
    assert line.startswith("MJ(1),Test,\"September, 2026\",26.00,") or line.startswith("MJ(1),Test,\"September, 2026\",25.00,")
    assert "INCOMPLETE" in line and "No entry found for day" in line


def test_leave_allowance_and_deduction_figures_go_to_their_own_columns():
    p = plan_for()
    p["lists"]["bik"].append({"name": "Company car", "type": "Ordinary"})
    p["employees"] = [employee(jobs=[], entries={"leave": {"Annual Leave": 2}, "allowance": {"Food Allowance": 150.5},
                                                 "deduction": {"Loan Deduction": 100}, "bik": {"Company car": 300}},
                               zakat=12, levy=5, message="Bonus next month")]
    clean = payroll.validate_plan(p, set())
    r = payroll.calculate(clean, [], clean["employees"][0])
    header, line = list(csv.reader(io.StringIO(payroll.build_csv(clean, [r]))))[:2]
    row = dict(zip(header, line))
    assert row["Leave: Annual Leave (Day)"] == "2.00" and row["Leave: Medical Leave (Day)"] == "0.00"
    assert row["Allowance: Food Allowance"] == "150.50" and row["Deduction: Loan Deduction"] == "100.00"
    assert row["Benefit In Kind (BIK): Company car"] == "300.00"
    assert row["Zakat paid by individual"] == "12.00" and row["Levy paid by individual"] == "5.00"
    assert row["Message"] == "Bonus next month" and header[-1] == "Notes"


def test_line_lists_are_checked_and_figures_for_removed_lines_are_dropped():
    p = plan_for()
    p["employees"] = [employee(entries={"allowance": {"Food Allowance": 10, "Gone": 5, "ADHOC ALLOWANCE": 0}})]
    clean = payroll.validate_plan(p, set())
    assert clean["employees"][0]["entries"]["allowance"] == {"Food Allowance": 10.0}
    del p["lists"]                                                   # a plan saved before the lists existed
    assert payroll.validate_plan(p, set())["lists"] == payroll.default_lists()
    for mutate in (lambda q: q["lists"]["leave"].append({"name": "annual leave", "type": "Pay Leave"}),
                   lambda q: q["lists"]["allowance"].append({"name": "  ", "type": ""}),
                   lambda q: q["employees"][0].update(entries={"deduction": {"Loan Deduction": -1}}),
                   lambda q: q["employees"][0].update(zakat="12"),
                   lambda q: q["employees"][0].update(message=5)):
        bad = plan_for()
        bad["employees"] = [employee()]
        mutate(bad)
        with pytest.raises(ocr.OcrError):
            payroll.validate_plan(bad, set())


def test_a_new_month_keeps_the_lines_of_the_latest_saved_month(tmp_path):
    s = payroll.PayrollStore(tmp_path / "payroll")
    p = plan_for("2026-09")
    p["lists"]["deduction"].append({"name": "UNIFORM", "type": ""})
    s.save(p)
    assert {"name": "UNIFORM", "type": ""} in s.load("2026-10")["lists"]["deduction"]
    assert s.load("2026-08")["lists"]["deduction"][-1]["name"] == "UNIFORM"


def test_csv_formula_characters_are_neutralised():
    r = payroll.calculate(plan_for(), [("c", card(1, 2))], employee(emp_no="=1+1", name="@x"))
    text = payroll.build_csv(plan_for(), [r])
    assert "'=1+1" in text and "'@x" in text


def test_store_round_trip_and_default(tmp_path):
    s = payroll.PayrollStore(tmp_path / "payroll")
    assert s.load("2026-09")["day_types"]["6"] == "rest"
    p = plan_for()
    p["day_types"]["16"] = "holiday"
    s.save(p)
    assert s.load("2026-09")["day_types"]["16"] == "holiday"
    assert s.load("2026-10")["month"] == "2026-10"
    with pytest.raises(ocr.OcrError):
        s.load("not-a-month")


# ------------------------------------------------------------------------------------------ clock-system reports
REPORT_LABELS = ("Date", "Day", "Time / In", "Time / Out", "Shift Details / Normal", "Shift Details / Late",
                 "Shift Details / EarlyOut", "Shift Details / Actual", "OverTime / 1.0", "OverTime / 1.5",
                 "OverTime / 2.0", "OverTime / 3.0", "OverTime / Flat")


def report(days, totals=None, flat=None):
    """``days`` maps day -> (actual, late, early, ot15, ot20). Every other day of September is an empty row."""
    rows = []
    for d in range(1, 31):
        actual, late, early, ot15, ot20 = days.get(d, ("", "", "", "", ""))
        rows.append({"Date": good(f"{d:02d}-09-2026"), "Day": good("Mon"), "Time / In": good(""), "Time / Out": good(""),
                     "Shift Details / Normal": good(""), "Shift Details / Late": good(late),
                     "Shift Details / EarlyOut": good(early), "Shift Details / Actual": good(actual),
                     "OverTime / 1.0": good(""), "OverTime / 1.5": good(ot15), "OverTime / 2.0": good(ot20),
                     "OverTime / 3.0": good(""), "OverTime / Flat": good((flat or {}).get(d, ""))})
    rec = record(rows, labels=REPORT_LABELS, header=[(k, good(v)) for k, v in (totals or {}).items()])
    rec["page"] = 1
    return jobs.merged_pages({"pages": [rec]}, {"edits": []})


def test_a_clock_report_is_added_up_as_printed_in_decimal_hours():
    days = {1: ("8.00", "0.25", "", "1.50", ""), 2: ("9.75", "", "0.30", "2.00", ""), 6: ("8.00", "", "", "", "8.00")}
    pages = report(days, totals={"Total Actual": "25.75", "Total Late": "0.25", "Total EarlyOut": "0.30",
                                 "Total OT 1.5": "3.50", "Total OT 2.0": "8.00"})
    r = payroll.calculate(plan_for(), [("report", pages)], employee())
    v = values(r)
    assert v["lateness"] == 0.25 and v["early_departure"] == 0.30
    assert v["ot_1_5"] == 3.50 and v["ot_2"] == 8.00                  # as printed, not worked out from normal hours
    assert v["days_worked"] == 2 and v["ot_rest_day"] == 0            # day 6 (Sunday) is in OT 2.0, not counted twice
    assert not [i for i in r["issues"] if i["kind"] in ("total", "unclear", "column")]
    assert r["days"][0]["printed"] == {"lateness": 0.25, "ot_1_5": 1.5}


def test_a_clock_report_that_does_not_match_its_printed_total_is_reported():
    pages = report({1: ("8.00", "", "", "1.50", "")}, totals={"Total OT 1.5": "2.50"})
    r = payroll.calculate(plan_for(), [("report", pages)], employee())
    assert any(i["kind"] == "total" and "OverTime / 1.5" in i["text"] and "2.50" in i["text"] for i in r["issues"])
    assert not r["complete"]


def test_an_unclear_report_figure_is_not_added():
    pages = report({1: ("8.00", "", "", "1.50", "")})
    pages[0]["rows"][0]["cells"]["OverTime / 1.5"] = {**cell(None, raw="1.?0", reason="smudged"), "needs_review": True}
    r = payroll.calculate(plan_for(), [("report", pages)], employee())
    assert values(r)["ot_1_5"] == 0 and not r["complete"]
    assert any("OverTime / 1.5 figure is unclear" in i["text"] for i in r["issues"])


def test_flat_overtime_on_a_report_is_left_to_the_user():
    pages = report({1: ("8.00", "", "", "", "")}, flat={1: "2.00"})
    r = payroll.calculate(plan_for(), [("report", pages)], employee())
    assert any(i["kind"] == "flat" for i in r["issues"]) and not r["complete"]


# ------------------------------------------------------------------------------- one worker per page (report PDFs)
def test_pages_with_different_workers_are_offered_one_by_one():
    pages = [{"page": n, "header_fields": [{"label": "Emp Code", "cell": good(code)}, {"label": "Name", "cell": good(nm)}]}
             for n, code, nm in ((1, "E01", "ALI"), (2, "E02", "AMIN"))]
    assert payroll.worker_parts(pages) == [{"page": 1, "label": "E01 ALI"}, {"page": 2, "label": "E02 AMIN"}]
    same = [{"page": n, "header_fields": [{"label": "Name", "cell": good("ALI")}]} for n in (1, 2)]
    assert payroll.worker_parts(same) == []                         # one worker over two pages: the whole document
    assert payroll.split_ref("job-1#p3") == ("job-1", 3) and payroll.split_ref("job-1") == ("job-1", None)


def test_a_page_and_its_whole_document_cannot_both_be_chosen():
    p = plan_for()
    p["employees"] = [employee(id="a", jobs=["j1#p1"]), employee(id="b", jobs=["j1#p2"])]
    payroll.validate_plan(p, {"j1", "j1#p1", "j1#p2"})                # different pages, different employees: fine
    p["employees"][1]["jobs"] = ["j1"]
    with pytest.raises(ocr.OcrError) as e:
        payroll.validate_plan(p, {"j1", "j1#p1", "j1#p2"})
    assert "one employee only" in e.value.message


# ------------------------------------------------------------------------------ employees added from the documents
def test_worker_name_from_the_file_name():
    assert payroll.name_from_file("MAJU JAYA ALI SEPT  26 2.jpeg", "MAJU JAYA") == "ALI"
    assert payroll.name_from_file("MAJU JAYA ALI SEPT26.jpeg", "MAJU JAYA") == "ALI"
    assert payroll.name_from_file("ACME KLC 1 SEPT 2026 (ZURA) (2).jpeg", "ACME") == "KLC ZURA"


def candidate(ref, name, company="MAJU JAYA", header=(), labels=("Date", "Total")):
    rec = record([{"Date": good("1"), labels[1]: good("8")}], labels=labels, header=header)
    rec["page"] = 1
    return {"ref": ref, "name": name, "company": company, "pages": jobs.merged_pages({"pages": [rec]}, {"edits": []})}


def test_auto_employees_groups_a_workers_cards_and_never_invents_an_employee_no():
    p = plan_for()
    ids = iter(["n1", "n2", "n3"])
    cands = [candidate("j1", "MAJU JAYA ALI SEPT 26.jpeg"), candidate("j2", "MAJU JAYA ALI SEPT 26 2.jpeg"),
             candidate("j3", "MAJU JAYA AMIN SEPT 26.jpeg", header=[("Name", good("AMIN BIN ABU"))]),
             candidate("j4", "MAJU JAYA LOG SEPT 26.jpeg", labels=("Date", "In"))]       # no hours column yet
    added, skipped, unnamed = payroll.auto_employees(p, cands, {}, lambda: next(ids))
    assert added == 2 and skipped == ["MAJU JAYA LOG SEPT 26.jpeg"] and unnamed == []
    ali, amin = p["employees"]
    assert ali["jobs"] == ["j1", "j2"] and ali["name"] == "ALI" and ali["emp_no"] == ""
    assert amin["name"] == "AMIN BIN ABU" and amin["worker_key"] == "maju jaya|name:amin bin abu"
    assert payroll.auto_employees(p, cands, {}, lambda: "x") == (0, ["MAJU JAYA LOG SEPT 26.jpeg"], [])   # nothing twice


def test_the_employee_no_typed_once_is_used_next_month():
    directory = {}
    sept = plan_for()
    payroll.auto_employees(sept, [candidate("j1", "MAJU JAYA ALI SEPT 26.jpeg")], directory, lambda: "a")
    sept["employees"][0]["emp_no"] = "MJ(7)"
    assert payroll.remember_employees(sept, directory) and directory["maju jaya|file:ali"]["emp_no"] == "MJ(7)"
    octo = plan_for("2026-10")
    payroll.auto_employees(octo, [candidate("k1", "MAJU JAYA ALI OCT 26.jpeg")], directory, lambda: "b")
    assert octo["employees"][0]["emp_no"] == "MJ(7)"
    assert payroll.validate_plan(octo, {"k1"})["employees"][0]["worker_key"] == "maju jaya|file:ali"


def test_a_card_with_an_unclear_printed_name_joins_its_pair_by_file_name():
    p = plan_for()
    cands = [candidate("j2", "MAJU JAYA ALI SEPT 26 2.jpeg"),                       # name unclear on this one
             candidate("j1", "MAJU JAYA ALI SEPT 26.jpeg", header=[("Name", good("ALI BIN ABU"))])]
    added, _, _ = payroll.auto_employees(p, cands, {}, lambda: "a")
    assert added == 1 and sorted(p["employees"][0]["jobs"]) == ["j1", "j2"]
    assert p["employees"][0]["name"] == "ALI BIN ABU"


# ------------------------------------------------------------------- month grids: one row per worker, a column per day
GRID_LABELS = ("Name",) + tuple(str(d) for d in range(1, 32)) + ("Remark",)
# September 2026 as such sheets are filled in: ticks, Sundays (6, 13, 20, 27) empty, Malaysia Day (16) PH, no day 31
SEPT_MARKS = {d: "" if d in (6, 13, 20, 27, 31) else "PH" if d == 16 else "✓" for d in range(1, 32)}


def grid_row(name, marks=None, remark="26"):
    marks = {**SEPT_MARKS, **(marks or {})}
    return {"Name": good(name) if name else good(""), **{str(d): good(v) for d, v in marks.items()}, "Remark": good(remark)}


def grid(*rows, header=(("CLEANER NAME", "ALI"),)):
    rec = record(list(rows), labels=GRID_LABELS, header=[(k, good(v)) for k, v in header])
    rec["page"] = 1
    return jobs.merged_pages({"pages": [rec]}, {"edits": []})


def holiday_16():
    p = plan_for()
    p["day_types"]["16"] = "holiday"
    return p


def test_a_grid_row_gives_days_worked_and_the_public_holiday():
    r = payroll.calculate(holiday_16(), [("grid (row 2)", grid(grid_row("AMIN")))], employee())
    v = values(r)
    assert v["working_days"] == 25 and v["days_worked"] == 25 and v["public_holiday"] == 1
    assert v["ot_1_5"] == 0 and v["ot_rest_day"] == 0 and v["ot_holiday"] == 0     # a tick is a normal day
    assert r["complete"], r["issues"]
    assert r["days"][0]["code"] == "✓" and r["days"][15]["code"] == "PH"


def test_each_worker_in_a_grid_is_offered_separately_with_the_name_in_their_row():
    pages = grid(grid_row("ALI"), grid_row("AMIN"), grid_row(""), grid_row("ZUL"))
    parts = payroll.document_parts(pages)
    assert [(p["page"], p["row"], p["label"]) for p in parts] == [(1, 1, "ALI"), (1, 2, "AMIN"), (1, 3, ""), (1, 4, "ZUL")]
    assert payroll.document_parts(grid(grid_row("ALI"))) == []                  # one worker: the file as a whole
    assert payroll.document_parts(merged([day(1, "9")])) == []                 # an ordinary card
    assert payroll.part_suffix(1, 3) == "#p1r3" and payroll.split_part("job-1#p1r3") == ("job-1", 1, 3)
    assert payroll.split_ref("job-1#p1r3") == ("job-1", 1) and payroll.split_part("job-1") == ("job-1", None, None)


def test_a_whole_grid_with_several_workers_is_not_given_to_one_employee():
    r = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI"), grid_row("AMIN")))], employee())
    assert not r["complete"] and values(r)["days_worked"] == 0
    assert any("lists 2 workers" in i["text"] for i in r["issues"])


def test_ph_on_a_working_day_of_the_calendar_is_reported():
    r = payroll.calculate(plan_for(), [("grid", grid(grid_row("ALI")))], employee())   # 16th not marked as holiday
    assert not r["complete"]
    assert any(i["kind"] == "daytype" and "day 16" in i["text"] for i in r["issues"])


@pytest.mark.parametrize("mark", ["S", "SU", "HALF", "late"])
def test_a_mark_table_reader_does_not_know_is_reported_not_guessed(mark):
    r = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", {3: mark}, remark="")))], employee())
    assert not r["complete"] and values(r)["days_worked"] == 24
    assert any(f"'{mark}' is not a mark" in i["text"] for i in r["issues"])


def test_an_unclear_grid_cell_is_left_out_and_reported():
    pages = grid(grid_row("ALI", remark=""))
    pages[0]["rows"][0]["cells"]["5"] = {**cell(None, raw="✓?", reason="faint"), "needs_review": True}
    r = payroll.calculate(holiday_16(), [("grid", pages)], employee())
    assert not r["complete"] and values(r)["days_worked"] == 24
    assert any("day 5: the mark is still unclear" in i["text"] for i in r["issues"])


def test_absent_off_and_leave_marks_are_days_not_worked():
    marks = {2: "0", 3: "OFF", 4: "AL", 5: "MC", 7: "-"}
    r = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", marks, remark="20")))], employee())
    v = values(r)
    assert v["days_worked"] == 20 and v["working_days"] == 25
    leave = [i for i in r["issues"] if i["kind"] == "leave"]
    assert leave and "4 (AL), 5 (MC)" in leave[0]["text"]
    assert r["complete"], r["issues"]                            # leave is clear: the user types it in the Leave table


def test_hours_written_in_a_grid_count_as_hours():
    r = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", {1: "10", 2: "8.5"}, remark="")))], employee())
    v = values(r)
    assert v["days_worked"] == 25 and v["ot_1_5"] == 2.5                     # (10 - 8) + (8.5 - 8)


def test_the_sheet_total_is_checked_but_never_used_as_a_figure():
    ok = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", remark="25")))], employee())
    assert ok["complete"]                                         # 25 days marked worked
    also_ok = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", remark="26")))], employee())
    assert also_ok["complete"]                                    # 25 worked + 1 PH: some sheets count it
    wrong = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", remark="22")))], employee())
    assert not wrong["complete"] and values(wrong)["days_worked"] == 25
    assert any(i["kind"] == "total" and "says 22" in i["text"] for i in wrong["issues"])
    note = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", remark="see HR")))], employee())
    assert note["complete"]                                       # a remark that is not a number is not a total


def test_a_mark_on_day_31_of_a_30_day_month_is_reported():
    r = payroll.calculate(holiday_16(), [("grid", grid(grid_row("ALI", {31: "✓"}, remark="")))], employee())
    assert not r["complete"] and any("day 31 is not in this month" in i["text"] for i in r["issues"])


def grid_candidates(pages, file="MAJU JAYA SEPT 26.jpeg", ref="g1"):
    out = []
    for p in payroll.document_parts(pages):
        rows = [{**pg, "rows": pg["rows"][p["row"] - 1:p["row"]]} for pg in pages if pg["page"] == p["page"]]
        out.append({"ref": ref + payroll.part_suffix(p["page"], p["row"]), "name": f"{file} (row {p['row']})",
                    "company": "MAJU JAYA", "pages": rows})
    return out


def test_auto_employees_makes_one_employee_per_grid_row_named_from_the_row():
    pages = grid(grid_row("ALI"), grid_row("AMIN"), grid_row(""), header=(("CLEANER NAME", "ALI"),))
    p = holiday_16()
    ids = iter(["n1", "n2", "n3"])
    added, skipped, unnamed = payroll.auto_employees(p, grid_candidates(pages), {}, lambda: next(ids))
    assert added == 2 and skipped == [] and unnamed == ["MAJU JAYA SEPT 26.jpeg (row 3)"]
    ali, amin = p["employees"]
    assert (ali["name"], ali["jobs"]) == ("ALI", ["g1#p1r1"]) and (amin["name"], amin["jobs"]) == ("AMIN", ["g1#p1r2"])
    assert amin["worker_key"] == "maju jaya|name:amin"            # not the name printed at the top (the first worker's)
    payroll.validate_plan(p, {"g1#p1r1", "g1#p1r2", "g1#p1r3"})
    results = [payroll.calculate(p, [("grid", [{**pages[0], "rows": [pages[0]["rows"][k]]}])], e)
               for k, e in enumerate(p["employees"])]
    assert [values(r)["days_worked"] for r in results] == [25, 25]


def test_the_same_worker_on_two_grid_files_becomes_one_employee():
    first = grid_candidates(grid(grid_row("ALI"), grid_row("AMIN")), ref="g1")
    second = grid_candidates(grid(grid_row("AMIN"), grid_row("ALI")), file="MAJU JAYA SEPT 26 2.jpeg", ref="g2")
    p = holiday_16()
    ids = iter(["n1", "n2"])
    added, _, _ = payroll.auto_employees(p, first + second, {}, lambda: next(ids))
    assert added == 2
    assert {e["name"]: e["jobs"] for e in p["employees"]} == {"ALI": ["g1#p1r1", "g2#p1r2"], "AMIN": ["g1#p1r2", "g2#p1r1"]}


def test_a_grid_row_and_its_whole_page_or_file_cannot_both_be_chosen():
    known = {"g1", "g1#p1", "g1#p1r1", "g1#p1r2"}
    p = plan_for()
    p["employees"] = [employee(id="a", jobs=["g1#p1r1"]), employee(id="b", jobs=["g1#p1r2"])]
    payroll.validate_plan(p, known)                                # two rows, two employees: fine
    for other in ("g1#p1", "g1"):
        p["employees"][1]["jobs"] = [other]
        with pytest.raises(ocr.OcrError):
            payroll.validate_plan(p, known)


# ------------------------------------------------------------------------------------------- IN/OUT time cards
def in_out(rows, labels=("DATE", "DAY", "IN", "OUT", "SIGN")):
    return merged([{**{c: good("") for c in labels}, labels[0]: good(str(d)), **{c: good(v) for c, v in times.items()}}
                   for d, times in rows], labels=labels)


def test_in_out_columns_are_paired_in_the_cards_order():
    assert payroll.clock_pairs(["DATE", "DAY", "IN", "OUT", "SIGN"]) == [("IN", "OUT")]
    assert payroll.clock_pairs(["Date", "Time In", "Signature", "Supervisor", "Time Out", "Signature (2)"]) == [
        ("Time In", "Time Out")]
    labels = ["DATE", "MORNING / IN", "MORNING / OUT", "AFTERNOON / IN", "AFTERNOON / OUT", "OVERTIME / IN", "OVERTIME / OUT"]
    assert payroll.clock_pairs(labels) == [(labels[1], labels[2]), (labels[3], labels[4]), (labels[5], labels[6])]
    assert payroll.clock_pairs(["Tarikh", "Masuk", "Keluar"]) == [("Masuk", "Keluar")]
    assert payroll.clock_pairs(["Date", "In"]) == [] and payroll.clock_pairs(["Date", "Out", "In"]) == []
    assert payroll.clock_pairs(["Date", "Total", "Input", "Outlet"]) == []


@pytest.mark.parametrize("text,minutes", [
    ("07:55", 475), ("7.55", 475), ("17:02:30", 1022.5), ("5.30 PM", 1050), ("5:30pm", 1050), ("5,30 p.m.", 1050),
    ("12.00 AM", 0), ("12:15 PM", 735), ("8.00 AM.", 480), ("0:00", 0),
    ("7.5", None), ("7.75", None), ("24:00", None), ("13.00 PM", None), ("530 PM", None), ("8", None), ("8.00 AM ✓", None),
    ("", None), ("abc", None)])
def test_clock_times_as_written_on_cards(text, minutes):
    assert payroll.parse_clock(text) == minutes


def test_a_single_in_out_pair_gives_out_minus_in_less_the_break():
    p = plan_for()                                                   # break 1 hour unless changed
    docs = [("card", in_out([(1, {"IN": "07:30", "OUT": "17:30"}), (2, {"IN": "8.00", "OUT": "5.00 PM"}),
                             (3, {"IN": "—", "OUT": ""}), (6, {"IN": "08:00", "OUT": "12:00"})]))]
    r = payroll.calculate(p, docs, employee())
    by_day = {d["day"]: d for d in r["days"]}
    assert by_day[1]["hours"] == 9.0 and by_day[1]["code"] == "07:30 - 17:30"
    assert by_day[1]["clock"] == {"hours": 9.0, "break": 1.0, "pairs": 1}
    assert by_day[2]["hours"] == 8.0 and by_day[3]["hours"] == 0.0 and by_day[3]["status"] == "ok"
    v = values(r)
    assert v["days_worked"] == 2 and v["ot_1_5"] == 1.0 and v["ot_rest_day"] == 1     # the 6th is a Sunday
    assert not [i for i in r["issues"] if i["kind"] == "unclear"]
    p["break_hours"] = 0.5                                           # changeable per month
    assert values(payroll.calculate(p, docs, employee()))["ot_1_5"] == 2.0            # 9.5 and 8.5 hours
    p["break_hours"] = 0
    assert {d["day"]: d for d in payroll.calculate(p, docs, employee())["days"]}[1]["clock"]["break"] == 0


def test_a_day_shorter_than_the_break_keeps_its_hours():
    r = payroll.calculate(plan_for(), [("card", in_out([(1, {"IN": "08:00", "OUT": "08:45"})]))], employee())
    assert r["days"][0]["hours"] == 0.75 and values(r)["days_worked"] == 1


def test_morning_and_afternoon_pairs_are_added_up_and_no_break_is_taken_off():
    labels = ("DATE", "MORNING / IN", "MORNING / OUT", "AFTERNOON / IN", "AFTERNOON / OUT", "OVERTIME / IN", "OVERTIME / OUT")
    rows = [(1, {labels[1]: "08:00", labels[2]: "12:00", labels[3]: "13:00", labels[4]: "17:00", labels[5]: "18:00",
                 labels[6]: "20:00"}),
            (2, {labels[1]: "08:00", labels[2]: "17:00"})]             # the whole day written in the first pair
    r = payroll.calculate(plan_for(), [("card", in_out(rows, labels=labels))], employee())
    assert r["days"][0]["hours"] == 10.0 and r["days"][0]["clock"] == {"hours": 10.0, "break": 0.0, "pairs": 3}
    assert r["days"][1]["hours"] == 8.0 and r["days"][1]["clock"]["break"] == 1.0
    assert values(r)["ot_1_5"] == 2.0


def test_in_out_days_that_cannot_be_worked_out_are_reported_and_never_guessed():
    rows = [{"DATE": good("1"), "IN": good("07:55"), "OUT": cell(None, raw="1?:0?", reason="smudged")},
            {"DATE": good("2"), "IN": good("07:55"), "OUT": good("")},
            {"DATE": good("3"), "IN": good("-"), "OUT": good("17:00")},
            {"DATE": good("4"), "IN": good("7.55 AM ✓"), "OUT": good("17:00")},
            {"DATE": good("7"), "IN": good("8.00"), "OUT": good("5.00")},        # afternoon, or a night shift?
            {"DATE": good("8"), "IN": good("20:00"), "OUT": good("05:00")}]
    r = payroll.calculate(plan_for(), [("card", merged(rows, labels=("DATE", "IN", "OUT")))], employee())
    texts = [i["text"] for i in r["issues"] if i["kind"] == "unclear"]
    assert texts[0] == "card, day 1: an IN or OUT time is still unclear. Check the yellow cell in the document."
    assert "day 2: there is an IN time (07:55) but no OUT time" in texts[1]
    assert "day 3: there is an OUT time (17:00) but no IN time" in texts[2]
    assert "day 4: '7.55 AM ✓' is not a clock time" in texts[3]
    assert "day 7: OUT 5.00 is not later than IN 8.00" in texts[4] and "day 8: OUT 05:00" in texts[5]
    assert all(d["hours"] is None and d["status"] == "unclear" for d in r["days"] if d["day"] in (1, 2, 3, 4, 7, 8))
    assert values(r)["days_worked"] == 0 and not r["complete"]


def test_a_door_system_date_with_the_year_first_is_read():
    assert payroll.parse_day("2026-09-16", 9) == (16, None)
    assert payroll.parse_day("2026-08-16", 9) == (None, "the date 2026-08-16 is not in the chosen month")
    rows = [{"Date": good("2026-09-01"), "Time In": good("07:58:10"), "Time Out": good("17:03:40")}]
    r = payroll.calculate(plan_for(), [("door", merged(rows, labels=("Date", "Time In", "Time Out")))], employee())
    assert r["days"][0]["hours"] == 8.09


def test_an_hours_column_wins_over_in_and_out_times():
    rows = [{"Date": good("1"), "IN": good("08:00"), "OUT": good("20:00"), "Total": good("9")}]
    r = payroll.calculate(plan_for(), [("card", merged(rows, labels=("Date", "IN", "OUT", "Total")))], employee())
    assert r["days"][0]["hours"] == 9.0 and r["days"][0]["clock"] is None


def test_in_out_cards_are_readable_and_the_break_is_validated():
    assert payroll.readable(in_out([(1, {"IN": "08:00", "OUT": "17:00"})])[0])
    p = plan_for()
    assert payroll.validate_plan(p, set())["break_hours"] == 1.0
    del p["break_hours"]                                             # a plan saved before IN/OUT cards
    assert payroll.validate_plan(p, set())["break_hours"] == 1.0
    for bad in (-1, 6, "1", True):
        with pytest.raises(ocr.OcrError):
            payroll.validate_plan(plan_for(break_hours=bad), set())
    assert payroll.validate_plan(plan_for(break_hours=0), set())["break_hours"] == 0.0


# ------------------------------------------------------------------------------------- Million import file (.xls)
BUNDLED_MAPPING = Path(__file__).resolve().parent.parent / "million" / "office-mapping.csv"
MAPPING = payroll.load_office_mapping(BUNDLED_MAPPING)


def million(results_of=None, n=3, **plan_kw):
    """(plan, results) for ``n`` complete employees on two half-month cards; ``results_of(k)`` adds employee fields."""
    p = holiday_16()
    p.update(plan_kw)
    docs = [("card 1", card(1, 15, not_worked={6, 13})), ("card 2", card(16, 30, not_worked={20, 27}))]
    emps = [employee(**{"id": f"e{k}", "emp_no": f"MJ({k})", "name": f"WORKER {k}", **((results_of or (lambda k: {}))(k))})
            for k in range(1, n + 1)]
    return p, [payroll.calculate(p, docs, e) for e in emps]


def read_xls(data):
    sheet = xlrd.open_workbook(file_contents=data).sheet_by_index(0)
    return sheet


def col(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1                                                    # 0-based, as xlrd counts


def test_million_file_has_the_office_columns_a_to_az_with_the_mapping_headers():
    plan, results = million()
    sheet = read_xls(payroll.build_xls(plan, results, mapping=MAPPING))
    assert sheet.name == "Import" and sheet.nrows == 4 and sheet.ncols == 52               # A..AZ
    headers = sheet.row_values(0)
    for m in MAPPING:
        assert headers[m["column"] - 1] == m["header"]
    assert headers[col("A")] == "Employee No." and headers[col("AZ")] == "Notes (not imported)"
    assert [sheet.cell_value(r, col("A")) for r in (1, 2, 3)] == ["MJ(1)", "MJ(2)", "MJ(3)"]
    assert sheet.cell_value(1, col("B")) == "WORKER 1"


def test_the_bundled_mapping_matches_the_built_in_table():
    assert [(m["field"], m["type"], m["column"], m["header"]) for m in MAPPING] == payroll.OFFICE_MAPPING
    assert len(xlrd.open_workbook(file_contents=payroll.build_xls(*million(n=1), mapping=None)).sheet_by_index(0)
               .row_values(0)) == 52                                              # whichever mapping is found


def test_million_columns_land_where_the_office_setting_reads_them():
    entries = {"allowance": {"RECAB 2.O BLC PERMIT": 50.0, "Transport Allowance": 30.0},
               "deduction": {"ALREADY PAID SALARY": 100.0, "ZAKAT": 12.5}, "leave": {"Annual Leave": 2.0}}
    plan, results = million(lambda k: {"entries": entries})          # Transport Allowance is a default line now
    sheet = read_xls(payroll.build_xls(plan, results, mapping=MAPPING))
    v = {letters: sheet.cell_value(1, col(letters)) for letters in ("C", "D", "E", "K", "O", "Q", "AC", "AK", "AT", "AY")}
    assert v == {"C": 0.0, "D": 25.0, "E": 25.0, "K": 25.0, "O": 1.0, "Q": 2.0, "AC": 50.0, "AK": 30.0, "AT": 100.0,
                 "AY": 12.5}
    # numbers are number cells (0 written explicitly), the Employee No. is a text cell
    assert all(sheet.cell_type(1, c) == xlrd.XL_CELL_NUMBER for c in range(col("C"), col("AY") + 1))
    assert sheet.cell_type(1, col("A")) == xlrd.XL_CELL_TEXT and sheet.cell_value(1, col("N")) == 0.0


def test_an_employee_no_like_007_stays_text():
    plan, results = million(lambda k: {"emp_no": "007"}, n=1)
    sheet = read_xls(payroll.build_xls(plan, results, mapping=MAPPING))
    assert sheet.cell_value(1, 0) == "007" and sheet.cell_type(1, 0) == xlrd.XL_CELL_TEXT


def refused(plan, results, code="MILLION_REFUSED", **kw):
    with pytest.raises(ocr.OcrError) as e:
        payroll.build_xls(plan, results, mapping=MAPPING, **kw)
    assert e.value.code == code
    return e.value.message


def test_million_file_is_refused_for_bad_employee_numbers():
    plan, results = million()
    results[0]["emp_no"], results[1]["emp_no"], results[2]["emp_no"] = "", " MJ(2)", "MJ(9)"
    msg = refused(plan, results)
    assert "WORKER 1: Employee No. is empty" in msg and "' MJ(2)' has a space" in msg
    plan, results = million()
    results[2]["emp_no"] = "MJ(1)"
    assert "Employee No. MJ(1) is used for two employees (WORKER 1 and WORKER 3)" in refused(plan, results)


@pytest.mark.parametrize("change,expected", [
    (lambda r: r["values"]["encashing_leave"].update(value=1.0), "Encashing Leave (Day) is 1.00"),
    (lambda r: r["values"]["lateness"].update(value=-1.0), "Lateness (Hour) is not a number"),
    (lambda r: r["values"]["ot_1"].update(value="2"), "Overtime 1 Time (Hour) is not a number"),
    (lambda r: r["entries"].setdefault("leave", {}).update({"Maternity Leave": 3.0}), "Leave 'Maternity Leave' is 3.00"),
    (lambda r: r["entries"].setdefault("allowance", {}).update({"loan cleaner": 80.0}), "Allowance 'loan cleaner' is 80.00"),
    (lambda r: r.update(zakat=15.0), "Zakat paid by individual is 15.00"),
    (lambda r: r.update(levy=5.0), "Levy paid by individual is 5.00"),
])
def test_million_file_is_refused_rather_than_lose_a_figure(change, expected):
    plan, results = million(lambda k: {"entries": {}})
    change(results[1])
    msg = refused(plan, results)
    assert f"MJ(2) WORKER 2: {expected}" in msg, msg
    assert msg.startswith("The Million file was not made. Fix these first, then download again:\n- ")


def test_a_line_the_office_file_does_not_have_is_refused_and_zero_lines_are_fine():
    plan, results = million(lambda k: {"entries": {"allowance": {"Phone Allowance": 20.0}}})
    plan["lists"]["allowance"].append({"name": "Phone Allowance", "type": "Ordinary"})
    assert "Allowance 'Phone Allowance' is 20.00" in refused(plan, results)
    plan, results = million(lambda k: {"entries": {}})
    plan["lists"]["allowance"].append({"name": "Phone Allowance", "type": "Ordinary"})
    payroll.build_xls(plan, results, mapping=MAPPING)                 # nothing on it: nothing is lost


def test_incomplete_employees_need_an_explicit_yes_and_keep_their_note():
    plan, results = million()
    results[1]["complete"] = False
    results[1]["issues"].append({"kind": "missing", "text": "No entry found for day 3 in the chosen documents.",
                                 "job": None})
    msg = refused(plan, results, code="MILLION_INCOMPLETE")
    assert msg.startswith("1 employee is marked INCOMPLETE: MJ(2) WORKER 2.")
    sheet = read_xls(payroll.build_xls(plan, results, mapping=MAPPING, allow_incomplete=True))
    assert sheet.cell_value(2, col("AZ")).startswith("INCOMPLETE - check before importing; No entry found for day 3")
    assert sheet.cell_value(1, col("AZ")) == ""
    results[0]["emp_no"] = ""                                         # hard problems are refused even with the yes
    msg = refused(plan, results, allow_incomplete=True)
    assert "Also marked INCOMPLETE: MJ(2) WORKER 2." in msg


def test_an_employee_no_that_is_not_in_employees_txt_needs_an_explicit_yes(tmp_path):
    f = tmp_path / "employees.txt"
    f.write_text("# codes in Million\n\nmj(1)\n  MJ(3)  \n", encoding="utf-8")
    known = payroll.load_million_employees(f)
    assert known == {"mj(1)", "mj(3)"}                               # case does not matter, brackets do
    plan, results = million()
    msg = refused(plan, results, code="MILLION_UNKNOWN", known=known)
    assert msg.startswith("1 Employee No. is not in the Million employee list: MJ(2) WORKER 2. ")
    assert read_xls(payroll.build_xls(plan, results, mapping=MAPPING, known=known, allow_unknown=True)).nrows == 4
    results[0]["emp_no"] = "MJ1"
    assert refused(plan, results, code="MILLION_UNKNOWN", known=known).startswith(
        "2 Employee Nos. are not in the Million employee list: MJ1 WORKER 1, MJ(2) WORKER 2. ")
    results[2]["complete"] = False                                    # asked about first, then INCOMPLETE
    refused(plan, results, code="MILLION_UNKNOWN", known=known, allow_incomplete=True)
    refused(plan, results, code="MILLION_INCOMPLETE", known=known, allow_unknown=True)


def test_no_employee_list_means_no_check(tmp_path, monkeypatch):
    assert payroll.load_million_employees() is None                  # no file
    f = tmp_path / "employees.txt"
    f.write_text("# nothing typed yet\n", encoding="utf-8")
    monkeypatch.setenv("TABLE_READER_MILLION_EMPLOYEES", str(f))
    assert payroll.load_million_employees() is None                  # a file with no codes
    payroll.build_xls(*million(), mapping=MAPPING, known=None)
    monkeypatch.delenv("TABLE_READER_MILLION_EMPLOYEES")
    assert payroll.million_employees_path().parts[-3:] == ("learn-million", "million-import-tools", "employees.txt")


def test_millions_employee_list_is_read_from_its_printed_report_layout():
    people = [("MJ(1)", "ALI BIN ABU"), ("MJ(2)", "AMINAH"), (100, "ZUL"), ("B01", "")]
    assert payroll.parse_million_employees(million_listing(people)) == [
        {"emp_no": "MJ(1)", "name": "ALI BIN ABU"}, {"emp_no": "MJ(2)", "name": "AMINAH"},
        {"emp_no": "100", "name": "ZUL"}, {"emp_no": "B01", "name": ""}]      # three pages, headings not taken as people
    # Million's "Payroll Information" report: its title, company name and total line sit in the Emp no. column
    assert [e["emp_no"] for e in payroll.parse_million_employees(million_listing(people, title_col=1))] == [
        "MJ(1)", "MJ(2)", "100", "B01"]


def test_an_employee_list_that_cannot_be_trusted_is_refused():
    with pytest.raises(ocr.OcrError) as e:
        payroll.parse_million_employees(million_listing([("MJ(1)", "ALI"), ("MJ(2)", "AMINAH")], total=3))
    assert e.value.code == "MILLION_LIST" and "Total Employees : 3, but 2 could be read" in e.value.message
    for not_the_list in (b"not an excel file", payroll.build_xls(*million(n=1), mapping=MAPPING), million_listing([])):
        with pytest.raises(ocr.OcrError) as e:
            payroll.parse_million_employees(not_the_list)
        assert e.value.message.startswith("This is not Million Payroll's employee list.")


def test_a_name_that_is_someone_else_in_million_needs_an_explicit_yes():
    names = {"mj(1)": "Worker 1", "mj(2)": "SITI", "mj(3)": ""}        # as in Million; MJ(3) has no name there
    plan, results = million()
    msg = refused(plan, results, code="MILLION_NAME", names=names, known=set(names))
    assert msg.startswith("1 employee has another name in Million Payroll: MJ(2) WORKER 2 (in Million: SITI). ")
    assert read_xls(payroll.build_xls(plan, results, mapping=MAPPING, names=names, allow_names=True)).nrows == 4
    names["mj(2)"] = "WORKER 2 BIN ABU"                                # all the words of one name are in the other
    payroll.build_xls(plan, results, mapping=MAPPING, names=names)
    names.update({"mj(1)": "A", "mj(2)": "B"})
    assert refused(plan, results, code="MILLION_NAME", names=names).startswith("2 employees have another name")
    results[0]["emp_no"] = "MJ(9)"                                     # an unknown number is asked about first
    refused(plan, results, code="MILLION_UNKNOWN", names=names, known=set(names), allow_names=True)


def test_a_broken_mapping_file_is_reported(tmp_path):
    good_text = BUNDLED_MAPPING.read_text(encoding="utf-8")
    f = tmp_path / "office-mapping.csv"
    for broken, problem in [(good_text.replace(",Key,1,", ",Info,1,"), "exactly one Key"),
                            (good_text.replace(",Number,4,", ",Number,3,"), "column 3 is used for both"),
                            (good_text.replace(",Number,5,", ",Number,five,"), "not a whole number")]:
        f.write_text(broken, encoding="utf-8")
        with pytest.raises(ocr.OcrError) as e:
            payroll.load_office_mapping(f)
        assert e.value.code == "MILLION_MAPPING" and problem in e.value.message
    with pytest.raises(ocr.OcrError) as e:
        payroll.load_office_mapping(tmp_path / "missing.csv")
    assert "missing.csv was not found" in e.value.message


def test_the_mapping_file_in_documents_is_preferred(tmp_path, monkeypatch):
    f = tmp_path / "office-mapping.csv"
    f.write_text(BUNDLED_MAPPING.read_text(encoding="utf-8").replace("ZAKAT (RM)", "ZAKAT (office)"), encoding="utf-8")
    monkeypatch.setenv("TABLE_READER_MILLION_MAPPING", str(f))
    assert payroll.load_office_mapping()[-1]["header"] == "ZAKAT (office)"
    assert payroll.mapping_paths()[-1].parts[-2:] == ("million", "office-mapping.csv")


def test_new_office_lines_are_in_the_default_lists():
    lists = payroll.default_lists()
    names = {kind: [line["name"] for line in lists[kind]] for kind in lists}
    assert {"Transport Allowance", "use and claim"} <= set(names["allowance"])
    assert {"PENALTY", "RENTAL CAR", "rental hostel", "ZAKAT"} <= set(names["deduction"])
    assert {"name": "ZAKAT", "type": "Zakat"} in lists["deduction"]


def test_the_employees_company_is_set_or_comes_from_their_files():
    docs = {"j1": "MAJU JAYA", "j2": "MAJU JAYA", "j3": "OTHER CO"}
    assert payroll.employee_company({"company": "ACME", "jobs": ["j3"]}, docs) == "ACME"
    assert payroll.employee_company({"jobs": ["j1", "j2#p3"]}, docs) == "MAJU JAYA"
    assert payroll.employee_company({"jobs": ["j1", "j3"]}, docs) == ""              # files of two companies
    p = plan_for()
    payroll.auto_employees(p, [candidate("j1", "MAJU JAYA ALI SEPT 26.jpeg")], {}, lambda: "a")
    assert p["employees"][0]["company"] == "MAJU JAYA"
