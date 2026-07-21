"""Deckwright documents: .ddz transport, the asset panel, reference
resolution, document themes, IndexedDB persistence, audience asset sync.

Asset names deliberately do NOT exist in the staging dir (doc-*.png): if
document resolution silently failed, the browser would fall back to fetching
the name relative to the app URL, and a same-named staging file would make
the test pass for the wrong reason.

Persistence is new global state: the app now autosaves to IndexedDB on every
edit, and restores on load. Each test here starts from a wiped DB and a
fresh page so no test inherits another's document (see fresh_document)."""
import io
import re
import struct
import time
import zipfile
import zlib

import pytest
from playwright.sync_api import expect

from dwtest.app import approx_rgb

MAGENTA = (255, 0, 255)
TEAL = (0, 200, 200)


# ---------------------------------------------------------------- helpers --

def solid_png(rgb, w=4, h=4) -> bytes:
    """A tiny valid PNG of one solid color, built by hand (no deps)."""
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def make_ddz(files: dict) -> bytes:
    """name -> bytes, zipped DEFLATED — this deliberately exercises the
    app's DecompressionStream inflate path, not just its own stored format."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def upload(dw, input_id, name, data, mime):
    dw.page.locator(f"#{input_id}").set_input_files(
        files=[{"name": name, "mimeType": mime, "buffer": data}])


def open_ddz(dw, files: dict, name="deck.ddz"):
    upload(dw, "importInput", name, make_ddz(files), "application/zip")


def add_asset(dw, name, data, mime="image/png"):
    # assets now enter through the single unified Load input, same as documents
    upload(dw, "importInput", name, data, mime)


IDB_READ = """() => new Promise(res => {
  const rq = indexedDB.open('deckwright', 1);
  rq.onupgradeneeded = () => rq.result.createObjectStore('kv');
  rq.onerror = () => res(null);
  rq.onsuccess = () => {
    const tx = rq.result.transaction('kv', 'readonly');
    const g = tx.objectStore('kv').get('current');
    g.onsuccess = () => {
      const r = g.result;
      res(r ? { source: r.source, filename: r.filename,
                assets: Object.keys(r.assets || {}).sort() } : null);
      rq.result.close();
    };
    g.onerror = () => { res(null); rq.result.close(); };
  };
})"""

IDB_WIPE = """() => new Promise(res => {
  const rq = indexedDB.deleteDatabase('deckwright');
  rq.onsuccess = rq.onerror = rq.onblocked = () => res();
})"""


def wait_for_persist(dw, predicate, timeout=6.0):
    """Poll the store until the autosave (800 ms debounce) has landed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rec = dw.page.evaluate(IDB_READ)
        if rec and predicate(rec):
            return rec
        time.sleep(0.1)
    raise AssertionError("autosave never landed: " + repr(dw.page.evaluate(IDB_READ)))


@pytest.fixture(autouse=True)
def fresh_document(dw):
    """Wipe persistence and reload so every test gets a virgin document —
    the in-memory doc (assets, registered document themes) survives
    set_source, so a reload is the only honest reset."""
    dw.page.evaluate(IDB_WIPE)
    dw.page.reload()
    dw.page.wait_for_selector("#rail .thumb")
    yield


# --------------------------------------------------------------- open .ddz --

DDZ_MD = """---
title: Zipped deck
theme: sun
---

<!-- image: img/doc-hero.png cover -->
# Hero
"""
DDZ_CSS = '/* @theme sun "Sunrise" */\n.slide{ --s-bg:#331100; }'


def test_ddz_open_manuscript_theme_and_assets(dw):
    open_ddz(dw, {
        "my deck.md": DDZ_MD.encode(),
        "sun.css": DDZ_CSS.encode(),
        "img/doc-hero.png": solid_png(MAGENTA),
    }, name="my deck.ddz")
    expect(dw.page.locator("#deckTitle")).to_have_text("Zipped deck")
    # the document's own theme registered and selected via front matter
    expect(dw.page.locator("#themeBtn")).to_have_text("Theme: Sunrise")
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (2)")
    # the reference resolved to a live blob of the zipped bytes
    img = dw.md.locator(".fig-cover img")
    assert img.get_attribute("src").startswith("blob:")
    assert approx_rgb(dw.canvas_pixel(0.5, 0.7), MAGENTA)


