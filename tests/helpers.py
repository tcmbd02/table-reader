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


def million_listing(employees, total=None, per_page=2, title_col=2):
    """Million Payroll's "Employment Listing" saved as Excel, as bytes: a printed-report layout (title, the heading rows
    again on every page, an employee every four rows, "Total Employees : n" at the end). ``employees`` = [(no, name)].
    ``title_col=1``: the "Payroll Information" report, whose title, company name and total are in the Emp no. column."""
    import io

    import xlwt

    book = xlwt.Workbook()
    sheet = book.add_sheet("Page 1")
    r = 0
    for start in range(0, max(len(employees), 1), per_page):
        sheet.write(r + 1, title_col, "Employment Listing")
        sheet.write(r + 5, title_col, "MAJU JAYA SDN BHD")
        sheet.write(r + 5, 26, f"Page {start // per_page + 1}")
        for col, label in ((1, "Emp no."), (4, "Name"), (8, "Gender"), (11, "D.O.B."), (24, "Basic Rate")):
            sheet.write(r + 7, col, label)
        sheet.write(r + 9, 4, "New I/C No.")
        sheet.write(r + 11, 4, "Old I/C No.")
        r += 15
        for no, name in employees[start:start + per_page]:
            sheet.write(r, 1, no)
            sheet.write(r, 4, name)
            sheet.write(r, 8, "M")
            sheet.write(r, 24, 1700.0)
            r += 4
        r += 5
    sheet.write(r, title_col, f"Total Employees : {len(employees) if total is None else total}")
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
