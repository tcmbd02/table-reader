import json

import pytest

import layouts
import ocr
import payroll
from helpers import cell, good, record

LABELS = ("DATE", "WHrs", "OT", "LIn(Min)", "E/Out(Min)")


def page(rows, labels=LABELS):
    rec = record([{c: v for c, v in zip(labels, r)} for r in rows], labels=labels)
    rec["page"] = 1
    return rec


def test_shapes_hide_names_and_numbers():
    p = page([(good("ALI BIN ABU"), good("07:58"), good("PH"))], labels=("NAME", "IN", "MARK"))
    assert layouts.shapes(p) == [{"NAME": "AAA AAA AAA", "IN": "99:99", "MARK": "PH"}]


def test_a_yellow_cell_is_shaped_from_what_claude_saw():
    p = page([(cell(None, raw="8:3?", reason="faded"), good("2"), good(""), good(""), good(""))])
    assert layouts.shapes(p)[0]["DATE"] == "9:9?"


def test_the_prompt_holds_headings_and_shapes_but_never_the_values():
    seen = []

    def ask(prompt, schema, **kw):
        seen.append(prompt)
        return {"columns": [{"label": c, "role": r, "unit": u} for c, r, u in (
            ("DATE", "date", "none"), ("WHrs", "hours", "hours"), ("OT", "ot_1_5", "hours"),
            ("LIn(Min)", "lateness", "minutes"), ("E/Out(Min)", "early_departure", "minutes"))]}

    p = page([(good("01/09/2026"), good("8.5"), good("2"), good("15"), good("0")),
              (good("02/09/2026"), good("SITI"), good(""), good(""), good(""))])
    got = layouts.suggest(p, ask=ask)
    assert got["WHrs"] == {"role": "hours", "unit": "hours"} and got["LIn(Min)"]["unit"] == "minutes"
    assert all(label in seen[0] for label in LABELS) and "99/99/9999" in seen[0]
    assert "SITI" not in seen[0] and "01/09/2026" not in seen[0]


@pytest.mark.parametrize("answer", [
    {"columns": [{"label": "DATE", "role": "salary", "unit": "none"}]},
    {"columns": "nonsense"}, {}, {"columns": [{"label": "DATE", "role": "date", "unit": "none"}] * 2}])
def test_suggest_refuses_a_bad_answer(answer):
    with pytest.raises(ocr.OcrError) as e:
        layouts.suggest(page([(good("1"), good("8"), good("0"), good("0"), good("0"))]), ask=lambda *a, **k: answer)
    assert e.value.code == "BAD_LAYOUT"


def test_the_schema_offers_only_the_calculations_roles_and_units():
    item = layouts.SUGGEST_SCHEMA["properties"]["columns"]["items"]["properties"]
    assert item["role"]["enum"] == list(payroll.LAYOUT_ROLES) and item["unit"]["enum"] == list(payroll.LAYOUT_UNITS)
