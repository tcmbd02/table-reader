"""Tests for payroll.py: the calculation from confirmed cells, the issues it must raise, and the payroll file."""
import csv
import io

import pytest

import jobs
import ocr
import payroll
from helpers import cell, good, record


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
