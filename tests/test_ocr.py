"""Tests for ocr.py that need no Claude: schema validation, CLI output parsing, "never guess" handling."""
import copy
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

import ocr


# ------------------------------------------------------------------------------------------------------ helpers
def cell(value=None, raw="", conf=0, reason=None):
    return {"value": value, "raw_text": raw, "confidence": conf, "unclear_reason": reason}


def page(rows=None, labels=("Date", "In"), header=None, quality="CLEAR", notes=(), turn=0):
    return {"rotate_clockwise_degrees": turn, "quality": quality, "header_fields": header or [], "column_labels": list(labels),
            "rows": rows if rows is not None else [], "notes": list(notes)}


def row(**cells):
    return {"cells": [{"column": col, "cell": c} for col, c in cells.items()]}


GOOD = page(rows=[row(Date=cell("16", "16", 95), In=cell("07:26", "07:26", 90))],
            header=[{"label": "Name", "cell": cell("A", "A", 90)}])


def envelope(**kw):
    base = {"type": "result", "is_error": False}
    base.update(kw)
    return json.dumps(base)


# ------------------------------------------------------------------------------------------- schema validation
def test_valid_page_has_no_errors():
    assert ocr.validate_page_json(GOOD) == []


def test_empty_page_is_valid():
    assert ocr.validate_page_json(page()) == []


def test_missing_required_key_is_reported():
    bad = copy.deepcopy(GOOD)
    del bad["notes"]
    assert any("missing required key 'notes'" in e for e in ocr.validate_page_json(bad))


def test_unexpected_key_is_reported():
    bad = copy.deepcopy(GOOD)
    bad["document_type"] = "PAYSLIP"
    assert any("unexpected key 'document_type'" in e for e in ocr.validate_page_json(bad))


def test_bad_quality_value_is_reported():
    bad = copy.deepcopy(GOOD)
    bad["quality"] = "PERFECT"
    assert any("not one of" in e for e in ocr.validate_page_json(bad))


def test_wrong_types_are_reported():
    bad = copy.deepcopy(GOOD)
    bad["rows"][0]["cells"][0]["cell"]["confidence"] = "high"
    bad["column_labels"] = "Date"
    errors = ocr.validate_page_json(bad)
    assert any("expected a number" in e for e in errors)
    assert any("expected array" in e for e in errors)


def test_boolean_is_not_a_number():
    bad = copy.deepcopy(GOOD)
    bad["rows"][0]["cells"][0]["cell"]["confidence"] = True
    assert ocr.validate_page_json(bad)


def test_cell_value_may_be_null_but_not_a_number():
    ok = copy.deepcopy(GOOD)
    ok["rows"][0]["cells"][0]["cell"]["value"] = None
    assert ocr.validate_page_json(ok) == []
    ok["rows"][0]["cells"][0]["cell"]["value"] = 16
    assert any("does not match any allowed type" in e for e in ocr.validate_page_json(ok))


@pytest.mark.parametrize("turn", [45, -90, 360, "90", 90.0, True])
def test_bad_rotation_values_are_rejected(turn):
    bad = copy.deepcopy(GOOD)
    bad["rotate_clockwise_degrees"] = turn
    assert ocr.validate_page_json(bad)


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_good_rotation_values_are_accepted(turn):
    ok = copy.deepcopy(GOOD)
    ok["rotate_clockwise_degrees"] = turn
    assert ocr.validate_page_json(ok) == []


def test_non_object_is_rejected():
    assert ocr.validate_page_json([1, 2]) and ocr.validate_page_json("x")


# ----------------------------------------------------------------------------------------- never guess: cells
def test_clear_confident_cell_is_kept():
    c = ocr.normalize_cell(cell("07:26", "07:26", 90))
    assert c == {"value": "07:26", "raw_text": "07:26", "confidence": 90.0, "unclear_reason": None,
                 "needs_review": False}


def test_cell_with_reason_loses_its_value_but_keeps_marks():
    c = ocr.normalize_cell(cell("8:15", "8:?5", 95, "Middle digit smudged"))
    assert c["value"] is None
    assert c["raw_text"] == "8:?5"
    assert c["unclear_reason"] == "Middle digit smudged"
    assert c["needs_review"] is True


