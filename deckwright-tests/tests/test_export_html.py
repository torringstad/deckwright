"""Save / Export HTML — capture the real downloads, then RENDER the exported
file in the browser and assert the slides survived the round trip."""
import re

from playwright.sync_api import expect

DECK = """---
title: Export me
theme: paper
---

# One
<!-- image: red.png width=50% shadow caption="fig one" -->
---
<!-- layout: split -->
<!-- image: green.png cover -->
==
## Right
"""


def test_save_roundtrips_source(dw):
    dw.set_source(DECK)
    with dw.page.expect_download() as dl:
        dw.page.locator("#exportBtn").click()
    saved = open(dl.value.path(), encoding="utf-8").read()
    assert saved == DECK  # the document IS the file


def test_export_html_static_and_complete(dw, staging, base_url):
    dw.set_source(DECK)
    html = dw.export_html()

    assert "<script" not in html.lower(), "export must be script-free"
    assert html.count('class="slide') == 2
    assert "@layer deck-base" in html and "@layer deck-theme" in html
    # the image-directive CSS made it through the SLIDE-CSS slice
    for needle in (".fig{", "fig-cover", "fig-bleed", "figcaption"):
        assert needle in html, f"missing {needle} in exported CSS"
    assert 'src="red.png"' in html and "fig one" in html

    # now actually render the export next to the images it references
    (staging / "exported.html").write_text(html, encoding="utf-8")
    page = dw.page.context.new_page()
    page.goto(base_url + "/exported.html")
    expect(page.locator(".slide")).to_have_count(2)
    expect(page.locator(".slide").first.locator("figcaption")).to_have_text("fig one")
    cover = page.locator(".slide").nth(1).locator(".col .fig-cover")
    expect(cover).to_be_visible()
    # theme applied: paper is light
    bg = page.locator(".slide").first.evaluate(
        "el => getComputedStyle(el).backgroundColor")
    nums = [int(x) for x in re.findall(r"\d+", bg)[:3]]
    assert all(n > 200 for n in nums), bg
    page.close()


def test_export_filename_derived_from_title(dw):
    dw.set_source("---\ntitle: Weird/Name Here\n---\n# x")
    with dw.page.expect_download() as dl:
        dw.page.locator("#exportHtmlBtn").click()
    assert dl.value.suggested_filename == "Weird_Name_Here.html"