@pytest.mark.parametrize("mds", [[], ["a.md", "b.md"]], ids=["none", "two"])
def test_ddz_rejects_wrong_root_md_count(dw, mds):
    dw.set_source("---\ntitle: Before\n---\n# x")
    files = {"img/pic.png": solid_png(TEAL)}
    files.update({m: b"# m" for m in mds})
    msgs = []
    dw.page.once("dialog", lambda d: (msgs.append(d.message), d.accept()))
    open_ddz(dw, files)
    dw.page.wait_for_function("() => true")  # let the async open settle
    assert msgs and "exactly one .md" in msgs[0]
    # the current document was left untouched
    expect(dw.page.locator("#deckTitle")).to_have_text("Before")
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets")


def test_ddz_save_roundtrip_lossless_and_junk_filtered(dw):
    notes = b"unknown files ride along untouched"
    open_ddz(dw, {
        "deck.md": DDZ_MD.encode(),
        "img/doc-hero.png": solid_png(MAGENTA),
        "extra/notes.txt": notes,
        "__MACOSX/._deck.md": b"junk",
        ".DS_Store": b"junk",
    })
    expect(dw.page.locator("#deckTitle")).to_have_text("Zipped deck")
    with dw.page.expect_download() as dl:
        dw.page.locator("#exportDdzBtn").click()
    assert dl.value.suggested_filename == "deck.ddz"
    with zipfile.ZipFile(dl.value.path()) as z:
        assert sorted(z.namelist()) == ["deck.md", "extra/notes.txt", "img/doc-hero.png"]
        assert z.read("deck.md").decode() == DDZ_MD      # manuscript verbatim
        assert z.read("extra/notes.txt") == notes        # unknown file verbatim
        assert z.read("img/doc-hero.png") == solid_png(MAGENTA)


def test_opening_bare_md_replaces_document(dw):
    open_ddz(dw, {"deck.md": DDZ_MD.encode(), "sun.css": DDZ_CSS.encode(),
                  "img/doc-hero.png": solid_png(MAGENTA)})
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (2)")
    msgs = []
    dw.page.once("dialog", lambda d: (msgs.append(d.message), d.accept()))
    upload(dw, "importInput", "plain.md", b"---\ntitle: Plain\n---\n# p",
           "text/markdown")
    expect(dw.page.locator("#deckTitle")).to_have_text("Plain")
    assert msgs and "replaced" in msgs[0]
    # assets gone, the document theme unregistered, fallback theme active
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets")
    expect(dw.page.locator("#themeBtn")).to_have_text("Theme: Midnight")


def test_drop_md_loads_document_not_asset(dw):
    """A document file dropped on the manuscript LOADS (replaces) — it is not
    stored as an asset. The unified ingest router routes by type everywhere,
    so a dropped .md/.ddz opens rather than joining the current document."""
    open_ddz(dw, {"deck.md": DDZ_MD.encode(),
                  "img/doc-hero.png": solid_png(MAGENTA)})
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (1)")
    msgs = []
    dw.page.once("dialog", lambda d: (msgs.append(d.message), d.accept()))
    dw.page.evaluate(
        """([name, text]) => {
            const f = new File([text], name, {type: 'text/markdown'});
            const dt = new DataTransfer(); dt.items.add(f);
            document.getElementById('src').dispatchEvent(new DragEvent('drop',
              {bubbles: true, cancelable: true, dataTransfer: dt}));
        }""", ["dropped.md", "---\ntitle: Dropped\n---\n# d"])
    expect(dw.page.locator("#deckTitle")).to_have_text("Dropped")
    assert msgs and "replaced" in msgs[0]
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets")  # not (2)


def test_single_load_input_adds_asset_and_loads_document(dw):
    """One input, two verbs chosen by type: a non-document is ADDED to the
    current document; a document REPLACES it. There is no separate asset
    picker any more — everything comes through Load."""
    dw.set_source("---\ntitle: Keep\n---\n# keep")
    add_asset(dw, "doc-red.png", solid_png(MAGENTA))          # non-doc -> add
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (1)")
    expect(dw.page.locator("#deckTitle")).to_have_text("Keep")   # not replaced
    msgs = []
    dw.page.once("dialog", lambda d: (msgs.append(d.message), d.accept()))
    upload(dw, "importInput", "next.md",
           b"---\ntitle: Next\n---\n# n", "text/markdown")        # doc -> load
    expect(dw.page.locator("#deckTitle")).to_have_text("Next")
    assert msgs and "replaced" in msgs[0]
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets")  # add gone


