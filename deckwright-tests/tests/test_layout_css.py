"""Slide-level rendering: layouts, zoom geometry, bg, themes, transitions."""
import pytest
from playwright.sync_api import expect

from dwtest.app import approx_rgb


def test_layout_classes(dw):
    dw.set_source("# a\n---\n<!-- layout: center -->\nb\n---\n"
                  "<!-- layout: split -->\nL\n==\nR")
    dw.select_slide(1)
    expect(dw.md).to_have_class("md lay-center")
    dw.select_slide(2)
    expect(dw.md).to_have_class("md lay-split")
    expect(dw.canvas.locator(".col")).to_have_count(2)


def test_split_bands(dw):
    dw.set_source("<!-- layout: split -->\nTOP\n==\nL\n==\nR\n==\nBOT")
    dw.select_slide(0)
    expect(dw.canvas.locator(".band-top")).to_have_text("TOP")
    expect(dw.canvas.locator(".band-bottom")).to_have_text("BOT")
    cols = dw.canvas.locator(".col")
    expect(cols.nth(0)).to_have_text("L")
    expect(cols.nth(1)).to_have_text("R")


def test_zoom_scales_logical_canvas(dw):
    dw.set_source("<!-- zoom: 0.8 -->\n# z")
    dw.select_slide(0)
    stage = dw.canvas.locator(".stage")
    w = stage.evaluate("el => parseFloat(el.style.width)")
    assert w == pytest.approx(1280 / 0.8, abs=1)
    # the slide box itself is unchanged: stage*scale fills it exactly
    sb, slb = dw.box(stage), dw.box(dw.slide)
    assert sb["width"] == pytest.approx(slb["width"], abs=1)


def test_bg_color_and_bg_image(dw):
    dw.set_source("<!-- bg: #ff0000 -->\n# r\n---\n"
                  "<!-- bg: url(green.png) -->\n# g")
    dw.select_slide(0)
    assert approx_rgb(dw.canvas_pixel(0.05, 0.9), (255, 0, 0))
    dw.select_slide(1)
    assert approx_rgb(dw.canvas_pixel(0.05, 0.9), (0, 200, 0))


def test_theme_front_matter_and_cycle_button(dw):
    dw.set_source("---\ntheme: paper\n---\n# t")
    expect(dw.page.locator("#themeBtn")).to_have_text("Theme: Paper")
    # paper is a light theme: slide bg must be light
    r, g, b = dw.canvas_pixel(0.02, 0.02)
    assert r > 200 and g > 200 and b > 200
    dw.page.locator("#themeBtn").click()
    expect(dw.page.locator("#themeBtn")).not_to_have_text("Theme: Paper")


def test_transition_directive_parsed_and_animates(dw):
    dw.set_source("<!-- transition: fade -->\n# one\n---\n"
                  "<!-- transition: fade -->\n# two")
    dw.key("ArrowRight")
    expect(dw.canvas.locator("h1")).to_have_text("two")
    assert dw.badge_count().startswith("02")
