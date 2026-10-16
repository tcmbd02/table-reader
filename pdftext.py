"""Read pages of a computer-made PDF from the PDF's own text, without Claude, once Claude has read one page of it.

A PDF made by a program (a clock-system report, not a scan) carries its text and where each word sits. That is not a
table yet: which words form which column, and what the columns and the fields above the table are called, is exactly
what Claude works out. So the first such page of a document is read by Claude as usual. Its reading is then matched,
word for word, against the words printed on that page; that gives a layout (where each column is, which lines are
table rows, where each field's value sits). Later pages with the same layout are filled in from their own text.

Never guess: a layout is only kept when Claude's whole reading of the page is found in the page's text, and when
applying the layout to that same page gives Claude's reading back exactly. On a later page every word must have its
place in the layout; one word that does not, and the page goes to Claude instead. Pictures of pages (scans, photos,
also scans that carry a hidden text layer) are never read this way.
"""
from __future__ import annotations

import re
from pathlib import Path

NOTE = "Read from the PDF's own text (no Claude): this page has the same layout as a page Claude read."
MIN_CHARS = 50          # fewer characters than this: not a text page
SLACK = 3.0             # points a printed word of the layout may sit left or right of where it was
EDGE = 1.0              # points a character may sit outside its column's known extent


def _squash(text: str) -> str:
    return "".join((text or "").split())


def _mask(text: str) -> str:
    """Digits -> 9, letters -> A."""
    return re.sub(r"[^\W\d_]", "A", re.sub(r"\d", "9", text))


def _shape(text: str) -> str:
    """The shape of a value, whatever its length: "17.00" -> "9.9", "OFF-DAY" -> "A-A", "12-09-2026" -> "9-9-9". A
    column only takes shapes that were seen in it on a page Claude read."""
    return re.sub(r"A+", "A", re.sub(r"9+", "9", _mask(_squash(text))))


# ------------------------------------------------------------------------------------------------ words of a page
def is_text_page(page) -> bool:
    """A page made of real text: it has text, is not turned, and no picture covers most of it (a scan with a hidden
    text layer is a picture: its text was made by a scanner's OCR and cannot be trusted)."""
    import pypdfium2.raw as raw

    if page.get_rotation() != 0 or page.get_textpage().count_chars() < MIN_CHARS:
        return False
    width, height = page.get_size()
    for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = obj.get_bounds()
        if (right - left) * (top - bottom) > 0.5 * width * height:
            return False
    return True


