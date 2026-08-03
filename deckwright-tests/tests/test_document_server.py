"""Document server mode: deckserver.py serving the document directory.

These tests have two actors — the app in the browser and the directory on
disk — and assert the contract between them: boot pulls the tree, edits
flush back as diffs, external edits arrive silently, and only a file dirty
on BOTH sides in the same window asks the user which version wins.

Needs deckserver's deps (bottle, waitress) importable, and deckserver.py
next to the app under test (or $DECKSERVER_PY).

Timing notes: the app debounces flushes at 800 ms and polls the manifest
every 2500 ms, so positive assertions poll the disk/DOM with a generous
deadline, and every "nothing happened" assertion sleeps past at least one
poll interval before looking.
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

import conftest
from dwtest.app import Deckwright

pytest.importorskip("bottle", reason="deckserver needs bottle")
pytest.importorskip("waitress", reason="deckserver needs waitress")

FLUSH_S = 0.8      # app-side debounce
POLL_S = 2.5       # app-side manifest poll

MD = "---\ntitle: Served\ntheme: midnight\n---\n\n# hello\n\nfrom disk\n"
PNG = bytes.fromhex(  # 1x1 red png
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8cfc000000301010018dd8db00000000049"
    "454e44ae426082"
)


def _find_server() -> Path:
    env = os.environ.get("DECKSERVER_PY")
    candidates = [Path(env)] if env else [
        conftest._find_app().parent / "deckserver.py",
        Path.cwd() / "deckserver.py",
    ]
    for c in candidates:
        if c and c.is_file():
            return c.resolve()
    raise pytest.UsageError(
        "deckserver.py not found — set DECKSERVER_PY or place it next to "
        "the app under test")


def wait_until(fn, timeout=10.0, *, page=None):
    """Poll fn. When a page is given, wait on IT rather than time.sleep:
    the sync Playwright API dispatches event callbacks (our dialog handler
    answering the app's confirm()) only while the test thread is inside a
    Playwright call — a pure time.sleep loop would leave a pending dialog
    unanswered and the app's sync lane frozen behind it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fn():
            return True
        if page is not None:
            page.wait_for_timeout(100)
        else:
            time.sleep(0.1)
    return False


class Server:
    def __init__(self, docdir: Path, app_html: Path, extra=()):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.dir = docdir
        self.proc = subprocess.Popen(
            [sys.executable, str(_find_server()), str(docdir),
             "--port", str(port), "--app", str(app_html), *extra],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        banner = ""
        deadline = time.time() + 10
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            banner += line
            m = re.search(r"open:\s+(\S+)", line)
            if m:
                self.url = m.group(1)                    # incl. ?token=…
                self.base = self.url.split("/?")[0]
                return
            if self.proc.poll() is not None:
                break
        raise RuntimeError("deckserver did not start:\n" + banner)

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


@pytest.fixture
def docdir(tmp_path) -> Path:
    (tmp_path / "talk.md").write_text(MD, encoding="utf-8")
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "logo.png").write_bytes(PNG)
    return tmp_path


@pytest.fixture
def server(docdir, staging):
    s = Server(docdir, staging / "deckwright.html")
    yield s
    s.stop()


@pytest.fixture
def dw(browser, server) -> Deckwright:
    """Same name as the base fixture on purpose: the failure-screenshot hook
    keys on `dw`. Dialogs are recorded; `dw.answer` decides accept/dismiss."""
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000},
                              accept_downloads=True)
    page = ctx.new_page()
    app = Deckwright(page, server.base)
    app.dialogs = []
    app.answer = True
    page.on("dialog", lambda d: (app.dialogs.append(d.message),
                                 d.accept() if app.answer else d.dismiss()))
    page.goto(server.url)
    # the thumb appears already in the pre-boot quick render; the badge is
    # the public signal that the server boot actually completed
    expect(page.get_by_text("serving " + server.dir.name)).to_be_visible()
    yield app
    ctx.close()


def manuscript(server) -> str:
    return (server.dir / "talk.md").read_text(encoding="utf-8")


# ---- boot ----------------------------------------------------------------

def test_boot_pulls_document_from_directory(dw, server):
    assert dw.page.locator("#src").input_value() == MD
    expect(dw.page.locator("#deckTitle")).to_have_text("Served")
    expect(dw.page.locator("#assetsList")).to_contain_text("img/logo.png")
    assert dw.dialogs == []


def test_empty_directory_starts_fresh_deck_and_materializes_it(
        browser, staging, tmp_path):
    s = Server(tmp_path, staging / "deckwright.html")
    try:
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = ctx.new_page()
        page.goto(s.url)
        expect(page.get_by_text("serving " + tmp_path.name)).to_be_visible()
        assert wait_until(lambda: (tmp_path / "deck.md").is_file(), page=page)
        assert "New deck" in (tmp_path / "deck.md").read_text(encoding="utf-8")
        ctx.close()
    finally:
        s.stop()


def test_two_root_manuscripts_refused_at_startup(tmp_path, staging):
    (tmp_path / "a.md").write_text("# a")
    (tmp_path / "b.md").write_text("# b")
    with pytest.raises(RuntimeError) as e:
        Server(tmp_path, staging / "deckwright.html")
    assert "more than one root .md" in str(e.value)


# ---- outbound: the app writes the directory ------------------------------

