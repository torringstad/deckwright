"""Presenter view and the dual-window audience sync (popup + postMessage)."""
from playwright.sync_api import expect

DECK = "# one\n---\n# two\n---\n# three"


def test_presenter_view_current_next_notes(dw):
    dw.set_source("<!-- notes: say hi -->\n# one\n---\n# two").select_slide(0)
    dw.enter_presenter()
    expect(dw.page.locator("#pCurrent h1")).to_have_text("one")
    expect(dw.page.locator("#pNext h1")).to_have_text("two")
    expect(dw.page.locator("#pNotes")).to_have_text("say hi")
    expect(dw.page.locator("#pCounter")).to_have_text("01 / 02")
    dw.page.locator("#pNext2").click()
    expect(dw.page.locator("#pCurrent h1")).to_have_text("two")
    expect(dw.page.locator("#pNext")).to_contain_text("END OF DECK")
    dw.exit_presenter()


def test_audience_receives_deck_and_tracks_nav(dw):
    dw.set_source(DECK).select_slide(0)
    aud = dw.open_audience()
    expect(aud.locator("#aSlide h1")).to_have_text("one")
    expect(aud.locator("#aCounter")).to_have_text("01 / 03")
    # editor navigates -> audience follows
    dw.select_slide(1)
    expect(aud.locator("#aSlide h1")).to_have_text("two")
    expect(aud.locator("#aCounter")).to_have_text("02 / 03")


def test_audience_backnav_updates_editor(dw):
    dw.set_source(DECK).select_slide(2)
    aud = dw.open_audience()
    expect(aud.locator("#aSlide h1")).to_have_text("three")
    aud.keyboard.press("ArrowLeft")
    expect(aud.locator("#aSlide h1")).to_have_text("two")
    expect(dw.canvas.locator("h1")).to_have_text("two")  # echoed back


def test_live_edit_pushes_to_audience(dw):
    dw.set_source("# before")
    aud = dw.open_audience()
    expect(aud.locator("#aSlide h1")).to_have_text("before")
    dw.set_source("# after")
    expect(aud.locator("#aSlide h1")).to_have_text("after")


def test_audience_status_and_hide(dw):
    dw.set_source(DECK)
    aud = dw.open_audience()
    expect(dw.page.locator("#audienceBtn")).to_have_text("Hide audience")
    dw.page.locator("#audienceBtn").click()
    expect(dw.page.locator("#audienceBtn")).to_have_text("Show audience")
    assert aud.is_closed()


def test_image_slide_reaches_audience(dw):
    dw.set_source("<!-- image: red.png cover dim=0.4 -->\n# hero")
    aud = dw.open_audience()
    fig = aud.locator("#aSlide .fig-cover img")
    expect(fig).to_be_visible()
    assert "brightness(0.6)" in fig.evaluate("el => getComputedStyle(el).filter")
