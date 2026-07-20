"""Fixtures: stage the app + test images, serve over localhost HTTP, drive a
real Chromium via Playwright. On any test failure, a full-page screenshot
lands in test-results/ so CSS regressions are diagnosable from artifacts.

App under test: $DECKWRIGHT_HTML, or deckwright.html found next to / above
this directory.

Env knobs: HEADED=1 (watch the browser), SLOWMO=250 (ms per action),
CHROMIUM_PATH=/path/to/chrome (override the Playwright-managed browser).
"""
from __future__ import annotations

import os
import shutil
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from dwtest.app import Deckwright
from dwtest.assets import write_assets

HERE = Path(__file__).parent


def _find_app() -> Path:
    env = os.environ.get("DECKWRIGHT_HTML")
    candidates = [Path(env)] if env else [
        HERE / "deckwright.html",
        HERE.parent / "deckwright.html",
        Path.cwd() / "deckwright.html",
    ]
    for c in candidates:
        if c and c.is_file():
            return c.resolve()
    raise pytest.UsageError(
        "deckwright.html not found — set DECKWRIGHT_HTML or place it next to "
        "the test directory"
    )


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep pytest output clean
        pass


@pytest.fixture(scope="session")
def staging(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("dw-staging")
    shutil.copy(_find_app(), d / "deckwright.html")
    write_assets(d)
    return d


@pytest.fixture(scope="session")
def base_url(staging: Path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = ThreadingHTTPServer(
        ("127.0.0.1", port), partial(_QuietHandler, directory=str(staging))
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        kwargs = {
            "headless": not os.environ.get("HEADED"),
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        if os.environ.get("SLOWMO"):
            kwargs["slow_mo"] = int(os.environ["SLOWMO"])
        if os.environ.get("CHROMIUM_PATH"):
            kwargs["executable_path"] = os.environ["CHROMIUM_PATH"]
        b = p.chromium.launch(**kwargs)
        yield b
        b.close()


@pytest.fixture
def dw(browser, base_url, request) -> Deckwright:
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000},
                              accept_downloads=True)
    page = ctx.new_page()
    app = Deckwright(page, base_url).goto()
    yield app
    ctx.close()


# ---- failure artifacts ---------------------------------------------------
RESULTS = HERE / "test-results"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    app = item.funcargs.get("dw")
    if not app:
        return
    RESULTS.mkdir(exist_ok=True)
    safe = item.nodeid.replace("/", "_").replace("::", "__")
    try:
        for i, pg in enumerate(app.page.context.pages):
            pg.screenshot(path=RESULTS / f"{safe}.{i}.png", full_page=True)
    except Exception:
        pass