def page_lines(page) -> list[list[dict]]:
    """The page's words as lines, top to bottom, each line left to right:
    [{"x0", "x1", "y", "text", "chars": [(x0, x1, character)]}]."""
    import pypdfium2.raw as raw

    textpage = page.get_textpage()
    words, current = [], None
    for i in range(textpage.count_chars()):
        code = raw.FPDFText_GetUnicode(textpage.raw, i)
        if 0xF020 <= code <= 0xF0FF:
            code -= 0xF000                                          # a "symbol" font: its letters sit at U+F000 + the letter
        ch = chr(code)
        # the loose box has the height of the font, the same for every character of a line ("-" is as tall as "8")
        left, bottom, right, top = textpage.get_charbox(i, loose=True)
        if ch.isspace() or ch in "\x00￾￿" or right <= left:
            current = None
            continue
        mid, size = (top + bottom) / 2, max(top - bottom, 1.0)
        if current and abs(mid - current["y"]) <= 0.5 * current["h"] and -0.5 * size <= left - current["x1"] <= 0.35 * size:
            current["text"] += ch
            current["x1"] = max(current["x1"], right)
            current["h"] = max(current["h"], size)
            current["chars"].append((left, right, ch))
        else:
            current = {"x0": left, "x1": right, "y": mid, "h": size, "text": ch, "chars": [(left, right, ch)]}
            words.append(current)
    words.sort(key=lambda w: (-w["y"], w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        if lines and abs(lines[-1][0]["y"] - w["y"]) <= 0.45 * min(lines[-1][0]["h"], w["h"]):
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


# ------------------------------------------------------------------------------------------- learning the layout
def _take(words: list[dict], start: int, value: str) -> int | None:
    """How many words from ``start`` spell ``value`` (spaces ignored), or None."""
    target, got = _squash(value), ""
    for n, w in enumerate(words[start:], start=1):
        got += w["text"]
        if got == target:
            return n
        if not target.startswith(got):
            return None
    return None


def _confirmed(cell: dict) -> str | None:
    """A cell's value when Claude was sure of it, "" when it is empty; None when it is in doubt."""
    if cell.get("needs_review"):
        return None
    return (cell.get("value") or "").strip()


def learn(record: dict, lines: list[list[dict]], why: list[str] | None = None) -> dict | None:
    """The layout of a page, from Claude's reading of it (``record``) and the page's own words (``lines``); None when
    the reading cannot be found in the words completely (``why`` then gets the reason). See the module text."""
    def no(reason: str) -> None:
        if why is not None:
            why.append(reason)

    labels = record["column_labels"]
    if not record["rows"] or record.get("rotated_clockwise"):
        return no("no rows, or the page was turned")
    bands: dict[str, list[float]] = {}
    shapes: dict[str, set[str]] = {}
    row_lines, at = [], 0
    filled_everywhere = set(labels)
    for row in record["rows"]:
        values = [(c, _confirmed(row["cells"][c])) for c in labels]
        if any(v is None for _, v in values):
            return no("Claude doubted a cell")                      # no layout from this page
        values = [(c, v) for c, v in values if v]
        if not values:
            return no("an empty row")
        target = "".join(_squash(v) for _, v in values)
        k = next((i for i in range(at, len(lines)) if "".join(w["text"] for w in lines[i]) == target), None)
        if k is None:
            return no(f"row {len(row_lines) + 1} is not printed as Claude read it")
        chars = [ch for w in lines[k] for ch in w["chars"]]
        row_lines.append(k)
        at = k + 1
        filled_everywhere &= {c for c, _ in values}
        pos = 0
        for c, v in values:                                         # the characters of each value, in column order
            n = len(_squash(v))
            x0, x1 = chars[pos][0], chars[pos + n - 1][1]
            pos += n
            band = bands.setdefault(c, [x0, x1])
            band[0], band[1] = min(band[0], x0), max(band[1], x1)
            shapes.setdefault(c, set()).add(_shape(v))
    ordered = [bands[c] for c in labels if c in bands]
    if any(a[1] >= b[0] for a, b in zip(ordered, ordered[1:])) or not filled_everywhere:
        return no("columns overlap, or no column is filled in every row")
    if row_lines != list(range(row_lines[0], row_lines[-1] + 1)):
        return no("a line between the rows is not a row")

    # the lines above and below the table: fixed words, and the places of the fields Claude reported
    furniture = [[{"x0": w["x0"], "x1": w["x1"], "text": w["text"], "field": None} for w in line]
                 for k, line in enumerate(lines) if k < row_lines[0] or k > row_lines[-1]]
    cursor = (0, 0)
    for f, field in enumerate(record["header_fields"]):
        value = _confirmed(field["cell"])
        if value is None:
            return no("Claude doubted a field above the table")
        if not value:
            continue
        place = _find_field(furniture, value, cursor) or _find_field(furniture, value, (0, 0))
        if place is None:
            return no(f"field {f + 1} is not printed as Claude wrote it")
        k, start, n = place
        for token in furniture[k][start:start + n]:
            token["field"] = f
        cursor = (k, start + n)
    layout = {"labels": labels, "bands": bands, "anchors": sorted(filled_everywhere, key=labels.index),
              "shapes": {c: sorted(shapes[c]) for c in shapes}, "above": row_lines[0],
              "furniture": furniture, "fields": [f["label"] for f in record["header_fields"]]}
    again = apply(layout, lines, why)
    if again is None or not _same(again, record):
        return no("the layout does not give Claude's reading back")
    return layout


def _find_field(furniture: list[list[dict]], value: str, start: tuple[int, int]) -> tuple[int, int, int] | None:
    for k in range(start[0], len(furniture)):
        for i in range(start[1] if k == start[0] else 0, len(furniture[k])):
            n = _take(furniture[k], i, value)
            if n is not None and all(t["field"] is None for t in furniture[k][i:i + n]):
                return k, i, n
    return None


def _same(a: dict, b: dict) -> bool:
    def cells(record):
        return ([[_squash(row["cells"][c].get("value") or "") for c in record["column_labels"]] for row in record["rows"]],
                [(f["label"], _squash(f["cell"].get("value") or "")) for f in record["header_fields"]])
    return a["column_labels"] == b["column_labels"] and cells(a) == cells(b)


# ------------------------------------------------------------------------------------------- applying the layout
def _cell(text: str) -> dict:
    return {"value": text or None, "raw_text": text, "confidence": 100.0 if text else 0.0, "unclear_reason": None,
            "needs_review": False}


def _row(layout: dict, line: list[dict]) -> dict | None:
    """The line as a table row ({column: text}), or None when it is not one: every character must sit in one known
    column, every column that is always filled must be filled, and each value must have a shape seen in its column."""
    row: dict[str, list[list[str]]] = {}
    for n, w in enumerate(line):
        for x0, x1, ch in w["chars"]:
            centre = (x0 + x1) / 2
            inside = [c for c, (b0, b1) in layout["bands"].items() if b0 <= centre <= b1] or \
                     [c for c, (b0, b1) in layout["bands"].items() if b0 - EDGE <= centre <= b1 + EDGE]
            if len(inside) != 1:
                return None                                         # outside every column, or between two
            parts = row.setdefault(inside[0], [])
            if not parts or parts[-1][0] != n:
                parts.append([n, ""])                               # a new word in this column
            parts[-1][1] += ch
    out = {c: " ".join(text for _, text in parts) for c, parts in row.items()}
    if any(c not in out for c in layout["anchors"]) or any(_shape(v) not in layout["shapes"][c] for c, v in out.items()):
        return None                                                 # e.g. a totals line: numbers, but no date
    return out


def _fields(template: list[dict], line: list[dict]) -> dict[int, str] | None:
    """The values of the fields on one line above or below the table, or None when the line does not fit."""
    fixed = [t for t in template if t["field"] is None]
    slots = [t for t in template if t["field"] is not None]
    used, values = set(), {}
    for w in line:
        hit = next((i for i, t in enumerate(fixed) if i not in used and t["text"] == w["text"]
                    and abs(t["x0"] - w["x0"]) <= 2 * SLACK), None)
        if hit is not None:
            used.add(hit)
            continue
        centre = (w["x0"] + w["x1"]) / 2
        left = max((t["x1"] for t in fixed if t["x1"] <= w["x0"] + SLACK), default=float("-inf"))
        right = min((t["x0"] for t in fixed if t["x0"] >= w["x1"] - SLACK), default=float("inf"))
        near = [t for t in slots if left - SLACK <= t["x0"] and t["x1"] <= right + SLACK]   # fields between those words
        if not near:
            return None
        field = min(near, key=lambda t: abs((t["x0"] + t["x1"]) / 2 - centre))["field"]
        values.setdefault(field, []).append(w["text"])
    if len(used) != len(fixed):
        return None                                                 # a printed word of the layout is missing here
    return {f: " ".join(parts) for f, parts in values.items()}


def apply(layout: dict, lines: list[list[dict]], why: list[str] | None = None) -> dict | None:
    """The page record for a page with this layout, from its own words; None when anything does not fit."""
    def no(reason: str) -> None:
        if why is not None:
            why.append(reason)

    rows = [_row(layout, line) for line in lines]
    is_row = [r is not None for r in rows]
    if True not in is_row:
        return no("no table rows found")
    first, last = is_row.index(True), len(is_row) - 1 - is_row[::-1].index(True)
    if not all(is_row[first:last + 1]):
        return no("a line between the rows is not a row")
    around = lines[:first] + lines[last + 1:]
    if first != layout["above"] or len(around) != len(layout["furniture"]):
        return no("another number of lines above or below the table")
    values: dict[int, str] = {}
    for n, (template, line) in enumerate(zip(layout["furniture"], around), start=1):
        found = _fields(template, line)
        if found is None or any(f in values for f in found):
            return no(f"line {n} outside the table does not fit")
        values.update(found)
    return {
        "quality": "CLEAR", "column_labels": list(layout["labels"]),
        "header_fields": [{"label": label, "cell": _cell(values.get(f, ""))} for f, label in enumerate(layout["fields"])],
        "rows": [{"cells": {c: _cell(r.get(c, "")) for c in layout["labels"]}} for r in rows[first:last + 1]],
        "notes": [NOTE], "rotated_clockwise": 0, "source": "pdf-text",
    }


# ------------------------------------------------------------------------------------------------- one document
class Document:
    """The text pages of one PDF. ``learn(number, record)`` after Claude has read a page; ``read(number)`` gives the
    record of another page from its own text, or None when Claude has to read it."""

    def __init__(self, path: Path):
        self._pdf, self._layouts, self._lines = None, [], {}
        if Path(path).suffix.lower() != ".pdf":
            return
        try:
            import pypdfium2 as pdfium

            self._pdf = pdfium.PdfDocument(str(path))
        except Exception:  # noqa: BLE001 - the page pictures were made already; reading goes on with Claude
            self._pdf = None

    def _page(self, number: int) -> list[list[dict]] | None:
        if self._pdf is None or not 1 <= number <= len(self._pdf):
            return None
        if number not in self._lines:
            try:
                page = self._pdf[number - 1]
                self._lines[number] = page_lines(page) if is_text_page(page) else None
            except Exception:  # noqa: BLE001
                self._lines[number] = None
        return self._lines[number]

    def learn(self, number: int, record: dict) -> bool:
        lines = self._page(number)
        if lines is None or record.get("source") == "pdf-text":
            return False
        try:
            layout = learn(record, lines)
        except Exception:  # noqa: BLE001
            layout = None
        if layout is not None:
            self._layouts.append(layout)
        return layout is not None

    def read(self, number: int) -> dict | None:
        lines = self._page(number)
        if lines is None:
            return None
        for layout in self._layouts:
            try:
                record = apply(layout, lines)
            except Exception:  # noqa: BLE001
                record = None
            if record is not None:
                return record
        return None

    def close(self) -> None:
        if self._pdf is not None:
            self._pdf.close()
            self._pdf = None
