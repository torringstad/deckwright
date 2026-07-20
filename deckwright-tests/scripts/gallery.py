#!/usr/bin/env python3
"""Render every slide of a deck to PNGs — a dev tool for eyeballing changes.

    python scripts/gallery.py my_deck.md [-o outdir] [--assets DIR]

Serves deckwright.html + the deck's directory (and any --assets dirs) over
localhost, loads the deck, screenshots each slide via the rail.
"""
from __future__ import annotations

import argparse
import shutil
import socket
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conftest import _find_app  # noqa: E402  (reuse the same resolution)

from playwright.sync_api import sync_playwright  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("gallery"))
    ap.add_argument("--assets", type=Path, action="append", default=[])
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args()

    staging = Path(tempfile.mkdtemp(prefix="dw-gallery-"))
    shutil.copy(_find_app(), staging / "deckwright.html")
    for src_dir in [args.deck.parent, *args.assets]:
        for f in src_dir.iterdir():
            if f.is_file() and f.suffix.lower() in {
                ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                shutil.copy(f, staging / f.name)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", port),
        partial(SimpleHTTPRequestHandler, directory=str(staging)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        pg = b.new_page(viewport={"width": args.width + 400, "height": 1000})
        pg.goto(f"http://127.0.0.1:{port}/deckwright.html")
        pg.wait_for_selector("#rail .thumb")
        pg.evaluate(
            """(src) => {
                const ta = document.getElementById('src');
                ta.value = src; ta.dispatchEvent(new Event('input'));
            }""",
            args.deck.read_text(encoding="utf-8"))
        pg.wait_for_timeout(400)
        n = pg.locator("#rail .thumb").count()
        for i in range(n):
            pg.locator("#rail .thumb").nth(i).click()
            pg.wait_for_timeout(250)
            path = args.out / f"slide{i + 1:02d}.png"
            pg.locator("#canvas").screenshot(path=str(path))
            print(path)
        b.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