# ------------------------------------------------------------- asset panel --

def test_asset_panel_add_insert_delete(dw):
    dw.set_source("# start")
    add_asset(dw, "doc-red.png", solid_png(MAGENTA))
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (1)")
    # the assets pane is open by default — no need to toggle it open
    row = dw.page.locator("#assetsList .a-row")
    expect(row).to_have_count(1)
    expect(row.locator(".a-name")).to_have_text("doc-red.png")
    row.hover()
    row.locator('.a-act[title^="Insert"]').click()
    src = dw.page.locator("#src").input_value()
    assert "<!-- image: doc-red.png -->" in src
    img = dw.md.locator(".fig img")
    assert img.get_attribute("src").startswith("blob:")
    # delete: confirm, list empties, the reference degrades to the placeholder
    dw.page.once("dialog", lambda d: d.accept())
    row.hover()
    row.locator('.a-act[title^="Remove"]').click()
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets")
    expect(dw.page.locator("#assetsList .a-empty")).to_be_visible()
    dw.page.wait_for_function(
        "() => document.querySelector('#canvas .fig img')"
        "        .src.startsWith('data:image/svg+xml')")


def test_asset_name_with_space_quotes_and_resolves(dw):
    dw.set_source("# s")
    add_asset(dw, "my pic.png", solid_png(TEAL))
    row = dw.page.locator("#assetsList .a-row")
    row.hover()
    row.locator('.a-act[title^="Insert"]').click()
    assert '<!-- image: "my pic.png" -->' in dw.page.locator("#src").input_value()
    assert dw.md.locator(".fig img").get_attribute("src").startswith("blob:")


def test_drop_on_manuscript_adds_and_inserts(dw):
    dw.set_source("# drop target")
    dw.page.evaluate(
        """([name, bytes]) => {
            const f = new File([new Uint8Array(bytes)], name, {type: 'image/png'});
            const dt = new DataTransfer(); dt.items.add(f);
            const ta = document.getElementById('src');
            ta.dispatchEvent(new DragEvent('drop',
              {bubbles: true, cancelable: true, dataTransfer: dt}));
        }""", ["doc-drop.png", list(solid_png(MAGENTA))])
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (1)")
    expect(dw.page.locator("#src")).to_have_value(
        re.compile(r"<!-- image: doc-drop\.png -->"))
    assert dw.md.locator(".fig img").get_attribute("src").startswith("blob:")


def test_assets_pane_open_by_default_and_toggles(dw):
    """The assets pane is shown on load (no click needed) and the toggle still
    closes and reopens it."""
    expect(dw.page.locator("#assetsPanel")).to_be_visible()
    expect(dw.page.locator("#assetsBtn")).to_have_class(re.compile(r"\bopen\b"))
    dw.page.locator("#assetsBtn").click()
    expect(dw.page.locator("#assetsPanel")).to_be_hidden()
    dw.page.locator("#assetsBtn").click()
    expect(dw.page.locator("#assetsPanel")).to_be_visible()


def test_assets_pane_fits_loaded_document_content(dw):
    """Opening a document fits the (default-open) pane to that document's
    assets: the first show pins an explicit, content-derived px height — not
    the CSS default — clamped so the rows fit without the list scrolling."""
    open_ddz(dw, {
        "deck.md": b"---\ntitle: A\n---\n# a",
        "one.png": solid_png(MAGENTA),
        "two.png": solid_png(TEAL),
        "three.png": solid_png(MAGENTA),
        "four.png": solid_png(TEAL),
    })
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (4)")
    # an explicit px height was pinned by the fit-to-content pass
    h = dw.page.locator("#assetsPanel").evaluate("el => el.style.height")
    assert h.endswith("px") and float(h[:-2]) >= 80
    # and the rows fit: the list isn't scrolling
    assert dw.page.locator("#assetsList").evaluate(
        "el => el.scrollHeight <= el.clientHeight + 2")


