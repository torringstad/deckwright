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


def test_table_basic(dw):
    html = dw.md_to_html("| A | B |\n| - | - |\n| 1 | 2 |")
    assert html == ("<table><thead><tr><th>A</th><th>B</th></tr></thead>"
                    "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>")


def test_table_optional_outer_pipes(dw):
    html = dw.md_to_html("A | B\n- | -\n1 | 2")
    assert html == ("<table><thead><tr><th>A</th><th>B</th></tr></thead>"
                    "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>")


def test_table_alignment_classes(dw):
    html = dw.md_to_html("| L | C | R |\n| :- | :-: | -: |\n| a | b | c |")
    assert '<th class="align-left">L</th>' in html
    assert '<th class="align-center">C</th>' in html
    assert '<th class="align-right">R</th>' in html
    assert '<td class="align-left">a</td>' in html
    assert '<td class="align-center">b</td>' in html
    assert '<td class="align-right">c</td>' in html


def test_table_ragged_rows_padded_and_truncated(dw):
    html = dw.md_to_html("| A | B |\n| - | - |\n| 1 |\n| 1 | 2 | 3 |")
    assert "<tr><td>1</td><td></td></tr>" in html   # short row padded
    assert "<tr><td>1</td><td>2</td></tr>" in html  # long row truncated


def test_table_cells_run_inline_markdown(dw):
    html = dw.md_to_html("| A |\n| - |\n| **b** `c` |")
    assert "<td><strong>b</strong> <code>c</code></td>" in html


def test_not_a_table_without_delimiter_row(dw):
    html = dw.md_to_html("a | b\nc | d")
    assert "<table" not in html
    assert "<p>a | b\nc | d</p>" == html


def test_table_breaks_paragraph(dw):
    html = dw.md_to_html("intro\n| A | B |\n| - | - |\n| 1 | 2 |")
    assert html.startswith("<p>intro</p><table")


# ---- math ($…$ inline, $$…$$ block) --------------------------------------
# These assert the pure-string-out contract WITHOUT the Temml converter
# present: renderMath() emits an honest placeholder carrying the raw TeX,
# wrapped in .math-src. What matters here is detection, protection ordering,
# escaping and paragraph-breaking — the MathML itself is Temml's concern and
# only materializes once the CDN script has loaded in a live surface.

def test_inline_math_placeholder_and_protection(dw):
    # underscores/carets/asterisks inside math must survive markdown intact
    html = dw.md_inline("mass is $E = mc^2$ ok")
    assert '<span class="math-src">$E = mc^2$</span>' in html
    assert "<em>" not in html and "<sup>" not in html


def test_inline_math_shields_markdown_metachars(dw):
    html = dw.md_inline("$a_i * b_j$")
    # no <em> from the * , no stray formatting from the _
    assert '<span class="math-src">$a_i * b_j$</span>' in html
    assert "<em>" not in html


def test_math_inside_code_stays_literal(dw):
    html = dw.md_inline("`$x$`")
    assert html == "<code>$x$</code>"


def test_escaped_dollar_is_literal(dw):
    html = dw.md_inline("costs \\$5 and \\$6")
    assert "$5 and $6" in html
    assert "math-src" not in html


def test_currency_not_treated_as_math(dw):
    # digit right after the closing $ reads as currency, not a math span
    html = dw.md_inline("from $5 to $10 today")
    assert "math-src" not in html


def test_block_math_one_line(dw):
    html = dw.md_to_html("$$ x = y $$")
    assert '<span class="math-src math-display">$$x = y$$</span>' == html


def test_block_math_multiline(dw):
    html = dw.md_to_html("$$\na + b\n= c\n$$")
    assert '<span class="math-src math-display">$$a + b\n= c$$</span>' == html


def test_block_math_breaks_paragraph_both_sides(dw):
    html = dw.md_to_html("before\n$$x$$\nafter")
    assert html.startswith("<p>before</p>")
    assert html.endswith("<p>after</p>")
    assert "math-display" in html


def test_math_in_fence_is_literal(dw):
    html = dw.md_to_html("```\n$$x$$\n$y$\n```")
    assert "<pre><code>" in html
    assert "math-src" not in html
    assert "$$x$$" in html and "$y$" in html


def test_math_body_is_escaped(dw):
    html = dw.md_inline("$a < b$")
    assert '<span class="math-src">$a &lt; b$</span>' in html
