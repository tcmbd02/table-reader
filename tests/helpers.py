"""Small builders shared by the tests."""
import ocr


def make_pdf(path, count=2):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    for _ in range(count):
        pdf.new_page(595, 842)                     # A4 in points
    pdf.save(str(path))
    pdf.close()


def cell(value=None, raw="", conf=0, reason=None):
    return {"value": value, "raw_text": raw, "confidence": conf, "unclear_reason": reason}


def good(value):
    return cell(value, value, 95)


def record(rows, header=(), labels=("Date", "In"), turn=0, notes=()):
    """A page record as ocr.read_image returns it. ``rows`` is a list of {column: cell}; ``header`` of (label, cell)."""
    raw = {"rotate_clockwise_degrees": 0, "quality": "CLEAR",
           "header_fields": [{"label": lab, "cell": c} for lab, c in header],
           "column_labels": list(labels),
           "rows": [{"cells": [{"column": col, "cell": c} for col, c in r.items()]} for r in rows],
           "notes": list(notes)}
    out = ocr.normalize_page(raw)
    out["rotated_clockwise"] = turn
    return out
