# Authoring Deckwright Themes

A theme is a plain `.css` file. No build step, no JSON, no API — if you can
write CSS, you can write a theme.

## The smallest possible theme

```css
/* @theme mint "Mint" */
.slide{
  --s-bg:#f2faf5; --s-surface:#e2f0e8; --s-text:#17241d;
  --s-muted:#5a6f63; --s-accent:#0c8a5f; --s-line:#d2e3d9;
}
```

Save it, click **Load theme…**, done. The header comment is the only required
ceremony: `@theme <id> "<Display Name>"` — the id is what deck front matter
refers to (`theme: mint`), the name is what the Theme button shows.

## How themes work

Deckwright's complete default design (typography, sizes, layouts) lives in the
CSS layer `deck-base`. Your theme is injected into the later layer
`deck-theme`, so **any rule you write beats the default** — no `!important`,
no specificity fights. You can:

- **Recolor** by re-declaring the six `--s-*` tokens (the example above), or
- **Restyle** any element outright — different fonts, sizes, decorations.

The six tokens, which the default design is built from:

| Token         | Used for                                  |
|---------------|-------------------------------------------|
| `--s-bg`      | slide background                          |
| `--s-surface` | code blocks, inline code                  |
| `--s-text`    | headings, strong text, quotes             |
| `--s-muted`   | body text, lists, h4                      |
| `--s-accent`  | links, list markers, kicker, quote rule   |
| `--s-line`    | horizontal rules                          |

Declare them on `.slide`. Note that body text uses `--s-muted`, not
`--s-text` — pick a muted color that's still comfortably readable.

## The DOM you can style (the contract)

Every rendered slide is exactly this, everywhere — editor preview,
thumbnails, presenter view, audience screen, HTML export:

```
.slide                     the slide box (tokens & backgrounds go here)
└─ .stage                  the scaled 1280×720 canvas — geometry, hands off
   └─ .md                  content root; also carries a layout class:
      │                    .lay-default | .lay-cover | .lay-center | .lay-split
      ├─ h1 h2 h3 h4 p ul ol li blockquote pre code a img strong em del hr
      ├─ .kicker           eyebrow-label helper
      └─ split layout only: .band-top / .band-bottom, .cols > .col
```

Keep every selector anchored on `.slide` or `.md`. Slides are always
1280×720 logical pixels — write absolute sizes (`font-size:30px`) and let the
app scale them.

**Off-limits:** the positioning/scaling of `.stage` (guarded by the app).
Everything visual is yours.

## The full CSS platform is available

Themes are real stylesheets, so anything the browser ships works:

```css
/* webfonts — put @import at the top of the file */
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;700&display=swap');

/* decorative chrome that markdown can't express */
.slide::before{
  content:""; position:absolute; top:0; left:0; right:0; height:6px;
  background:var(--s-accent);
}

/* per-layout treatment — same markdown, different stage direction */
.md.lay-cover{ justify-content:flex-end; padding-bottom:120px; }

/* restyle elements, not just recolor them */
.md blockquote{
  border-left:0; border:3px dashed var(--s-accent);
  border-radius:14px; text-align:center;
}
```

Gradients, `@font-face`, `::before`/`::after`, `color-mix()`,
`li::marker`, filters — all fair game.

## Tips

- **Start from a built-in.** Midnight and Paper are token-only themes; the
  bundled `theme_boardroom.css` and `theme_humanist.css` show heavier
  restyling. Copy one and diverge.
- **Check all four layouts** — a cover, a centered slide, a split slide, and
  a dense bullets-and-code slide — plus a slide with a quote and an image.
- **Fallback fonts matter.** Webfonts need a network; give a system stack:
  `"Source Sans 3","Segoe UI",Arial,sans-serif`.
- **Prefer tokens in your own rules** (`var(--s-accent)` over `#0c8a5f`) so a
  later palette tweak is one edit.
- Loaded themes are session-only for now; keep the `.css` file around and
  reload it next session.

## Checklist

1. Header comment: `/* @theme id "Name" */`
2. Six `--s-*` tokens on `.slide`
3. All selectors scoped under `.slide` / `.md`
4. `@import` lines (if any) at the top of the file
5. Eyeballed against cover, center, split, and a dense content slide
