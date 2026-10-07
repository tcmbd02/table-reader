"""Tests for pages.py: PDF / picture -> page images."""
import pytest
from PIL import Image

import ocr
import pages
from helpers import make_pdf


def test_supported_types():
    for name in ("a.pdf", "A.PDF", "b.jpg", "b.JPEG", "c.png", "d.tif"):
        assert pages.is_supported(name)
    for name in ("a.xlsx", "a.docx", "a", "a.csv"):
        assert not pages.is_supported(name)


def test_pdf_gives_one_png_per_page(tmp_path):
    src = tmp_path / "doc.pdf"
    make_pdf(src, 3)
    out = pages.render_pages(src, tmp_path / "pages")
    assert [p.name for p in out] == ["page-1.png", "page-2.png", "page-3.png"]
    with Image.open(out[0]) as im:
        assert im.format == "PNG" and max(im.size) <= ocr.MAX_SIDE and im.size[0] < im.size[1]


def test_original_is_left_alone(tmp_path):
    src = tmp_path / "doc.pdf"
    make_pdf(src)
    before = src.read_bytes()
    pages.render_pages(src, tmp_path / "pages")
    assert src.read_bytes() == before


def test_existing_page_images_are_reused_so_a_stopped_read_can_resume(tmp_path):
    src = tmp_path / "doc.pdf"
    make_pdf(src, 2)
    out_dir = tmp_path / "pages"
    first = pages.render_pages(src, out_dir)
    pages.turn_page(first[0], 90)                                  # a page turned upright earlier must stay turned
    turned = Image.open(first[0]).size
    assert turned[0] > turned[1]
    again = pages.render_pages(src, out_dir)
    assert again == first and Image.open(again[0]).size == turned


def test_big_photo_is_shrunk_and_exif_applied(tmp_path):
    src = tmp_path / "photo.jpg"
    im = Image.new("RGB", (4000, 2000), "white")
    exif = Image.Exif()
    exif[0x0112] = 6
    im.save(src, exif=exif)
    (out,) = pages.render_pages(src, tmp_path / "pages")
    with Image.open(out) as res:
        assert res.size == (1200, 2400)                            # turned upright, longest side capped


def test_multi_frame_tiff_gives_several_pages(tmp_path):
    src = tmp_path / "scan.tif"
    frames = [Image.new("RGB", (100, 50), c) for c in ("white", "black", "red")]
    frames[0].save(src, save_all=True, append_images=frames[1:])
    assert len(pages.render_pages(src, tmp_path / "pages")) == 3


def test_unsupported_type_is_refused_in_plain_words(tmp_path):
    src = tmp_path / "sheet.xlsx"
    src.write_bytes(b"x")
    with pytest.raises(ocr.OcrError) as e:
        pages.render_pages(src, tmp_path / "pages")
    assert e.value.code == "FILE_TYPE" and "PDF" in e.value.message


@pytest.mark.parametrize("name", ["bad.pdf", "bad.jpg"])
def test_damaged_files_give_a_clear_message(tmp_path, name):
    src = tmp_path / name
    src.write_bytes(b"this is not really a file of that kind")
    with pytest.raises(ocr.OcrError) as e:
        pages.render_pages(src, tmp_path / "pages")
    assert e.value.code == {"bad.pdf": "PDF_UNREADABLE", "bad.jpg": "IMAGE_UNREADABLE"}[name]
    assert "again" in e.value.message


def test_too_many_pages_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(pages, "MAX_PAGES", 2)
    src = tmp_path / "long.pdf"
    make_pdf(src, 3)
    with pytest.raises(ocr.OcrError) as e:
        pages.render_pages(src, tmp_path / "pages")
    assert e.value.code == "TOO_MANY_PAGES" and "Split" in e.value.message


@pytest.mark.parametrize("deg,size", [(0, (40, 20)), (360, (40, 20)), (90, (20, 40)), (180, (40, 20)), (270, (20, 40))])
def test_turn_page_in_place(tmp_path, deg, size):
    p = tmp_path / "page-1.png"
    Image.new("RGB", (40, 20), "white").save(p)
    pages.turn_page(p, deg)
    with Image.open(p) as im:
        assert im.size == size
    assert not list(tmp_path.glob("*.tmp"))