def test_low_confidence_value_is_blanked_and_flagged():
    c = ocr.normalize_cell(cell("42", "42", 55))
    assert c["value"] is None
    assert c["raw_text"] == "42"            # what Claude saw is kept so the user can accept it with one look
    assert "55%" in c["unclear_reason"]
    assert c["needs_review"] is True


def test_confidence_exactly_at_threshold_is_trusted():
    assert ocr.normalize_cell(cell("42", "42", ocr.UNSURE_BELOW))["value"] == "42"
    assert ocr.normalize_cell(cell("42", "42", ocr.UNSURE_BELOW - 0.1))["value"] is None


def test_question_mark_in_raw_text_blanks_value():
    c = ocr.normalize_cell(cell("1250", "12?0", 99))
    assert c["value"] is None and c["needs_review"] and c["raw_text"] == "12?0"


def test_marks_without_value_or_reason_get_a_reason():
    c = ocr.normalize_cell(cell(None, "scribble", 0))
    assert c["value"] is None and c["unclear_reason"] and c["needs_review"]


def test_truly_empty_cell_is_not_flagged():
    c = ocr.normalize_cell(cell(None, "", 0))
    assert c == {"value": None, "raw_text": "", "confidence": 0.0, "unclear_reason": None, "needs_review": False}


@pytest.mark.parametrize("raw", ["........", ". . . . .", "______", "……", "-----"])
def test_printed_fill_in_lines_are_empty_not_unclear(raw):
    c = ocr.normalize_cell(cell(None, raw, 95))
    assert c == {"value": None, "raw_text": "", "confidence": 0.0, "unclear_reason": None, "needs_review": False}


@pytest.mark.parametrize("raw", ["-", "--", ".", "x...", "7..", "?"])
def test_short_dashes_and_real_marks_are_still_flagged(raw):
    c = ocr.normalize_cell(cell(None, raw, 95))
    assert c["needs_review"] and c["raw_text"] == raw


def test_fill_in_line_with_a_reason_is_kept_as_claude_reported_it():
    c = ocr.normalize_cell(cell(None, "....", 50, "Something written over the line"))
    assert c["needs_review"] and c["raw_text"] == "...."


def test_whitespace_value_counts_as_empty():
    c = ocr.normalize_cell(cell("   ", "", 80))
    assert c["value"] is None and not c["needs_review"]


def test_blank_reason_string_is_not_a_reason():
    c = ocr.normalize_cell(cell("5", "5", 90, "  "))
    assert c["value"] == "5" and not c["needs_review"]


def test_raw_text_is_filled_from_value_when_missing():
    assert ocr.normalize_cell(cell("5", "", 90))["raw_text"] == "5"


@pytest.mark.parametrize("conf", [None, "abc", -20, 250])
def test_odd_confidence_never_breaks_and_stays_in_range(conf):
    c = ocr.normalize_cell(cell("5", "5", conf))
    assert 0.0 <= c["confidence"] <= 100.0
    if conf in (None, "abc", -20):
        assert c["value"] is None and c["needs_review"]     # unknown confidence is not trusted


def test_normalising_never_invents_a_value():
    for v, raw, conf, reason in [(None, "", 0, None), (None, "x", 90, "faded"), ("1", "1", 50, None),
                                 ("1", "?", 99, None)]:
        out = ocr.normalize_cell(cell(v, raw, conf, reason))
        assert out["value"] is None or out["value"] == v


# ------------------------------------------------------------------------------------------ never guess: page
def test_normalize_page_shape_and_flags():
    out = ocr.normalize_page(page(
        rows=[row(Date=cell("16", "16", 95), In=cell("07:26", "07:26", 40, "faint"))],
        header=[{"label": "Name", "cell": cell("A", "A", 90)}]))
    assert out["column_labels"] == ["Date", "In"]
    cells = out["rows"][0]["cells"]
    assert list(cells) == ["Date", "In"]
    assert cells["Date"]["value"] == "16"
    assert cells["In"]["value"] is None and cells["In"]["needs_review"]
    assert out["header_fields"][0]["cell"]["value"] == "A"


