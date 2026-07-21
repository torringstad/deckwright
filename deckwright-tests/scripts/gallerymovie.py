#!/usr/bin/env python3.12
"""Record a movie of a deck being "typed" slide by slide — a dev tool for
demoing/eyeballing changes as motion.

    python scripts/gallerymovie.py my_deck.md [-o out.webm] [--assets DIR]
                                   [--slides 2-5] [--cps 40] [--width 1280]

Serves deckwright.html + the deck's directory (and any --assets dirs) over
localhost, then simulates a human typing the deck source into the editor,
one slide at a time, while Playwright records the page to a video.
"""
from __future__ import annotations

import argparse
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conftest import _find_app  # noqa: E402  (reuse the same resolution)

from playwright.sync_api import sync_playwright  # noqa: E402


def split_slides(src: str) -> list[str]:
    """Split deck source into slide chunks on '---' separator lines,
    keeping the separators attached to the following slide so the
    reconstructed source is byte-identical to the input."""
    lines = src.split("\n")
    slides: list[list[str]] = [[]]
    for ln in lines:
        if re.fullmatch(r"\s*---+\s*", ln) and slides[-1]:
            slides.append([])
        slides[-1].append(ln)
    return ["\n".join(chunk) for chunk in slides]


def transcode(webm: Path, out: Path, fps: int | None,
              resize: float = 1.0) -> None:
    """Transcode the recorded webm to `out` based on its extension using
    ffmpeg. .mp4 -> H.264/yuv420p (broad compatibility); .gif -> two-pass
    palette for decent color. `resize` scales the frame (1.0 = none)."""
    ext = out.suffix.lower()
    rate = ["-r", str(fps)] if fps else []
    scale = f"trunc(iw*{resize}/2)*2:-1" if resize != 1.0 \
        else "trunc(iw/2)*2:-1"
    if ext == ".gif":
        # Pass 1: generate palette. Pass 2: apply it.
        palette = out.with_suffix(".palette.png")
        vf = "fps={},scale={}:flags=lanczos".format(fps or 15, scale)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(webm),
             "-vf", f"{vf},palettegen", str(palette)],
            check=True)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(webm), "-i", str(palette),
             "-lavfi", f"{vf} [x]; [x][1:v] paletteuse", str(out)],
            check=True)
        palette.unlink(missing_ok=True)
    else:
        vf = ["-vf", f"scale={scale}:flags=lanczos"] if resize != 1.0 else []
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(webm),
             *rate, *vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
            check=True)


def parse_range(spec: str, n: int) -> range:
    """Parse a 1-based inclusive slide range like '3', '2-5', '2-', '-4'
    into a 0-based range over n slides."""
    spec = spec.strip()
    if "-" in spec:
        lo_s, hi_s = spec.split("-", 1)
        lo = int(lo_s) if lo_s.strip() else 1
        hi = int(hi_s) if hi_s.strip() else n
    else:
        lo = hi = int(spec)
    lo = max(1, lo)
    hi = min(n, hi)
    if lo > hi:
        raise SystemExit(f"empty slide range: {spec!r} over {n} slides")
    return range(lo - 1, hi)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("gallery.webm"))
    ap.add_argument("--assets", type=Path, action="append", default=[])
    ap.add_argument("--slides", default=None,
                    help="1-based slide range, e.g. 3, 2-5, 2-, -4")
    ap.add_argument("--cps", type=int, default=60,
                    help="typing speed in characters per second")
    ap.add_argument("--fps", type=int, default=None,
                    help="frame rate for transcoded (non-webm) output")
    ap.add_argument("--resize", type=float, default=1.0,
                    help="scale factor for transcoded (non-webm) output; "
                         "1.0 = none, 0.5 = 50%%")
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args()

    staging = Path(tempfile.mkdtemp(prefix="dw-gallerymovie-"))
    shutil.copy(_find_app(), staging / "deckwright.html")
    for src_dir in [args.deck.parent, *args.assets]:
        for f in src_dir.iterdir():
            if f.is_file() and f.suffix.lower() in {
                ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                shutil.copy(f, staging / f.name)

    src = args.deck.read_text(encoding="utf-8")
    slides = split_slides(src)
    sel = parse_range(args.slides, len(slides)) if args.slides \
        else range(len(slides))
    chunks = [slides[i] for i in sel]
    # Slides before the selected range are "fast-forwarded": their source is
    # injected instantly (off camera) so the app's slide index / preview /
    # rail state is correct before typing begins.
    preamble = "\n".join(slides[:sel.start])

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", port),
        partial(SimpleHTTPRequestHandler, directory=str(staging)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    vw, vh = args.width + 400, 1000
    delay_ms = max(1, round(1000 / args.cps))

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = b.new_context(
            viewport={"width": vw, "height": vh},
            record_video_dir=str(staging),
            record_video_size={"width": vw, "height": vh})
        pg = ctx.new_page()
        pg.goto(f"http://127.0.0.1:{port}/deckwright.html")
        pg.wait_for_selector("#rail .thumb")

        # Fast-forward: instantly inject the source for all slides before the
        # selected range so the app state is up to date, then place the caret
        # at the end so the freshly-typed slides append correctly.
        pg.evaluate("""(v) => {
            const ta = document.getElementById('src');
            ta.value = v;
            ta.selectionStart = ta.selectionEnd = v.length;
            ta.dispatchEvent(new Event('input', {bubbles: true}));
            ta.dispatchEvent(new Event('keyup', {bubbles: true}));
            document.dispatchEvent(new Event('selectionchange'));
        }""", preamble)
        pg.wait_for_timeout(300)

        # The app debounces preview re-render, so periodically pause long
        # enough to let it flush — this makes the preview advance mid-slide
        # instead of only at the end.
        flush_ms = 350

        ta = pg.locator("#src")
        ta.click()
        acc = preamble
        for ci, chunk in enumerate(chunks):
            text = chunk if (ci == 0 and not preamble) else "\n" + chunk
            for ch in text:
                acc += ch
                pg.evaluate("""(v) => {
                    const ta = document.getElementById('src');
                    ta.value = v;
                    ta.selectionStart = ta.selectionEnd = v.length;
                    ta.dispatchEvent(new Event('input', {bubbles: true}));
                    ta.dispatchEvent(new Event('keyup', {bubbles: true}));
                    document.dispatchEvent(new Event('selectionchange'));
                }""", acc)
                pg.wait_for_timeout(delay_ms)
                # Let the debounced preview catch up at end of each line.
                if ch == "\n":
                    pg.wait_for_timeout(flush_ms)
            # Pause on the freshly-typed slide so it lingers in the movie.
            pg.wait_for_timeout(800)

        pg.wait_for_timeout(600)
        video = pg.video
        ctx.close()  # finalizes the video file
        if video:
            if args.out.suffix.lower() == ".webm":
                video.save_as(str(args.out))
                print(args.out)
            else:
                tmp_webm = args.out.with_suffix(".webm")
                video.save_as(str(tmp_webm))
                transcode(tmp_webm, args.out, args.fps, args.resize)
                tmp_webm.unlink(missing_ok=True)
                print(args.out)
        b.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
