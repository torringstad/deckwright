"""parseDeck / parseSlide — directive routing, ranges, warnings."""
DECK = """---
title: My deck
theme: paper
aspect: "16:9"
---

<!-- layout: center -->
<!-- transition: fade -->
<!-- zoom: 0.9 -->
<!-- bg: #102030 -->
<!-- notes: line one
line two -->
# One
<!-- image: a.png width=50% -->

---

## Two
"""


def test_front_matter_and_slide_directives(dw):
    d = dw.parse_deck(DECK)
    assert d["meta"]["title"] == "My deck"
    assert d["meta"]["theme"] == "paper"
    s = d["slides"][0]
    assert (s["layout"], s["transition"], s["zoom"], s["bg"]) == \
        ("center", "fade", 0.9, "#102030")
    assert s["notes"] == "line one\nline two"


def test_block_directive_survives_into_body(dw):
    s = dw.parse_deck(DECK)["slides"][0]
    assert "<!-- image: a.png width=50% -->" in s["body"]
    assert "layout" not in s["body"]  # slide directives stripped


def test_source_ranges_cover_document(dw):
    d = dw.parse_deck(DECK)
    assert d["slides"][0]["start"] < d["slides"][0]["end"]
    assert d["slides"][1]["end"] == len(DECK)


def test_warnings_unknown_and_bad_options(dw):
    d = dw.parse_deck(
        "# ok\n---\n<!-- imgae: t.png -->\n"
        "<!-- image: b.png width=banana wobble dim=7 -->\n## two")
    w = d["warnings"]
    assert any('slide 2: unknown directive "imgae"' in x for x in w)
    assert any('slide 2: bad image width "banana"' in x for x in w)
    assert any('slide 2: unknown image option "wobble"' in x for x in w)
    assert any('slide 2: bad image dim "7"' in x for x in w)
    assert not any(x.startswith("slide 1") for x in w)


def test_no_warning_for_fenced_or_escaped(dw):
    d = dw.parse_deck("```\n<!-- bogus: x -->\n```\n\\<!-- also: fine -->")
    assert d["warnings"] == []


def test_escaped_slide_directive_not_applied(dw):
    d = dw.parse_deck("\\<!-- layout: center -->\ntext")
    assert d["slides"][0]["layout"] == "default"


def test_image_only_slide_survives_empty_filter(dw):
    d = dw.parse_deck("# a\n---\n<!-- image: only.png -->\n---\n# b")
    assert len(d["slides"]) == 3


def test_empty_deck_fallback_shape(dw):
    d = dw.parse_deck("")
    assert len(d["slides"]) == 1
    assert d["slides"][0]["warnings"] == [] and d["warnings"] == []


def test_split_sections_keep_directives(dw):
    d = dw.parse_deck("<!-- layout: split -->\nL\n<!-- image: l.png bleed -->\n==\nR")
    assert "<!-- image: l.png bleed -->" in d["slides"][0]["body"]