def test_cell_claude_left_out_is_flagged_not_treated_as_empty():
    out = ocr.normalize_page(page(rows=[row(Date=cell("16", "16", 95))], labels=("Date", "In")))
    missing = out["rows"][0]["cells"]["In"]
    assert missing["value"] is None and missing["needs_review"]
    assert "did not report" in missing["unclear_reason"]


def test_column_used_in_row_but_not_listed_is_added_not_dropped():
    out = ocr.normalize_page(page(rows=[row(Date=cell("1", "1", 90), Extra=cell("x", "x", 90))],
                                  labels=("Date",)))
    assert out["column_labels"] == ["Date", "Extra"]
    assert out["rows"][0]["cells"]["Extra"]["value"] == "x"


def test_rows_are_rectangular_and_ordered_like_the_columns():
    out = ocr.normalize_page(page(rows=[row(In=cell("1", "1", 90), Date=cell("2", "2", 90)), row()],
                                  labels=("Date", "In")))
    for r in out["rows"]:
        assert list(r["cells"]) == ["Date", "In"]


def test_duplicate_column_labels_are_kept_apart():
    labels = ("Name", "IN", "OUT", "IN", "OUT")
    r = {"cells": [{"column": c, "cell": cell(str(i), str(i), 90)} for i, c in enumerate(labels)]}
    out = ocr.normalize_page(page(rows=[r], labels=labels))
    assert out["column_labels"] == ["Name", "IN", "OUT", "IN (2)", "OUT (2)"]
    values = [c["value"] for c in out["rows"][0]["cells"].values()]
    assert values == ["0", "1", "2", "3", "4"]          # nothing overwritten


def test_empty_column_label_gets_a_placeholder():
    out = ocr.normalize_page(page(rows=[], labels=("", "")))
    assert out["column_labels"] == ["COL", "COL (2)"]


def test_normalize_page_does_not_change_its_input():
    src = page(rows=[row(Date=cell("16", "16", 40, "faint"), In=cell("7", "7", 95))])
    before = copy.deepcopy(src)
    ocr.normalize_page(src)
    assert src == before


def test_notes_and_quality_pass_through():
    out = ocr.normalize_page(page(quality="FADED", notes=["2 empty rows skipped"]))
    assert out["quality"] == "FADED" and out["notes"] == ["2 empty rows skipped"]


# -------------------------------------------------------------------------------------------- CLI output parsing
def test_parse_structured_output():
    assert ocr.parse_cli_output(envelope(structured_output=GOOD)) == GOOD


def test_parse_falls_back_to_json_in_result_text():
    assert ocr.parse_cli_output(envelope(result=json.dumps(GOOD))) == GOOD


@pytest.mark.parametrize("stdout", ["", "not json", "Error: something\n"])
def test_parse_non_json_output(stdout):
    with pytest.raises(ocr.OcrError) as e:
        ocr.parse_cli_output(stdout, "boom")
    assert e.value.code == "CLAUDE_CLI_ERROR"


def test_parse_json_that_is_not_an_object():
    with pytest.raises(ocr.OcrError) as e:
        ocr.parse_cli_output("[1,2]")
    assert e.value.code == "CLAUDE_CLI_BAD_JSON"


def test_parse_missing_structured_output():
    with pytest.raises(ocr.OcrError) as e:
        ocr.parse_cli_output(envelope(result="Sorry, I could not read it."))
    assert e.value.code == "CLAUDE_CLI_BAD_JSON"


def test_parse_schema_mismatch_is_rejected_not_repaired():
    bad = copy.deepcopy(GOOD)
    del bad["rows"]
    with pytest.raises(ocr.OcrError) as e:
        ocr.parse_cli_output(envelope(structured_output=bad))
    assert e.value.code == "CLAUDE_CLI_BAD_JSON" and "rows" in e.value.message


