---
title: Deckwright
theme: midnight
aspect: "16:9"
---

<!-- layout: cover -->
<!-- notes: Concise intro to Deckwright -->

# Deckwright

#### Tor Ringstad (tor.ringstad@gmail.com)
#### https://github.com/torringstad/deckwright/

---

# Principles

Deckwright slideshows are mostly standard markdown. They can be
conveniently edited in any text editor, and are likely to render well in
your favorite markdown tool.

- Slide separator: `---`
- HTML-comment directives: `<!-- variable: value -->`

The rest is details.

---

# Paragraphs

This is a paragraph.

This too. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Proin id
velit elementum, eleifend mauris vitae, cursus mi. Phasellus posuere leo
sit amet metus rhoncus accumsan sed in dolor. Vivamus faucibus, ex vitae
dignissim fringilla,

And this.

---

# Headings

# H1
## H2
### H3
#### H4
##### H5
###### H6

---

# Basic styles

**Bold**

_italic_ or *italic*

~~strikethrough~~

`inline code`

---

# Lists

- Unordered with...
  - ...multiple...
    - ...levels 

1. Ordered...
1. ...with automatic numbering

- Mixed
  1. One
  1. Two

---

# Blockquotes

> Lorem ipsum dolor sit amet, consectetur adipiscing elit. Proin id velit elementum, eleifend mauris vitae, cursus mi. Phasellus posuere.

---

# Fenced code blocks

```c
#include <stdio.h>

int main() {
  printf("Hello, World!\n");
  return 0;
}
```

---

<!-- layout: split -->

# Split column layout

Sections are divided by `==`.
Two sections give left+right columns,
three give an additional top band,
and four also give a bottom band.
This is the **top** section.

==

## Column 1

- This is the **left** section.
- Item
- Item

==

## Column 2

- This is the **right** section.

==

This is the **bottom** section.

---

<!-- zoom: 0.7  -->

# Zoom

The entire slide may be zoomed in/out.
Convenient if you need "just that small bit
of extra space" on a slide.

This slide is at zoom level `0.7`.

---

# External images

![Alt text](deckwright_logo_small.png)

---

<!-- bg: #502020 -->

# Background color

---

<!-- bg: url(background.png) -->

# Background images

---

# Embedded SVG

![bar chart](data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22520%22%20height%3D%22300%22%20viewBox%3D%220%200%20520%20300%22%3E%3Crect%20width%3D%22520%22%20height%3D%22300%22%20fill%3D%22%230e1530%22%2F%3E%3Cline%20x1%3D%2240%22%20y1%3D%22260%22%20x2%3D%22500%22%20y2%3D%22260%22%20stroke%3D%22%232a3a66%22%20stroke-width%3D%222%22%2F%3E%3Crect%20x%3D%2240%22%20y%3D%22184%22%20width%3D%2256%22%20height%3D%2276%22%20rx%3D%226%22%20fill%3D%22%236ea8fe%22%20opacity%3D%220.5%22%2F%3E%3Crect%20x%3D%22130%22%20y%3D%22132%22%20width%3D%2256%22%20height%3D%22128%22%20rx%3D%226%22%20fill%3D%22%236ea8fe%22%20opacity%3D%220.6%22%2F%3E%3Crect%20x%3D%22220%22%20y%3D%22156%22%20width%3D%2256%22%20height%3D%22104%22%20rx%3D%226%22%20fill%3D%22%236ea8fe%22%20opacity%3D%220.7%22%2F%3E%3Crect%20x%3D%22310%22%20y%3D%2284%22%20width%3D%2256%22%20height%3D%22176%22%20rx%3D%226%22%20fill%3D%22%236ea8fe%22%20opacity%3D%220.8%22%2F%3E%3Crect%20x%3D%22400%22%20y%3D%22118%22%20width%3D%2256%22%20height%3D%22142%22%20rx%3D%226%22%20fill%3D%22%236ea8fe%22%20opacity%3D%220.9%22%2F%3E%3C%2Fsvg%3E)

---

<!-- transition: fade  -->

# Slide transitions #1

This slide will crossfade.

---

<!-- transition: slideleft  -->

# Slide transitions #2

This slide will slide left.

---

<!-- transition: slideright  -->

# Slide transitions #3

This slide will slide right.

---

<!-- transition: slidedown  -->

# Slide transitions #4

This slide will slide down.

---

<!-- transition: slideup  -->

# Slide transitions #5

This slide will slide up.

---

# Summary of HTML-comment directives

<!-- notes: This slide has speaker notes.
Notes may span several lines-->

- Speaker notes:  `\<!-- notes: notes goes here -->`
- Layouts: `\<!-- layout: cover|center|split -->`
- Transitions:
  - `\<!-- transition: none  -->`
  - `\<!-- transition: fade  -->`
  - `\<!-- transition: slideleft|slideright|slideup|slidedown -->`
- Zoom:  `\<!-- zoom: 0.7  -->`
- Background: `\<!-- bg: #001220 | url(...) -->`

---

# Front matter directives

- Title: `title: Deckwright`
- Theme: `theme: midnight`
