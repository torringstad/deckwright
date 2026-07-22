#!/usr/bin/env python3
"""
deckserver — serve a Deckwright document directory to the Deckwright app.

    cd my-deck/          # a directory with (at most) one root .md + assets
    deckserver           # prints the URL to open

The directory IS the document: one root manuscript (.md), optionally root
.css themes, plus assets in any subdirectory layout. deckserver serves the
Deckwright application at "/", the document files at their plain paths (so
the directory doubles as an ordinary static site — a static HTML export
dropped here just works), and a small file API under /@deckwright/api/ that
the app uses as its persistence layer instead of browser storage.

Requirements:  Python 3.12+,  pip install bottle waitress
(both pure Python; no compilers were harmed)

Security model, for the self-hosted case this program serves:
  * binds 127.0.0.1 only;
  * every request must carry a loopback Host header (DNS-rebinding guard);
  * the API additionally requires a per-run random token, printed as part
    of the startup URL (Jupyter-style; --no-token disables);
  * before ANY network activity, everything needed from outside the
    document root (the app HTML) is read into memory; the process then
    chdirs into the root and all subsequent filesystem access goes through
    a strict path jail (normalized, symlink-resolved, must stay inside).
    A true chroot needs root privileges and was deliberately not used.

The request handling is one plain WSGI app, so a future CGI mode is just a
different launcher (wsgiref.handlers.CGIHandler) around make_app().
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import socket
import sys
import tempfile
from pathlib import Path

import bottle
from bottle import Bottle, request, response

API_PREFIX = "/@deckwright/api"
DEFAULT_PORT = 8317
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}

# ---------------------------------------------------------------------------
# helpers

def http_error(code: int, message: str):
    """A JSON error the app can read; raises out of the handler."""
    err = bottle.HTTPResponse(
        status=code,
        body=json.dumps({"error": message}),
        content_type="application/json",
    )
    raise err


def mime_of(path: str) -> str:
    if path.lower().endswith((".md", ".markdown")):
        return "text/markdown; charset=utf-8"
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def clean_rel_path(rel: str) -> str:
    """Validate a document-relative path from a request. Rejects anything
    that could step out of the root or address hidden files: absolute paths,
    backslashes, empty/'.'/'..' segments, dot-prefixed segments."""
    if not rel or "\\" in rel or rel.startswith("/"):
        http_error(400, "bad path")
    parts = rel.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        http_error(400, "bad path")
    return "/".join(parts)


def root_md_names(root: Path) -> list[str]:
    return sorted(
        e.name
        for e in os.scandir(root)
        if e.is_file(follow_symlinks=False)
        and not e.name.startswith(".")
        and e.name.lower().endswith((".md", ".markdown"))
    )


# ---------------------------------------------------------------------------
# the WSGI app

def make_app(root: Path, app_html: bytes, token: str | None,
             manuscript_default: str, manuscript_forced: str | None) -> Bottle:
    """root must already be resolved (realpath). app_html is the Deckwright
    application, fully buffered — nothing outside root is touched again."""

    app = Bottle()
    app.config["autojson"] = True

    def jail(rel: str) -> Path:
        """clean_rel_path + symlink-resolved containment check."""
        rel = clean_rel_path(rel)
        p = (root / rel).resolve()
        if p != root and root not in p.parents:
            http_error(400, "path escapes document root")
        return p

    @app.hook("before_request")
    def guard():
        # Host check on EVERY request: a page on evil.example that resolves
        # its own hostname to 127.0.0.1 (DNS rebinding) sends that hostname
        # as Host and is turned away here.
        host = (request.get_header("Host") or "").rsplit(":", 1)[0]
        if host not in LOOPBACK_HOSTS:
            http_error(403, "loopback access only")
        # Token check on the API only; plain paths stay tool-friendly.
        if request.path.startswith(API_PREFIX) and token is not None:
            got = (request.get_header("X-Deckwright-Token")
                   or request.query.get("token") or "")
            if not secrets.compare_digest(got, token):
                http_error(401, "missing or wrong token")
        response.set_header("Cache-Control", "no-store")

    # ---- the application itself ------------------------------------------
    @app.get("/")
    def serve_app():
        response.content_type = "text/html; charset=utf-8"
        return app_html

    # ---- API: manifest ----------------------------------------------------
    def current_manuscript() -> tuple[str, str | None]:
        """(name, problem). Recomputed per request so external renames are
        seen. --file pins the choice and disables the one-.md rule."""
        if manuscript_forced:
            return manuscript_forced, None
        mds = root_md_names(root)
        if len(mds) == 1:
            return mds[0], None
        if not mds:
            return manuscript_default, None      # will be created on flush
        return mds[0], ("more than one root .md (" + ", ".join(mds)
                        + ") — a Deckwright document has exactly one; "
                        "remove the extras or restart deckserver with --file")

    @app.get(API_PREFIX + "/manifest")
    def manifest():
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                p = Path(dirpath) / name
                st = p.stat()
                files.append({
                    "path": p.relative_to(root).as_posix(),
                    "size": st.st_size,
                    # STRING on purpose: st_mtime_ns exceeds JavaScript's
                    # safe-integer range; the app treats it as opaque
                    "mtime": str(st.st_mtime_ns),
                })
        files.sort(key=lambda f: f["path"])
        name, problem = current_manuscript()
        out = {"v": 1, "root": root.name, "manuscript": name, "files": files}
        if problem:
            out["problem"] = problem
        return out

    # ---- API: files -------------------------------------------------------
    @app.get(API_PREFIX + "/file/<rel:path>")
    def get_file(rel):
        p = jail(rel)
        if not p.is_file():
            http_error(404, "no such file")
        response.content_type = mime_of(rel)
        response.set_header("X-Deckwright-Mtime", str(p.stat().st_mtime_ns))
        return p.read_bytes()

    def check_precondition(p: Path):
        """X-Deckwright-If-Mtime carries the mtime_ns the client believes the
        file has ('new' = believes it doesn't exist). A mismatch means the
        file changed under the client since it last looked: 412, don't touch.
        This closes the window between manifest polls in which a flush could
        silently clobber an external edit."""
        cond = request.get_header("X-Deckwright-If-Mtime")
        if cond is None:
            return                       # unconditional (e.g. beacon POST)
        exists = p.is_file()
        if cond == "new":
            if exists:
                http_error(412, "file appeared on disk")
        elif not exists or str(p.stat().st_mtime_ns) != cond:
            http_error(412, "file changed on disk")

    def put_file(rel):
        p = jail(rel)
        if p.is_dir():
            http_error(409, "path is a directory")
        if request.method == "PUT":      # POST = last-gasp beacon, best effort
            check_precondition(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = request.body.read()
        # atomic: never let a crash leave a half-written manuscript
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".deckserver-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, p)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return {"ok": True, "mtime": str(p.stat().st_mtime_ns)}

    app.route(API_PREFIX + "/file/<rel:path>", "PUT", put_file)
    # POST alias: navigator.sendBeacon (the app's last-gasp flush on page
    # close) can only POST and cannot set headers — hence ?token=… there.
    app.route(API_PREFIX + "/file/<rel:path>", "POST", put_file)

    @app.delete(API_PREFIX + "/file/<rel:path>")
    def delete_file(rel):
        p = jail(rel)
        missing = not p.exists()
        if p.is_dir():
            http_error(409, "path is a directory")
        if not missing:
            check_precondition(p)
            p.unlink()
            # the document is its file set; empty dirs are not part of it
            parent = p.parent
            while parent != root:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        return {"ok": True, "missing": missing}

    # ---- plain paths: the directory as a static site ----------------------
    @app.get("/<rel:path>")
    def static(rel):
        p = jail(rel)
        if not p.is_file():
            http_error(404, "no such file")
        response.content_type = mime_of(rel)
        return p.read_bytes()

    return app


# ---------------------------------------------------------------------------
# launcher

def find_port(host: str, wanted: int) -> int:
    """wanted if free, else the next free one in a short range."""
    for port in range(wanted, wanted + 20):
        with socket.socket() as s:
            try:
                s.bind((host, port))
            except OSError:
                continue
            return port
    print(f"deckserver: no free port in {wanted}..{wanted + 19}",
          file=sys.stderr)
    sys.exit(2)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="deckserver",
        description="Serve a Deckwright document directory on localhost.")
    ap.add_argument("root", nargs="?", default=".",
                    help="document root directory (default: current dir)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port to serve on (default {DEFAULT_PORT}; "
                         "if taken, the next free one is used)")
    ap.add_argument("--file", metavar="NAME",
                    help="treat NAME as the manuscript, even if other root "
                         ".md files exist")
    ap.add_argument("--app", metavar="HTML",
                    help="path to deckwright.html (default: next to "
                         "deckserver.py)")
    ap.add_argument("--no-token", action="store_true",
                    help="serve the API without the access token (trusted "
                         "machines only)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"deckserver: {args.root} is not a directory", file=sys.stderr)
        sys.exit(2)

    # -- read everything from OUTSIDE the root, before any network activity
    app_path = Path(args.app) if args.app else Path(__file__).with_name(
        "deckwright.html")
    try:
        app_html = app_path.read_bytes()
    except OSError as e:
        print(f"deckserver: cannot read the app at {app_path}: {e}\n"
              "  (put deckwright.html next to deckserver.py, or use --app)",
              file=sys.stderr)
        sys.exit(2)

    # -- settle the manuscript before serving
    mds = root_md_names(root)
    forced = None
    if args.file:
        forced = clean_rel_path(args.file)
        if "/" in forced or not forced.lower().endswith((".md", ".markdown")):
            print("deckserver: --file must name a root-level .md",
                  file=sys.stderr)
            sys.exit(2)
        default = forced
    elif len(mds) > 1:
        print("deckserver: this directory has more than one root .md:\n"
              + "".join(f"    {m}\n" for m in mds)
              + "  A Deckwright document has exactly one manuscript.\n"
              "  Move the extras away, or pick one with:  deckserver "
              f"--file {mds[0]}", file=sys.stderr)
        sys.exit(2)
    else:
        default = mds[0] if mds else "deck.md"

    # -- from here on, the document root is our world
    os.chdir(root)

    token = None if args.no_token else secrets.token_urlsafe(16)
    app = make_app(root, app_html, token, default, forced)

    host = "127.0.0.1"
    port = find_port(host, args.port)
    url = f"http://{host}:{port}/" + (f"?token={token}" if token else "")

    manuscript = forced or default
    state = "" if (root / manuscript).exists() else "  (will be created)"
    print(f"deckwright document server\n"
          f"  root:        {root}\n"
          f"  manuscript:  {manuscript}{state}\n"
          f"  open:        {url}\n"
          f"stop with Ctrl-C", flush=True)

    import waitress
    try:
        waitress.serve(app, host=host, port=port, threads=8, ident=None)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
