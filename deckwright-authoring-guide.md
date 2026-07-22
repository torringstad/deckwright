# Deckwright Authoring Guide (for an AI)

You author two things: a **deck** (one Markdown manuscript) and, optionally, a **theme** (one CSS file). This is the complete contract. Follow it exactly — Deckwright's parser is small and literal.

## 1. The mental model

- A **slide is flowing Markdown**, laid out by CSS + a theme + a layout hint. It is *not* absolute-positioned boxes.
- The whole deck is **one Markdown document**. Slides are separated by `---` on its own line.
- Every slide renders onto a fixed **1280×720 logical canvas** (16:9). All sizes below are logical px against that canvas; the canvas is then scaled to fit whatever surface it's shown on.
- Slides have `overflow: hidden`. **Content that doesn't fit is clipped, not scrolled or shrunk.** Keep each slide to one screenful. If it's tight, use `zoom` (§4), a `split` layout, or simply less text.
- A **document** is: one root `.md` manuscript, optional root `.css` theme files, plus assets (images, fonts) in the root or nested folders. Relative paths resolve from the document root, exactly as a web server would.

## 2. Deck skeleton

```markdown
---
title: My Deck
theme: midnight
aspect: "16:9"
---

<!-- layout: cover -->
<!-- notes: Opening slide. -->

# Headline

One-line hook

---

## Second slide

- point one
- point two
```

**Front matter** (optional, must be the very first block, fenced by `---`):

| key | meaning | default |
|---|---|---|
| `title` (or `deck`) | deck title | `Untitled deck` |
| `theme` | theme id to use | `midnight` |
| `aspect` | aspect ratio label | `16:9` |

If `theme` names an unknown id, it silently falls back to `midnight`.

**Slide separator:** a line that is **exactly** `---` (three dashes, nothing else but surrounding whitespace). `----` does *not* separate. Empty slides are dropped.

## 3. Layouts

Set per slide with `<!-- layout: … -->`. Four values:

- **`default`** — top-aligned column. The workhorse: heading + body.
- **`cover`** — vertically centered, oversized headline (h1 ≈ 96px). Title/section slides.
- **`center`** — fully centered, text-aligned center. Great for a single quote or statement.
- **`split`** — two columns, no outer padding. Divide sections with `==` on its own line:
  - 2 parts → `left == right`
  - 3 parts → full-width top band, then `left == right`
  - 4 parts → `top == left == right == bottom` (top/bottom are full-width bands)
  - Lead with `==` to skip the top band. Empty sections collapse.

```markdown
<!-- layout: split -->

## Full-width heading across the top

==

Left column text.

==

Right column text.
```

## 4. Slide directives (metadata — position doesn't matter)

HTML comments, stripped from the visible body. Put them anywhere in the slide (top is conventional).

| directive | notes |
|---|---|
| `<!-- layout: … -->` | see §3 |
| `<!-- bg: #001220 -->` | any CSS color/gradient; overrides the slide background for this slide only |
| `<!-- bg: url(photo.jpg) -->` | image background, sized `cover`, centered; path is document-relative |
| `<!-- transition: fade -->` | per-slide entrance: `fade`, `slideleft`, `slideright`, `slideup`, `slidedown`, `none` (default `none`) |
| `<!-- zoom: 0.9 -->` | typesets content at 90% (buys ~11% more room). `>1` enlarges. Slide box size is unchanged |
| `<!-- notes: … -->` | speaker notes (presenter view only). May span multiple lines until `-->` |

## 5. Images (a *block* directive — renders where it stands)

```markdown
<!-- image: "my chart.png" width=60% right shadow caption="Q3, by region" -->
```

First token is the file or URL — **quote it if it contains spaces**. Then any of:

- **Width:** `width=480` (logical px) or `width=60%`
- **Alignment (in-flow):** `left` · `center` (default) · `right`
- **Fill the frame (behind text):** `cover` or `contain` — fills the whole slide, or the *column* in split layout, at `z-index:-1`. Pair with `dim=0.5` (0–1) to darken for legible overlaid text.
- **`bleed`** — edge-to-edge horizontally but still in the text flow.
- **Frame:** `rounded` (default) · `plain` · `shadow` · `border` · `circle`
- **`caption="…"`** — caption below (inline Markdown allowed). **`alt="…"`** — falls back to caption, then filename.

Inline Markdown images also work: `![alt](path.png)`. Note: inline syntax **can't contain spaces** — spell them `my%20chart.png`, or use the `image:` directive with quotes.

A missing image renders a visible "image not found" placeholder showing the path — useful, not fatal.

## 6. Markdown supported

