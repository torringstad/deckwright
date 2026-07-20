"""Generated test images with KNOWN pixel values, so tests can assert real
rendering (e.g. `dim=0.5` on a pure-red image must sample to ~(128,0,0)).

Everything is written into the staging dir the HTTP server serves from, so
the app under test loads them exactly like co-located user images.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# name -> (size, solid RGB)  — solid colors make pixel sampling trivial
SOLID = {
    "red.png": ((800, 450), (255, 0, 0)),
    "green.png": ((800, 450), (0, 200, 0)),
    "blue-wide.png": ((1600, 400), (0, 80, 255)),  # wider than 16:9 → cover crops
    "square.png": ((400, 400), (200, 120, 40)),
}


def write_assets(staging: Path) -> None:
    for name, (size, rgb) in SOLID.items():
        Image.new("RGB", size, rgb).save(staging / name)

    # a non-solid image, for eyeballing gallery output
    img = Image.new("RGB", (800, 450), (20, 30, 60))
    d = ImageDraw.Draw(img)
    for i in range(0, 800, 80):
        d.rectangle([i, 0, i + 40, 450], fill=(40 + i // 8, 60, 120))
    d.ellipse([300, 125, 500, 325], fill=(230, 200, 90))
    img.save(staging / "pattern.png")
