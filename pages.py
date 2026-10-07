"""Turn an uploaded PDF or picture into page images (PNG). Derived copies only; the original is never touched."""
from __future__ import annotations

from pathlib import Path

from ocr import IMAGE_EXT, MAX_SIDE, OcrError

PDF_EXT = {".pdf"}
SUPPORTED_EXT = PDF_EXT | IMAGE_EXT
PDF_DPI = 200
MAX_PAGES = 100            # a safety stop, not a promise: Claude reads about one page every 40 seconds


def is_supported(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED_EXT


def page_file(out_dir: Path, number: int) -> Path:
    return out_dir / f"page-{number}.png"


def render_pages(path: Path, out_dir: Path) -> list[Path]:
    """Write ``page-1.png``, ``page-2.png``… into ``out_dir`` and return them in order. A page image that already
    exists is reused, so a read that was interrupted can carry on. Raises OcrError with a plain message."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise OcrError("FILE_TYPE", f"{path.name} is not a PDF or a picture (JPG, PNG). Save or scan it as a PDF, "
                       "JPG or PNG and add it again.")
    out_dir.mkdir(parents=True, exist_ok=True)
    return _render_pdf(path, out_dir) if ext in PDF_EXT else _render_image(path, out_dir)


def _render_pdf(path: Path, out_dir: Path) -> list[Path]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(str(path))
    except Exception as exc:  # noqa: BLE001 - damaged, encrypted or not a PDF at all
        raise OcrError("PDF_UNREADABLE", f"{path.name} could not be opened. It may be damaged or password-protected. "
                       "Open it on your computer to check, then add it again.") from exc
    try:
        count = len(pdf)
        if count == 0:
            raise OcrError("PDF_EMPTY", f"{path.name} has no pages.")
        if count > MAX_PAGES:
            raise OcrError("TOO_MANY_PAGES", f"{path.name} has {count} pages; Table Reader takes up to {MAX_PAGES} "
                           "at a time. Split the file and add the parts separately.")
        outputs = []
        for i in range(count):
            target = page_file(out_dir, i + 1)
            if not target.exists():
                try:
                    img = pdf[i].render(scale=PDF_DPI / 72).to_pil().convert("RGB")
                except Exception as exc:  # noqa: BLE001
                    raise OcrError("PDF_UNREADABLE", f"Page {i + 1} of {path.name} could not be drawn. Open the file "
                                   "on your computer to check it, then add it again.") from exc
                img.thumbnail((MAX_SIDE, MAX_SIDE))
                img.save(target)
            outputs.append(target)
        return outputs
    finally:
        pdf.close()


def _render_image(path: Path, out_dir: Path) -> list[Path]:
    from PIL import Image, ImageOps

    try:
        with Image.open(path) as im:
            frames = getattr(im, "n_frames", 1)
            if frames > MAX_PAGES:
                raise OcrError("TOO_MANY_PAGES", f"{path.name} has {frames} pages; Table Reader takes up to "
                               f"{MAX_PAGES} at a time. Split the file and add the parts separately.")
            outputs = []
            for i in range(frames):
                target = page_file(out_dir, i + 1)
                if not target.exists():
                    im.seek(i)
                    frame = ImageOps.exif_transpose(im.convert("RGB"))
                    frame.thumbnail((MAX_SIDE, MAX_SIDE))
                    frame.save(target)
                outputs.append(target)
            return outputs
    except OcrError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise OcrError("IMAGE_UNREADABLE", f"{path.name} could not be opened as a picture. Check that the file is "
                       "not damaged, or take the photo again.") from exc


def turn_page(page: Path, clockwise_degrees: int) -> None:
    """Turn a stored page image in place (a derived copy) so the viewer shows it upright."""
    from PIL import Image

    if clockwise_degrees % 360 == 0:
        return
    with Image.open(page) as im:
        turned = im.rotate(-(clockwise_degrees % 360), expand=True)
    tmp = page.with_name(page.name + ".tmp")
    turned.save(tmp, format="PNG")
    tmp.replace(page)
