"""The image directive, rendered for real: DOM, computed CSS, geometry,
and pixel sampling. This is the layer jsdom/node can't reach."""
import re

import pytest
from playwright.sync_api import expect

from dwtest.app import approx_rgb


def deck(body: str) -> str:
    return f"---\ntitle: t\n---\n\n{body}\n"


def test_figure_dom_and_options(dw):
    dw.set_source(deck(
        '# H\n<!-- image: "red.png" width=50% shadow caption="cap *md*" alt="Alt!" -->'
    )).select_slide(0)
    fig = dw.md.locator("figure.fig")
    expect(fig).to_have_class("fig fig-shadow align-center has-w")
    assert dw.computed(fig, "width")  # explicit width applied
    img = fig.locator("img")
    expect(img).to_have_attribute("alt", "Alt!")
    expect(img).to_have_attribute("decoding", "async")
    expect(fig.locator("figcaption em")).to_have_text("md")
    # width=50% really is half the content width
    md_box, fig_box = dw.box(dw.md), dw.box(fig)
    content_w = md_box["width"] - 2 * 86 * (md_box["width"] / 1280)
    assert fig_box["width"] == pytest.approx(content_w / 2, rel=0.02)


def test_alignment_right(dw):
    dw.set_source(deck("<!-- image: red.png width=30% right -->")).select_slide(0)
    fig, md = dw.box(dw.md.locator(".fig")), dw.box(dw.md)
    pad = 86 * (md["width"] / 1280)
    right_edge = md["x"] + md["width"] - pad
    assert fig["x"] + fig["width"] == pytest.approx(right_edge, abs=3)


def test_shadow_and_border_and_plain(dw):
    dw.set_source(deck(
        "<!-- image: red.png width=30% shadow -->\n\n"
        "<!-- image: green.png width=30% border -->\n\n"
        "<!-- image: square.png width=20% plain -->"))
    dw.select_slide(0)
    figs = dw.md.locator(".fig")
    assert "rgba(0, 0, 0" in dw.computed(figs.nth(0).locator("img"), "box-shadow")
    assert "3px solid" in dw.computed(figs.nth(1).locator("img"), "border").replace("3.", "3")
    assert dw.computed(figs.nth(2).locator("img"), "border-radius") == "0px"


def test_circle(dw):
    dw.set_source(deck("<!-- image: square.png circle -->")).select_slide(0)
    img = dw.md.locator(".fig-circle img")
    assert dw.computed(img, "border-radius").endswith("%") or "50%" in dw.computed(img, "border-radius")
    b = dw.box(img)
    assert b["width"] == pytest.approx(b["height"], abs=2)  # aspect 1:1


def test_bleed_spans_full_slide_width(dw):
    dw.set_source(deck("above\n<!-- image: blue-wide.png bleed -->\nbelow"))
    dw.select_slide(0)
    fig, slide = dw.box(dw.md.locator(".fig-bleed img")), dw.box(dw.slide)
    assert fig["x"] == pytest.approx(slide["x"], abs=2)
    assert fig["width"] == pytest.approx(slide["width"], abs=3)
    # and it stayed in flow: text exists above and below
    expect(dw.md.locator("p").nth(0)).to_have_text("above")
    expect(dw.md.locator("p").nth(1)).to_have_text("below")


def test_cover_fills_slide_under_text(dw):
    dw.set_source(deck(
        "<!-- layout: cover -->\n<!-- image: red.png cover -->\n# On top"))
    dw.select_slide(0)
    fig, slide = dw.box(dw.md.locator(".fig-cover")), dw.box(dw.slide)
    for k in ("x", "y", "width", "height"):
        assert fig[k] == pytest.approx(slide[k], abs=2)
    assert dw.computed(dw.md.locator(".fig-cover"), "z-index") == "-1"
    # a corner far from the heading is pure image red
    assert approx_rgb(dw.canvas_pixel(0.97, 0.97), (255, 0, 0))
    # the heading is genuinely painted over the image
    expect(dw.md.locator("h1")).to_be_visible()


