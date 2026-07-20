"""Page object for Deckwright.

All tests talk to the app through this class, and only through public
behavior: the DOM, keyboard, mouse, downloads, popups. The one deliberate
exception: the engine/parser functions (mdToHtml, parseDeck, …) are
top-level in the app's script and therefore reachable from page.evaluate —
the unit-level tests call them directly in the real browser, so there is
exactly one implementation under test and zero re-implementation drift.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image
from playwright.sync_api import Locator, Page, expect

REPARSE_DEBOUNCE_MS = 120  # mirrors the app's input debounce


class Deckwright:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    # ---- lifecycle -------------------------------------------------------
    def goto(self) -> "Deckwright":
        self.page.goto(self.base_url + "/deckwright.html")
        expect(self.page.locator("#rail .thumb").first).to_be_visible()
        return self

    def set_source(self, md: str) -> "Deckwright":
        """Type-equivalent: set the manuscript and fire the input pipeline."""
        self.page.evaluate(
            """(src) => {
                const ta = document.getElementById('src');
                ta.value = src;
                ta.dispatchEvent(new Event('input'));
            }""",
            md,
        )
        # outlive the debounce; individual assertions still auto-retry
        self.page.wait_for_timeout(REPARSE_DEBOUNCE_MS + 150)
        return self

    # ---- engine access (same-realm, no re-implementation) ----------------
    def md_to_html(self, md: str) -> str:
        return self.page.evaluate("(s) => mdToHtml(s)", md)

    def md_inline(self, md: str) -> str:
        return self.page.evaluate("(s) => mdInline(s)", md)

    def parse_deck(self, src: str) -> dict:
        return json.loads(
            self.page.evaluate(
                """(s) => {
                    const d = parseDeck(s);
                    return JSON.stringify({
                        meta: d.meta,
                        warnings: d.warnings,
                        slides: d.slides.map(x => ({
                            body: x.body, layout: x.layout, bg: x.bg,
                            transition: x.transition, notes: x.notes,
                            zoom: x.zoom, warnings: x.warnings,
                            start: x.start, end: x.end,
                        })),
                    });
                }""",
                src,
            )
        )

    # ---- locators --------------------------------------------------------
    @property
    def canvas(self) -> Locator:
        return self.page.locator("#canvas")

    @property
    def slide(self) -> Locator:
        return self.canvas.locator(".slide")

    @property
    def md(self) -> Locator:
        return self.canvas.locator(".md")

    @property
    def thumbs(self) -> Locator:
        return self.page.locator("#rail .thumb")

    @property
    def err_box(self) -> Locator:
        return self.page.locator("#errBox")

    # ---- navigation ------------------------------------------------------
    def select_slide(self, i: int) -> "Deckwright":
        self.thumbs.nth(i).click()
        expect(self.thumbs.nth(i)).to_have_class("thumb active")
        return self

    def key(self, key: str) -> "Deckwright":
        # keyboard nav is ignored while the manuscript has focus in edit view
        self.page.locator(".stagewrap").click(position={"x": 5, "y": 5})
        self.page.keyboard.press(key)
        return self

    def badge_count(self) -> str:
        return self.page.locator("#badgeCount").inner_text()

    # ---- views -----------------------------------------------------------
    def enter_presenter(self) -> "Deckwright":
        self.page.locator("#viewBtn").click()
        expect(self.page.locator("#presenter")).to_have_class("on")
        return self

    def exit_presenter(self) -> "Deckwright":
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#presenter")).not_to_have_class("on")
        return self

    def open_audience(self) -> Page:
        with self.page.context.expect_page() as popup_info:
            self.page.locator("#audienceBtn, #audienceBtn2").locator("visible=true").click()
        popup = popup_info.value
        popup.wait_for_load_state()
        expect(popup.locator("#aSlide .slide")).to_be_visible()
        return popup

    # ---- export ----------------------------------------------------------
    def export_html(self) -> str:
        with self.page.expect_download() as dl:
            self.page.locator("#exportHtmlBtn").click()
        return Path(dl.value.path()).read_text(encoding="utf-8")

    # ---- geometry & pixels ----------------------------------------------
    def box(self, locator: Locator) -> dict:
        b = locator.bounding_box()
        assert b, f"no bounding box for {locator}"
        return b

    def computed(self, locator: Locator, prop: str) -> str:
        return locator.evaluate(
            "(el, p) => getComputedStyle(el).getPropertyValue(p)", prop
        )

    def canvas_pixel(self, fx: float, fy: float) -> tuple[int, int, int]:
        """Sample the rendered slide at fractional coordinates (0..1)."""
        shot = self.canvas.screenshot()
        img = Image.open(io.BytesIO(shot)).convert("RGB")
        return img.getpixel((int(img.width * fx), int(img.height * fy)))


def approx_rgb(actual, expected, tol=12) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected))