**Block:** headings `#`–`####`, fenced code ` ``` `, blockquote `>`, unordered/ordered lists (one level of nesting), `---`-style `hr` (use inside a slide — but remember a lone `---` *ends the slide*, so for a rule use it mid-content only where it can't be mistaken for a separator... prefer letting the theme style `hr`), images, and the `image:` directive.
**Inline:** `` `code` ``, `![img](src)`, `[link](url)`, `**bold**`, `*italic*`, `~~strike~~`, line breaks.

**Not supported:** raw HTML (it's escaped and shown literally). The only "HTML" that does anything is the comment directives above.

**Escaping:** to show a directive literally, prefix with a backslash: `\<!-- layout: x -->`. Directive-shaped lines inside fenced code blocks are safe and won't trigger warnings.

**Authoring caution:** an unknown directive name (typo) is dropped and reported as a warning; the deck still renders.

## 7. Themes

A theme is **a plain CSS file** whose first comment is the header:

```css
/* @theme mytheme "My Theme" */
```

`id` is `[\w-]+`; the quoted name is the display label. Add the `.css` to the document (root level) and reference it by id in front matter: `theme: mytheme`. Built-in ids: **`midnight`**, **`paper`**.

### The six tokens (a minimal theme is just these)

Declare them on `.slide`:

```css
/* @theme mytheme "My Theme" */
.slide{
  --s-bg:      #0b1020;  /* slide background            */
  --s-surface: #161d33;  /* code blocks, chips, panels  */
  --s-text:    #e8ecf6;  /* headings, strong text       */
  --s-muted:   #9aa6c2;  /* body copy, captions         */
  --s-accent:  #6ea8fe;  /* links, list markers, rules  */
  --s-line:    #27314f;  /* borders, hr, dividers       */
}
```

Recoloring the whole deck can be *only* this. That's a complete, valid theme.

### Going further

Theme CSS is injected into `@layer deck-theme`, which **outranks** the built-in design (`@layer deck-base`). So you may restyle **any** element — fonts, spacing, `::before`/`::after` chrome, backgrounds, `@keyframes`, gradients, `color-mix()`, whatever the browser ships.

**Two things you cannot override** (guarded with `!important` in the earlier base layer, which wins):
1. The `.stage` scaling geometry — the 1280×720 canvas transform. Leave `.stage` positioning/transform alone.
2. The `.still` freeze — static previews (thumbnails, presenter "next") kill all animation. You don't need to handle this; it just works.

`@import` (e.g. Google Fonts) is allowed and is automatically hoisted above the layer. `@font-face` and `url(...)` in the CSS resolve document-relative, so you can bundle fonts/textures with the deck.

### The DOM contract (what every slide guarantees you can target)

```
.slide                         ← backgrounds + the --s-* tokens live here
  .stage                       ← 1280×720 scaled canvas (do not restyle geometry)
    .md.lay-{default|cover|center|split}   ← content root
      h1 h2 h3 h4 p ul ol li blockquote pre code a img strong em del hr
      .band-top / .band-bottom ← split full-width bands
      .cols > .col             ← split columns
      .fig                     ← image figure; modifiers: align-left/right,
                                 fig-cover/contain/bleed, fig-plain/shadow/
                                 border/circle, has-w, has-dim
```

Base type scale (so your overrides stay proportional to the canvas): h1 64px (96px in cover/center), h2 44px, h3 32px, h4 26px, body/list 30px, blockquote 38px. All relative to 1280×720.

### Theme starting points

```css
/* @theme paper "Paper" */
.slide{
  --s-bg:#f6f4ee; --s-surface:#ece8df; --s-text:#1d2330;
  --s-muted:#5b6577; --s-accent:#c0612f; --s-line:#d8d2c6;
}
```

For a richer look, add on top of the tokens: a display `@font-face`/`@import` for headings, a gradient or textured `.slide` background, or an accent underline on `h2`.

## 8. Deckwright Document Zip (.ddz)

A .ddz is a zip archive with one root .md manuscript, optional root .css
themes, plus assets. If you don't have the capability to create zip files,
create the individual files, along with concise instructions on how to
zip up the .ddz.

## 9. Checklist before you ship a deck

- [ ] Front matter is the first block; `theme:` names a registered id.
- [ ] Every slide fits one screen (headline + a few lines, or a split). No overflow.
- [ ] Slide breaks are bare `---` lines; nothing accidentally splits a slide.
- [ ] Image paths are document-relative and exist; spaces are quoted (directive) or `%20`-encoded (inline).
- [ ] `cover`/`center` for title and statement slides; `default` for content; `split` for comparisons and image-beside-text.
- [ ] Notes added where a presenter would want them.
- [ ] If you shipped a theme: header comment present, six tokens on `.slide`, `.stage` geometry untouched.
