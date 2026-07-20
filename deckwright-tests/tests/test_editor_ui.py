"""Editor chrome: rail, caret sync, keyboard, notes, warnings box."""
from playwright.sync_api import expect

THREE = "# one\n---\n# two\n---\n# three"


def test_rail_thumbs_and_click_nav(dw):
    dw.set_source(THREE)
    expect(dw.thumbs).to_have_count(3)
    dw.select_slide(2)
    expect(dw.canvas.locator("h1")).to_have_text("three")
    assert dw.badge_count() == "03 / 03"
    # thumbnails are real rendered slides, frozen
    expect(dw.thumbs.nth(1).locator(".slide")).to_have_class("slide still")


def test_keyboard_navigation_and_bounds(dw):
    dw.set_source(THREE).select_slide(0)
    dw.key("ArrowRight")
    expect(dw.canvas.locator("h1")).to_have_text("two")
    dw.key("ArrowLeft")
    dw.key("ArrowLeft")  # underflow clamps
    expect(dw.canvas.locator("h1")).to_have_text("one")


def test_caret_moves_select_slide(dw):
    dw.set_source(THREE)
    pos = THREE.index("# two") + 2
    dw.page.evaluate(
        """(pos) => {
            const ta = document.getElementById('src');
            ta.focus(); ta.setSelectionRange(pos, pos);
            ta.dispatchEvent(new KeyboardEvent('keyup'));
        }""", pos)
    expect(dw.canvas.locator("h1")).to_have_text("two")
    expect(dw.thumbs.nth(1)).to_have_class("thumb active")


def test_rail_click_places_caret_in_slide(dw):
    dw.set_source(THREE).select_slide(2)
    start = dw.page.evaluate("() => document.getElementById('src').selectionStart")
    assert start >= THREE.index("# three")


def test_notes_panel_and_toggle(dw):
    dw.set_source("<!-- notes: remember this -->\n# n")
    dw.select_slide(0)
    expect(dw.page.locator("#notesText")).to_have_text("remember this")
    dw.page.locator("#notesBtn").click()
    expect(dw.page.locator("#notesPanel")).to_be_hidden()
    dw.page.locator("#notesBtn").click()
    expect(dw.page.locator("#notesPanel")).to_be_visible()


def test_errbox_warnings_lifecycle(dw):
    dw.set_source("# ok\n<!-- imgae: typo.png -->")
    expect(dw.err_box).to_be_visible()
    expect(dw.err_box).to_have_class("err warn")
    expect(dw.err_box).to_contain_text('slide 1: unknown directive "imgae"')
    dw.set_source("# all fixed")
    expect(dw.err_box).to_be_hidden()


def test_deck_title_from_front_matter(dw):
    dw.set_source("---\ntitle: Hello Deck\n---\n# x")
    expect(dw.page.locator("#deckTitle")).to_have_text("Hello Deck")