def test_cover_dim_darkens_pixels(dw):
    dw.set_source(deck("<!-- image: red.png cover dim=0.5 -->"))
    dw.select_slide(0)
    fig = dw.md.locator(".fig-cover")
    assert "brightness(0.5)" in dw.computed(fig.locator("img"), "filter")
    assert approx_rgb(dw.canvas_pixel(0.5, 0.5), (128, 0, 0), tol=14)


def test_contain_letterboxes(dw):
    # blue-wide is 4:1 — contained in 16:9 it leaves slide bg above/below
    dw.set_source(deck("<!-- bg: #000000 -->\n<!-- image: blue-wide.png contain -->"))
    dw.select_slide(0)
    assert approx_rgb(dw.canvas_pixel(0.5, 0.5), (0, 80, 255))   # image band
    assert approx_rgb(dw.canvas_pixel(0.5, 0.04), (0, 0, 0))     # letterbox


def test_cover_inside_split_column(dw):
    dw.set_source(deck(
        "<!-- layout: split -->\n<!-- image: green.png cover -->\n==\n## Right"))
    dw.select_slide(0)
    fig = dw.canvas.locator(".col .fig-cover")
    col = dw.canvas.locator(".col").first
    fb, cb, sb = dw.box(fig), dw.box(col), dw.box(dw.slide)
    for k in ("x", "y", "width", "height"):
        assert fb[k] == pytest.approx(cb[k], abs=2)
    gap = 64 * (sb["width"] / 1280)  # .cols grid gap, scaled
    assert fb["width"] == pytest.approx((sb["width"] - gap) / 2, abs=3)
    assert approx_rgb(dw.canvas_pixel(0.25, 0.5), (0, 200, 0))   # left = image
    assert not approx_rgb(dw.canvas_pixel(0.75, 0.5), (0, 200, 0))  # right isn't


def test_bleed_inside_column(dw):
    dw.set_source(deck(
        "<!-- layout: split -->\n### L\n<!-- image: red.png bleed -->\n==\n### R"))
    dw.select_slide(0)
    img = dw.canvas.locator(".col .fig-bleed img")
    col = dw.canvas.locator(".col").first
    ib, cb = dw.box(img), dw.box(col)
    assert ib["x"] == pytest.approx(cb["x"], abs=2)
    assert ib["width"] == pytest.approx(cb["width"], abs=3)


def test_missing_image_shows_placeholder(dw):
    dw.set_source(deck("<!-- image: nope_missing.png width=50% -->"))
    dw.select_slide(0)
    img = dw.md.locator(".fig img")
    expect(img).to_have_js_property("complete", True)
    src = img.get_attribute("src")
    # onerror swapped in the generated placeholder…
    dw.page.wait_for_function(
        "() => document.querySelector('#canvas .fig img').src.startsWith('data:image/svg+xml')")
    # …which names the missing file
    assert "nope_missing.png" in dw.page.evaluate(
        "() => decodeURIComponent(document.querySelector('#canvas .fig img').src)")


def test_legacy_markdown_image_untouched(dw):
    dw.set_source(deck("![alt](red.png)")).select_slide(0)
    expect(dw.md.locator("p > img")).to_have_attribute("alt", "alt")
    expect(dw.md.locator("figure")).to_have_count(0)


def test_caption_and_alt_fallback_chain(dw):
    dw.set_source(deck(
        '<!-- image: red.png caption="From caption" -->\n\n'
        "<!-- image: img/deep/red.png -->"))
    dw.select_slide(0)
    imgs = dw.md.locator(".fig img")
    expect(imgs.nth(0)).to_have_attribute("alt", "From caption")
    expect(imgs.nth(1)).to_have_attribute("alt", "red.png")  # basename fallback