@pytest.mark.parametrize("msg,code", [
    ("Not logged in · Please run /login", "CLAUDE_LOGIN_REQUIRED"),
    ("API Error: 401 authentication_error", "CLAUDE_LOGIN_REQUIRED"),
    ("5-hour usage limit reached", "CLAUDE_PLAN_LIMIT"),
    ("API Error: 429 rate limit", "CLAUDE_PLAN_LIMIT"),
    ("something odd happened", "CLAUDE_CLI_ERROR"),
])
def test_parse_cli_error_messages_are_classified(msg, code):
    with pytest.raises(ocr.OcrError) as e:
        ocr.parse_cli_output(envelope(is_error=True, result=msg))
    assert e.value.code == code


def test_every_error_message_says_what_to_do_next():
    for stdout in ["", "[]", envelope(result="x"), envelope(is_error=True, result="not logged in"),
                   envelope(is_error=True, result="usage limit"), envelope(is_error=True, result="odd")]:
        with pytest.raises(ocr.OcrError) as e:
            ocr.parse_cli_output(stdout)
        assert any(w in e.value.message.lower() for w in ("try", "press", "wait", "sign in")), e.value.message


# -------------------------------------------------------------------------------------------- environment / auth
def test_billing_variables_are_removed_from_the_cli_environment(monkeypatch):
    for k in ocr._BILLING_ENV:
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("KEEP_ME", "1")
    env = ocr._env()
    assert not any(k in env for k in ocr._BILLING_ENV)
    assert env["KEEP_ME"] == "1"


def _fake_run(stdout="", returncode=0, raises=None, calls=None):
    def run(cmd, **kwargs):
        if calls is not None:
            calls.append((cmd, kwargs))
        if raises:
            raise raises
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return run


def test_auth_status_when_cli_missing(monkeypatch):
    monkeypatch.setattr(ocr, "cli_path", lambda: None)
    s = ocr.auth_status()
    assert not s["installed"] and not s["logged_in"] and "not installed" in s["message"]


def test_auth_status_signed_in_with_plan(monkeypatch):
    monkeypatch.setattr(ocr, "cli_path", lambda: "claude")
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(
        {"loggedIn": True, "authMethod": "claude.ai", "email": "a@b.c", "subscriptionType": "pro"})))
    s = ocr.auth_status()
    assert s["installed"] and s["logged_in"] and s["email"] == "a@b.c" and s["plan"] == "pro" and not s["message"]


def test_auth_status_not_signed_in(monkeypatch):
    monkeypatch.setattr(ocr, "cli_path", lambda: "claude")
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps({"loggedIn": False})))
    s = ocr.auth_status()
    assert s["installed"] and not s["logged_in"] and "Sign in" in s["message"]


def test_auth_status_api_account_is_not_accepted(monkeypatch):
    monkeypatch.setattr(ocr, "cli_path", lambda: "claude")
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps({"loggedIn": True, "authMethod": "api_key"})))
    s = ocr.auth_status()
    assert not s["logged_in"] and "billed per use" in s["message"]


@pytest.mark.parametrize("exc", [subprocess.TimeoutExpired("claude", 30), OSError("nope")])
def test_auth_status_never_raises(monkeypatch, exc):
    monkeypatch.setattr(ocr, "cli_path", lambda: "claude")
    monkeypatch.setattr(subprocess, "run", _fake_run(raises=exc))
    assert not ocr.auth_status()["logged_in"]


def test_auth_status_garbage_output_never_raises(monkeypatch):
    monkeypatch.setattr(ocr, "cli_path", lambda: "claude")
    monkeypatch.setattr(subprocess, "run", _fake_run("<html>"))
    assert not ocr.auth_status()["logged_in"]


# ------------------------------------------------------------------------------------------ image preparation
def test_prepare_image_shrinks_big_images_and_leaves_original_alone(tmp_path):
    src = tmp_path / "big.jpg"
    Image.new("RGB", (5000, 3000), "white").save(src)
    before = src.read_bytes()
    out_dir = tmp_path / "work"
    out_dir.mkdir()
    out = ocr.prepare_image(src, out_dir)
    with Image.open(out) as im:
        assert max(im.size) == ocr.MAX_SIDE and im.format == "PNG"
    assert src.read_bytes() == before