# --------------------------------------------------------- document themes --

def test_added_css_registers_theme_without_activating_then_resolves(dw):
    """A .css now arrives through the ADD path (the Load input / drop) like any
    asset: a root .css with an @theme header registers as a document theme but
    does NOT become active — activation is a separate, deliberate act. Once
    selected, its document-relative url()s resolve against the assets."""
    dw.set_source("# themed")
    add_asset(dw, "doc-bg.png", solid_png(TEAL))
    add_asset(dw, "night.css",
              ('/* @theme night "Doc Night" */\n'
               '.slide{ background: url(doc-bg.png); background-size: cover; }'
               ).encode(), "text/css")
    # registered and joined the document, but the active theme is untouched
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (2)")
    expect(dw.page.locator("#themeBtn")).to_have_text("Theme: Midnight")

    # selecting it via front matter activates it; the url() then paints the
    # asset's pixels, proving document-relative resolution in theme CSS
    dw.set_source("---\ntheme: night\n---\n# themed")
    expect(dw.page.locator("#themeBtn")).to_have_text("Theme: Doc Night")
    assert approx_rgb(dw.canvas_pixel(0.05, 0.9), TEAL)

    # both files are part of the saved document
    with dw.page.expect_download() as dl:
        dw.page.locator("#exportDdzBtn").click()
    with zipfile.ZipFile(dl.value.path()) as z:
        assert "night.css" in z.namelist() and "doc-bg.png" in z.namelist()


# ------------------------------------------------------------- persistence --

def test_autosave_and_restore_across_reload(dw):
    dw.set_source("---\ntitle: Persisted\n---\n# survives reload")
    add_asset(dw, "doc-keep.png", solid_png(MAGENTA))
    wait_for_persist(dw, lambda r: "survives reload" in r["source"]
                     and r["assets"] == ["doc-keep.png"])
    dw.page.reload()
    dw.page.wait_for_selector("#rail .thumb")
    expect(dw.page.locator("#src")).to_have_value(
        re.compile("survives reload"))
    expect(dw.page.locator("#deckTitle")).to_have_text("Persisted")
    expect(dw.page.locator("#assetsBtn")).to_have_text("Assets (1)")


# ----------------------------------------------------------- audience sync --

def test_audience_renders_document_assets(dw):
    # asset present BEFORE the popup opens: the ready-handshake path
    dw.set_source("<!-- image: doc-red.png cover -->\n# hero")
    add_asset(dw, "doc-red.png", solid_png(MAGENTA))
    aud = dw.open_audience()
    img = aud.locator("#aSlide .fig-cover img")
    expect(img).to_be_visible()
    assert img.get_attribute("src").startswith("blob:")
    # the blob actually decodes in the audience window's own realm
    aud.wait_for_function(
        "() => { const i = document.querySelector('#aSlide .fig img');"
        "        return i && i.complete && i.naturalWidth > 0; }")

    # asset added AFTER the popup opened: the push-on-change path
    add_asset(dw, "doc-late.png", solid_png(TEAL))
    dw.set_source("<!-- image: doc-late.png cover -->\n# late")
    expect(aud.locator("#aSlide h1")).to_have_text("late")
    aud.wait_for_function(
        "() => { const i = document.querySelector('#aSlide .fig img');"
        "        return i && i.src.startsWith('blob:')"
        "          && i.complete && i.naturalWidth > 0; }")


# ------------------------------------------------------------ export stays raw

def test_export_html_keeps_relative_refs(dw):
    dw.set_source("---\ntitle: t\n---\n<!-- image: doc-red.png width=50% -->")
    add_asset(dw, "doc-red.png", solid_png(MAGENTA))
    assert dw.md.locator(".fig img").get_attribute("src").startswith("blob:")
    html = dw.export_html()
    assert 'src="doc-red.png"' in html, "export must keep the document path"
    assert "blob:" not in html, "blob: URLs are dead outside this session"
    # the resolver hook was restored after the export ran
    dw.set_source("---\ntitle: t\n---\n<!-- image: doc-red.png width=50% -->")
    add_asset(dw, "doc-red.png", solid_png(MAGENTA))
    assert dw.md.locator(".fig img").get_attribute("src").startswith("blob:")