def test_edit_flushes_to_disk(dw, server):
    dw.set_source(MD + "\nedited in app\n")
    assert wait_until(lambda: "edited in app" in manuscript(server), page=dw.page)
    assert dw.dialogs == []


def test_asset_upload_and_delete_reach_disk(dw, server, tmp_path_factory):
    up = tmp_path_factory.mktemp("up") / "extra.png"
    up.write_bytes(PNG)
    dw.page.locator("#importInput").set_input_files(str(up))
    expect(dw.page.locator("#assetsList")).to_contain_text("extra.png")
    assert wait_until(lambda: (server.dir / "extra.png").is_file(), page=dw.page)

    row = dw.page.locator("#assetsList .a-row", has_text="extra.png")
    row.hover()                      # action buttons are hover-revealed
    row.locator("button", has_text="×").click()   # confirm auto-accepted
    assert wait_until(lambda: not (server.dir / "extra.png").exists(), page=dw.page)
    assert any("Remove extra.png" in m for m in dw.dialogs)


def test_theme_button_edits_front_matter_and_reaches_disk(dw, server):
    dw.page.locator("#themeBtn").click()
    assert wait_until(
        lambda: re.search(r"^theme: (?!midnight)(\w+)$",
                          manuscript(server), re.M), page=dw.page)
    new = re.search(r"^theme: (\w+)$", manuscript(server), re.M).group(1)
    assert new.lower() in dw.page.locator("#themeBtn").inner_text().lower()
    # and it is a manuscript edit, visible in the editor too
    assert f"theme: {new}" in dw.page.locator("#src").input_value()


# ---- inbound: the directory changes under the app ------------------------

def test_external_manuscript_edit_pulls_silently(dw, server):
    (server.dir / "talk.md").write_text(MD + "\nedited on disk\n",
                                        encoding="utf-8")
    assert wait_until(lambda: "edited on disk"
                      in dw.page.locator("#src").input_value(), page=dw.page)
    assert dw.dialogs == []          # no conflict, no questions


def test_external_asset_add_and_remove(dw, server):
    (server.dir / "img" / "extra.png").write_bytes(PNG)
    expect(dw.page.locator("#assetsList")).to_contain_text("img/extra.png")
    (server.dir / "img" / "extra.png").unlink()
    expect(dw.page.locator("#assetsList")).not_to_contain_text(
        "img/extra.png")
    assert dw.dialogs == []


def test_on_disk_rename_is_adopted(dw, server):
    (server.dir / "talk.md").rename(server.dir / "renamed.md")
    dw.page.wait_for_timeout((POLL_S + 1.0) * 1000)   # let a poll adopt the name
    assert dw.dialogs == []          # a pure external rename asks nothing
    dw.set_source(MD + "\npost-rename edit\n")
    assert wait_until(lambda: (server.dir / "renamed.md").is_file()
                      and "post-rename edit"
                      in (server.dir / "renamed.md").read_text("utf-8"),
                      page=dw.page)
    dw.page.wait_for_timeout((FLUSH_S + 0.5) * 1000)  # a wrong flush would recreate it
    assert not (server.dir / "talk.md").exists()


# ---- conflicts: dirty on both sides --------------------------------------

def _make_both_dirty(dw, server, app_line, disk_line):
    """App edit whose flush is still pending when the disk changes under it:
    the conditional write refuses (412) and the next poll must ask."""
    dw.set_source(MD + app_line)     # returns before the 800 ms flush
    (server.dir / "talk.md").write_text(MD + disk_line, encoding="utf-8")


def test_conflict_app_wins_on_cancel(dw, server):
    dw.answer = False                # dismiss = keep the app version
    _make_both_dirty(dw, server, "\napp says A\n", "\ndisk says B\n")
    assert wait_until(lambda: "app says A" in manuscript(server), page=dw.page)
    assert "app says A" in dw.page.locator("#src").input_value()
    assert len(dw.dialogs) == 1 and "talk.md" in dw.dialogs[0]
    dw.page.wait_for_timeout((POLL_S + 1.0) * 1000)   # settled: no 2nd question
    assert len(dw.dialogs) == 1


def test_conflict_disk_wins_on_ok(dw, server):
    dw.answer = True                 # accept = load the disk version
    _make_both_dirty(dw, server, "\napp says C\n", "\ndisk says D\n")
    assert wait_until(lambda: "disk says D"
                      in dw.page.locator("#src").input_value(), page=dw.page)
    assert "app says C" not in dw.page.locator("#src").input_value()
    dw.page.wait_for_timeout((POLL_S + 1.0) * 1000)   # nothing flushes app text back
    assert "disk says D" in manuscript(server)
    assert "app says C" not in manuscript(server)
    assert len(dw.dialogs) == 1


# ---- access control ------------------------------------------------------

def test_missing_token_alerts_and_falls_back_to_browser_storage(
        browser, server):
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()
    msgs = []
    page.on("dialog", lambda d: (msgs.append(d.message), d.accept()))
    page.goto(server.base + "/")     # deliberately without ?token=
    expect(page.locator("#rail .thumb").first).to_be_visible()
    assert any("token" in m for m in msgs)
    before = manuscript(server)
    page.evaluate("""() => {
        const ta = document.getElementById('src');
        ta.value = 'should never reach disk';
        ta.dispatchEvent(new Event('input'));
    }""")
    page.wait_for_timeout((FLUSH_S + POLL_S) * 1000)  # would have flushed if writable
    assert manuscript(server) == before
    ctx.close()
