"""Make static/icons.svg from Tabler Icons (outline, MIT licence): one <symbol id="ti-<name>"> per downloaded icon.

python tools/make_icon_sprite.py <folder with <name>.svg files> <out icons.svg>

To add an icon: download https://unpkg.com/@tabler/icons@3.19.0/icons/outline/<name>.svg into the folder with the
others and run this again. The page uses an icon with icon("<name>") / iconButton("<name>", …) (static/app.js)."""
import re
import sys
from pathlib import Path


def symbol(name: str, svg: str) -> str:
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    inner = re.sub(r'<path stroke="none" d="M0 0h24v24H0z" fill="none"\s*/>', "", inner)     # Tabler's empty frame
    inner = " ".join(line.strip() for line in inner.splitlines() if line.strip())
    return f'<symbol id="ti-{name}" viewBox="0 0 24 24">{inner}</symbol>'


def main(folder: Path, out: Path) -> None:
    symbols = [symbol(f.stem, f.read_text(encoding="utf-8")) for f in sorted(folder.glob("*.svg"))]
    out.write_text('<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n'
                   "<!-- Tabler Icons 3.19.0 (outline), MIT licence: see icons-LICENSE.txt -->\n"
                   + "\n".join(symbols) + "\n</svg>\n", encoding="utf-8")
    print(f"{len(symbols)} icons -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
