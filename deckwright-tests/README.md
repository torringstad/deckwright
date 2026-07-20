# Deckwright test system

Python-driven, full-application tests: pytest + Playwright drive a real
Chromium against the actual `deckwright.html` served over localhost HTTP.
No part of the app is re-implemented for testing — even the markdown-engine
unit tests call the app's own `mdToHtml`/`parseDeck` in the live page, so
there is exactly one implementation under test.

## Setup

    pip install -r requirements.txt
    playwright install chromium
    pytest

The app under test is resolved from `$DECKWRIGHT_HTML`, or `deckwright.html`
found in this directory, its parent, or the working directory.

## What's covered

`tests/test_engine_md.py` — markdown blocks and inlines, fenced-code
protection, escaping (`\<!--`), directive paragraph-breaking, HTML injection
safety.

`tests/test_parser_deck.py` — front matter, slide splitting and source
ranges, slide- vs block-directive routing, the warnings channel (unknown
names, bad options, fence/escape immunity).

`tests/test_image_directive.py` — the image directive rendered for real:
DOM shape, computed CSS, geometry (`width=50%` measures half the content
width; `bleed` spans the slide; `cover` fills the slide — or the column in
split layout), and pixel sampling against generated solid-color images
(`dim=0.5` on pure red must sample ≈ rgb(128,0,0); `contain` letterboxes).
Placeholder fallback for missing files.

`tests/test_layout_css.py` — layouts and split bands, zoom geometry, `bg:`
color and image (by pixel), theme front matter and cycling, transitions.

`tests/test_editor_ui.py` — rail thumbnails and click-nav, keyboard nav with
clamping, caret→slide sync and rail→caret sync, notes panel, errBox warning
lifecycle, deck title.

`tests/test_presenter_audience.py` — presenter view (current/next/notes/
counter), the audience popup: deck transfer, nav sync both directions, live
edits pushed, hide/show, image CSS arriving in the popup.

`tests/test_export_html.py` — Save round-trips the source byte-identically;
Export HTML is captured as a real download, asserted script-free and
complete, then **rendered in the browser next to its images** and checked
(slides, figures, captions, theme colors).

## Conventions

Tests interact through public behavior only: DOM, keyboard, mouse,
downloads, popups. Pixel assertions use `dwtest/assets.py`'s generated
images with known colors. On any failure a full-page screenshot of every
open window is written to `test-results/`.

Env knobs: `HEADED=1` watches the browser, `SLOWMO=250` slows actions,
`CHROMIUM_PATH=` overrides the browser binary.

## Dev tool

    python scripts/gallery.py my_deck.md -o gallery/

renders every slide of a deck to PNGs (serving the deck's directory so
co-located images resolve) — quick visual review of CSS or theme changes.

## Validation

The suite has been mutation-checked: deliberately breaking the directive
paragraph rule, the bleed CSS, and the audience sync each made the
corresponding tests (and only sensible ones) fail. Full run: 58 tests,
~30 s headless.