def test_prepare_image_keeps_small_images_small(tmp_path):
    src = tmp_path / "s.png"
    Image.new("RGB", (300, 200), "white").save(src)
    out = ocr.prepare_image(src, tmp_path)
    with Image.open(out) as im:
        assert im.size == (300, 200)


def test_prepare_image_applies_exif_rotation(tmp_path):
    src = tmp_path / "r.jpg"
    im = Image.new("RGB", (400, 200), "white")
    exif = Image.Exif()
    exif[0x0112] = 6                     # rotate 90 degrees clockwise to display
    im.save(src, exif=exif)
    out = ocr.prepare_image(src, tmp_path)
    with Image.open(out) as res:
        assert res.size == (200, 400)


def test_prepare_image_turns_clockwise(tmp_path):
    src = tmp_path / "t.png"
    im = Image.new("RGB", (40, 20), "white")
    im.putpixel((0, 0), (255, 0, 0))                     # red marker at the top-left corner
    im.save(src)
    for deg, size, marker in [(90, (20, 40), (19, 0)),    # clockwise: top-left goes to top-right
                              (180, (40, 20), (39, 19)),
                              (270, (20, 40), (0, 39))]:   # top-left goes to bottom-left
        with Image.open(ocr.prepare_image(src, tmp_path, deg)) as out:
            assert out.size == size
            assert out.getpixel(marker) == (255, 0, 0), deg


def test_prepare_image_rejects_a_damaged_file(tmp_path):
    src = tmp_path / "bad.jpg"
    src.write_bytes(b"this is not a picture")
    with pytest.raises(ocr.OcrError) as e:
        ocr.prepare_image(src, tmp_path)
    assert e.value.code == "IMAGE_UNREADABLE"


# ------------------------------------------------------------------------------------------------ read_image
@pytest.fixture
def signed_in(monkeypatch):
    monkeypatch.setattr(ocr, "cli_path", lambda: "claude")
    monkeypatch.setattr(ocr, "auth_status", lambda: {"installed": True, "logged_in": True, "message": None})


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "scan.png"
    Image.new("RGB", (200, 100), "white").save(p)
    return p


def test_read_image_end_to_end_with_fake_cli(monkeypatch, signed_in, png):
    calls = []
    monkeypatch.setattr(subprocess, "run", _fake_run(envelope(structured_output=GOOD), calls=calls))
    result = ocr.read_image(png)
    assert result["rows"][0]["cells"]["In"]["value"] == "07:26"
    cmd, kwargs = calls[0]
    assert cmd[cmd.index("--tools") + 1] == "Read"                         # Claude may only read files
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert "page.png" in kwargs["input"]
    assert not any(k in kwargs["env"] for k in ocr._BILLING_ENV)
    assert str(png.parent) not in kwargs["cwd"]                            # works in its own temp folder
    assert png.exists()                                                    # original untouched


def test_read_image_applies_never_guess_to_claude_output(monkeypatch, signed_in, png):
    unsure = page(rows=[row(Date=cell("16", "16", 95), In=cell("07:26", "07:26", 30))])
    monkeypatch.setattr(subprocess, "run", _fake_run(envelope(structured_output=unsure)))
    cells = ocr.read_image(png)["rows"][0]["cells"]
    assert cells["In"]["value"] is None and cells["In"]["raw_text"] == "07:26" and cells["In"]["needs_review"]


def _sequence_run(outputs, seen):
    """Fake CLI that returns the given outputs in turn and records the size of the page it was shown."""
    outputs = list(outputs)

    def run(cmd, **kwargs):
        with Image.open(Path(kwargs["cwd"]) / "page.png") as im:
            seen.append(im.size)
        return subprocess.CompletedProcess(cmd, 0, stdout=outputs.pop(0), stderr="")
    return run


def test_upright_page_is_read_once(monkeypatch, signed_in, png):
    seen = []
    monkeypatch.setattr(subprocess, "run", _sequence_run([envelope(structured_output=GOOD)], seen))
    result = ocr.read_image(png)
    assert seen == [(200, 100)] and result["rotated_clockwise"] == 0


