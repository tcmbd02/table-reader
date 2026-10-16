"""The icons the page uses (Tabler Icons, MIT) come from one sprite in static/, never from the internet."""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def test_every_icon_the_page_uses_is_in_the_sprite():
    sprite = (STATIC / "icons.svg").read_text(encoding="utf-8")
    have = set(re.findall(r'<symbol id="ti-([a-z0-9-]+)"', sprite))
    used = set()
    for f in [*STATIC.glob("*.js"), STATIC / "index.html"]:
        text = f.read_text(encoding="utf-8")
        used |= set(re.findall(r'icon(?:Button)?\("([a-z0-9-]+)"', text)) | set(re.findall(r"icons\.svg#ti-([a-z0-9-]+)", text))
    assert used and used <= have, sorted(used - have)


def test_the_sprite_carries_the_licence():
    assert "MIT" in (STATIC / "icons-LICENSE.txt").read_text(encoding="utf-8")
