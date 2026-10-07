"""Make the Table Reader icon (packaging/table-reader.ico): a blue tile with a white table grid."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=44, fill=(34, 87, 214, 255))
left, top, right, bottom = 52, 64, SIZE - 52, SIZE - 56
d.rounded_rectangle((left, top, right, bottom), radius=10, fill=(255, 255, 255, 255))
d.rectangle((left, top, right, top + 34), fill=(190, 208, 250, 255))           # header row
for i in (1, 2):                                                                  # column lines
    x = left + (right - left) * i // 3
    d.line((x, top, x, bottom), fill=(34, 87, 214, 255), width=5)
for y in (top + 34, top + 34 + (bottom - top - 34) // 2):                         # row lines
    d.line((left, y, right, y), fill=(34, 87, 214, 255), width=5)
d.rectangle((left + 2, top + 38 + (bottom - top - 34) // 2 + 4, left + (right - left) // 3 - 4, bottom - 4),
            fill=(255, 227, 102, 255))                                            # one highlighted "check me" cell
img.save(Path(__file__).with_name("table-reader.ico"), sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