def test_sideways_page_is_turned_and_read_again(monkeypatch, signed_in, png):
    seen = []
    sideways = page(turn=90, quality="ILLEGIBLE")
    monkeypatch.setattr(subprocess, "run", _sequence_run(
        [envelope(structured_output=sideways), envelope(structured_output=GOOD)], seen))
    result = ocr.read_image(png)
    assert seen == [(200, 100), (100, 200)]                       # second look is at the turned picture
    assert result["rotated_clockwise"] == 90
    assert result["rows"][0]["cells"]["In"]["value"] == "07:26"   # only the second reading is kept
    assert not any("not sure which way up" in n for n in result["notes"])


def test_wrong_first_direction_is_corrected_by_the_next_look(monkeypatch, signed_in, png):
    seen = []
    monkeypatch.setattr(subprocess, "run", _sequence_run(
        [envelope(structured_output=page(turn=90)),        # first guess: wrong way
         envelope(structured_output=page(turn=180)),       # now upside down: turn half a circle more
         envelope(structured_output=GOOD)], seen))
    result = ocr.read_image(png)
    assert len(seen) == 3 and result["rotated_clockwise"] == 270
    assert result["rows"][0]["cells"]["In"]["value"] == "07:26"
    assert not any("not sure which way up" in n for n in result["notes"])


def test_turning_stops_after_the_last_look_and_that_look_must_transcribe(monkeypatch, signed_in, png):
    seen, prompts = [], []
    outputs = [envelope(structured_output=page(turn=90)), envelope(structured_output=page(turn=90)),
               envelope(structured_output=page(turn=90, rows=[row(Date=cell("1", "1", 90), In=cell("2", "2", 90))]))]
    inner = _sequence_run(outputs, seen)

    def run(cmd, **kwargs):
        prompts.append(kwargs["input"])
        return inner(cmd, **kwargs)
    monkeypatch.setattr(subprocess, "run", run)
    result = ocr.read_image(png)
    assert len(seen) == ocr.MAX_LOOKS == 3                        # no endless turning
    assert [("last look" in p) for p in prompts] == [False, False, True]
    assert result["rows"][0]["cells"]["Date"]["value"] == "1"     # the last look's transcription is kept
    assert any("not sure which way up" in n for n in result["notes"])


def test_prompt_demands_every_row():
    assert "Never stop part-way" in ocr.SYSTEM_PROMPT


def test_prompt_treats_empty_signature_lines_as_blank_not_unclear():
    assert "unsigned signature space" in ocr.SYSTEM_PROMPT


def test_read_image_missing_file(tmp_path):
    with pytest.raises(ocr.OcrError) as e:
        ocr.read_image(tmp_path / "nope.png")
    assert e.value.code == "FILE_MISSING"


