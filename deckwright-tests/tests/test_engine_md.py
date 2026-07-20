"""Markdown engine — mdToHtml/mdInline called in the app's own realm."""
import pytest


@pytest.mark.parametrize("md,expect", [
    ("# Head", "<h1>Head</h1>"),
    ("## Two words", "<h2>Two words</h2>"),
    ("plain para", "<p>plain para</p>"),
    ("**b** *i* ~~s~~ `c`",
     "<p><strong>b</strong> <em>i</em> <del>s</del> <code>c</code></p>"),
    ("[t](u)", '<p><a href="u">t</a></p>'),
    ("![a](u)", '<p><img src="u" alt="a"></p>'),
    ("> quoted", "<blockquote>quoted</blockquote>"),
    ("***", "<hr>"),
])
def test_basic_blocks(dw, md, expect):
    assert dw.md_to_html(md) == expect


def test_lists_nesting(dw):
    html = dw.md_to_html("- a\n- b\n  - b1\n- c")
    assert html == "<ul><li>a</li><li>b<ul><li>b1</li></ul></li><li>c</li></ul>"


def test_fenced_code_protects_everything(dw):
    html = dw.md_to_html("```\n# not a heading\n<!-- image: x.png -->\n```")
    assert "<pre><code>" in html
    assert "&lt;!-- image: x.png --&gt;" in html
    assert "<h1>" not in html and "<figure" not in html


def test_escaped_comment_is_literal_everywhere(dw):
    assert "&lt;!-- image: x --&gt;" in dw.md_to_html("\\<!-- image: x -->")
    assert "&lt;!-- x --&gt;" in dw.md_inline("mid \\<!-- x --> text")
    # inside a fence the escape is honoured too (parity with historic behavior)
    assert "&lt;!-- layout: center --&gt;" in dw.md_to_html(
        "```\n\\<!-- layout: center -->\n```")
    # …and inline code drops the escaping backslash too, matching every
    # other context (fixed bug: the backslash used to leak through here)
    assert "<code>&lt;!-- x --&gt;</code>" in dw.md_inline("`\\<!-- x -->`")
    assert "\\" not in dw.md_inline("`\\<!-- x -->`")


def test_escaped_directive_backslash_dropped_in_every_inline_context(dw):
    """Regression for a bug where \\<!-- ... --> rendered correctly as a
    literal (non-directive) comment in plain text, bold, and fenced code,
    but inline code (`...`) incorrectly kept the escaping backslash instead
    of stripping it like every other context does."""
    plain = dw.md_inline("plain \\<!-- transition: fade --> text")
    assert "&lt;!-- transition: fade --&gt;" in plain and "\\" not in plain

    bold = dw.md_inline("**\\<!-- transition: fade -->**")
    assert bold == "<strong>&lt;!-- transition: fade --&gt;</strong>"

    code = dw.md_inline("`\\<!-- transition: fade -->`")
    assert code == "<code>&lt;!-- transition: fade --&gt;</code>"


def test_html_is_always_escaped(dw):
    html = dw.md_to_html("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_directive_breaks_paragraph_both_sides(dw):
    html = dw.md_to_html("before\n<!-- image: a.png -->\nafter")
    assert "<p>before</p><figure" in html
    assert "</figure><p>after</p>" in html


def test_unknown_directive_line_dropped(dw):
    html = dw.md_to_html("x\n<!-- bogus: nope -->\ny")
    assert "bogus" not in html
    assert html == "<p>x</p><p>y</p>"