def test_read_image_wrong_type(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF")
    with pytest.raises(ocr.OcrError) as e:
        ocr.read_image(p)
    assert e.value.code == "FILE_TYPE"


def test_read_image_when_not_signed_in_does_not_start_claude(monkeypatch, png):
    monkeypatch.setattr(ocr, "auth_status", lambda: {"installed": True, "logged_in": False, "message": "Sign in."})
    monkeypatch.setattr(subprocess, "run", _fake_run(raises=AssertionError("must not run")))
    with pytest.raises(ocr.OcrError) as e:
        ocr.read_image(png)
    assert e.value.code == "CLAUDE_LOGIN_REQUIRED"


def test_read_image_when_cli_missing(monkeypatch, png):
    monkeypatch.setattr(ocr, "auth_status", lambda: {"installed": False, "logged_in": False, "message": "Install."})
    with pytest.raises(ocr.OcrError) as e:
        ocr.read_image(png)
    assert e.value.code == "CLAUDE_CLI_MISSING"


def test_read_image_timeout(monkeypatch, signed_in, png):
    monkeypatch.setattr(subprocess, "run", _fake_run(raises=subprocess.TimeoutExpired("claude", 300)))
    with pytest.raises(ocr.OcrError) as e:
        ocr.read_image(png, timeout=300)
    assert e.value.code == "CLAUDE_CLI_TIMEOUT" and "5 minutes" in e.value.message


def test_read_image_cli_cannot_start(monkeypatch, signed_in, png):
    monkeypatch.setattr(subprocess, "run", _fake_run(raises=OSError("denied")))
    with pytest.raises(ocr.OcrError) as e:
        ocr.read_image(png)
    assert e.value.code == "CLAUDE_CLI_ERROR"


def test_read_image_bad_claude_output_returns_nothing(monkeypatch, signed_in, png):
    monkeypatch.setattr(subprocess, "run", _fake_run(envelope(result="I cannot do that")))
    with pytest.raises(ocr.OcrError) as e:
        ocr.read_image(png)
    assert e.value.code == "CLAUDE_CLI_BAD_JSON"


# ------------------------------------------------------------------------------------------------------ main()
def test_main_prints_json_and_writes_file(monkeypatch, signed_in, png, tmp_path, capsys):
    monkeypatch.setattr(subprocess, "run", _fake_run(envelope(structured_output=GOOD)))
    assert ocr.main([str(png)]) == 0
    assert json.loads(capsys.readouterr().out)["rows"]
    out = tmp_path / "out.json"
    assert ocr.main([str(png), "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["column_labels"] == ["Date", "In"]


def test_main_reports_plain_error_and_nonzero_exit(tmp_path, capsys):
    assert ocr.main([str(tmp_path / "nope.png")]) == 1
    err = capsys.readouterr().err
    assert "FILE_MISSING" in err and "nope.png" in err


# ------------------------------------------------------------------------------------------- prompt / schema sanity
def test_prompt_is_generic_not_payroll_specific():
    low = ocr.SYSTEM_PROMPT.lower()
    for word in ("payroll", "malaysia", "attendance", "payslip"):
        assert word not in low
    for must in ("never infer", "null", "raw_text", "unclear_reason", "?"):
        assert must in low or must in ocr.SYSTEM_PROMPT


def test_schema_is_json_serialisable_and_closed():
    json.dumps(ocr.PAGE_SCHEMA)
    assert ocr.PAGE_SCHEMA["additionalProperties"] is False
    assert set(ocr.PAGE_SCHEMA["required"]) == set(ocr.PAGE_SCHEMA["properties"])


@pytest.fixture(autouse=True)
def _cli_through_subprocess_run(monkeypatch):
    """The tests below fake subprocess.run; route ocr._run_cli through it. _run_cli itself has real-process tests."""
    monkeypatch.setattr(ocr, "_run_cli", lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw))


def _python_cmd(code):
    return [sys.executable, "-I", "-c", code]


def test_run_cli_returns_output_like_subprocess_run(monkeypatch):
    monkeypatch.undo()                                   # use the real _run_cli
    out = ocr._run_cli(_python_cmd("import sys; print(sys.stdin.read().upper())"), input="abc", timeout=20, cwd=".",
                       env=ocr._env())
    assert out.returncode == 0 and out.stdout.strip() == "ABC"


def test_run_cli_stops_when_cancelled(monkeypatch):
    monkeypatch.undo()
    event = threading.Event()
    ocr.set_cancel_event(event)
    threading.Timer(1.0, event.set).start()
    started = time.monotonic()
    try:
        with pytest.raises(ocr.OcrError) as e:
            ocr._run_cli(_python_cmd("import time; time.sleep(60)"), input="", timeout=120, cwd=".", env=ocr._env())
    finally:
        ocr.set_cancel_event(None)
    assert e.value.code == "CANCELLED" and time.monotonic() - started < 15


def test_run_cli_cancelled_before_start_never_launches(monkeypatch):
    monkeypatch.undo()
    event = threading.Event()
    event.set()
    ocr.set_cancel_event(event)
    try:
        with pytest.raises(ocr.OcrError) as e:
            ocr._run_cli(["definitely-not-a-program"], input="", timeout=5, cwd=".", env=ocr._env())
    finally:
        ocr.set_cancel_event(None)
    assert e.value.code == "CANCELLED"


def test_run_cli_timeout_kills_the_process(monkeypatch):
    monkeypatch.undo()
    with pytest.raises(subprocess.TimeoutExpired):
        ocr._run_cli(_python_cmd("import time; time.sleep(60)"), input="", timeout=1, cwd=".", env=ocr._env())


# ------------------------------------------------------------------------------------------------ compact answer format
def compact(rows, doubts=(), labels=("Date", "In"), turn=0, header=None, notes=()):
    return {"rotate_clockwise_degrees": turn, "quality": "CLEAR", "header_fields": header or [],
            "column_labels": list(labels), "rows": rows, "doubts": list(doubts), "notes": list(notes)}


def doubt(row, column, raw="", reason="faded"):
    return {"row": row, "column": column, "raw_text": raw, "reason": reason}


def test_compact_answer_is_accepted_and_expanded():
    data = compact([["16", "07:26"], ["17", ""]], [doubt(1, 1, "0?:3?", "Digits faded")])
    assert ocr.validate_page_json(data, ocr.COMPACT_SCHEMA) == []
    rows = ocr.normalize_page(data)["rows"]
    assert rows[0]["cells"]["In"]["value"] == "07:26" and not rows[0]["cells"]["In"]["needs_review"]
    flagged = rows[1]["cells"]["In"]
    assert flagged["value"] is None and flagged["raw_text"] == "0?:3?" and flagged["needs_review"]
    assert flagged["unclear_reason"] == "Digits faded"
    assert rows[1]["cells"]["Date"]["value"] == "17"


def test_compact_blank_cell_is_empty_not_flagged():
    cells = ocr.normalize_page(compact([["16", ""]]))["rows"][0]["cells"]
    assert cells["In"]["value"] is None and not cells["In"]["needs_review"]


def test_compact_short_row_is_flagged_not_treated_as_empty():
    cells = ocr.normalize_page(compact([["16"]]))["rows"][0]["cells"]
    assert cells["In"]["needs_review"] and "did not report" in cells["In"]["unclear_reason"]


def test_compact_extra_cells_get_a_column_not_lost():
    page_ = ocr.normalize_page(compact([["16", "07:26", "extra"]]))
    assert page_["column_labels"] == ["Date", "In", "COL3"] and page_["rows"][0]["cells"]["COL3"]["value"] == "extra"


def test_compact_doubt_with_no_cell_goes_to_notes_instead_of_vanishing():
    page_ = ocr.normalize_page(compact([["16", "07:26"]], [doubt(5, 0, "x", "smudge")]))
    assert any("could not place" in n and "smudge" in n for n in page_["notes"])
    assert page_["rows"][0]["cells"]["Date"]["value"] == "16"


def test_compact_value_with_question_mark_is_still_flagged():
    cell_ = ocr.normalize_page(compact([["16", "07:2?"]]))["rows"][0]["cells"]["In"]
    assert cell_["value"] is None and cell_["needs_review"]


def test_compact_doubt_without_reason_still_gets_one():
    cell_ = ocr.normalize_page(compact([["16", ""]], [doubt(0, 1, "7", "")]))["rows"][0]["cells"]["In"]
    assert cell_["needs_review"] and cell_["unclear_reason"]


def test_compact_is_the_default_and_the_command_uses_it():
    cmd = ocr.build_command("claude", Path("."))
    assert ocr.OUTPUT_FORMAT == "compact" and '"doubts"' in cmd[cmd.index("--json-schema") + 1]
    assert cmd[cmd.index("--system-prompt") + 1] == ocr.COMPACT_PROMPT


def test_read_image_with_compact_answer_records_timing(monkeypatch, signed_in, png):
    env = envelope(structured_output=compact([["16", "07:26"]], [doubt(0, 0, "1?", "faded")]))
    monkeypatch.setattr(subprocess, "run", _fake_run(env))
    result = ocr.read_image(png)
    assert result["rows"][0]["cells"]["Date"]["needs_review"] and result["rows"][0]["cells"]["In"]["value"] == "07:26"
    t = result["timing"]
    assert t["looks"] == 1 and len(t["claude_seconds"]) == 1 and t["model"] == ocr.MODEL and t["format"] == "compact"
