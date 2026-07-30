# Feature ideas — quality-of-life for daily lookup work

Candidate improvements for the Title 7 reader, aimed at someone who uses the
page as a working tool (Kyle) rather than reading it front to back.

## The constraint

The page is already near its comfortable density: sidebar TOC, topbar search,
results rail, hover tools, scrubber, theme toggle. Anything added must earn its
place. The rule used to sort this list:

> **A feature should cost zero permanent pixels.** It may live on hover, on a
> keystroke, inside an existing container, only when non-empty, or only while
> searching. If it needs a new always-visible control, it probably belongs in a
> separate view — or nowhere.

Tiers below are by value-per-pixel, not by effort.

---

## Tier 1 — high value, invisible until used

### 1. Clickable cross-references ✅ *(shipped)*
The statute is dense with "as defined in Section 66424", "pursuant to Section
65913.4". Today those are dead text; following one means retyping the number.
Linkify them at build time (in `build.py`, or at render in `viewer_template.html`)
so a click jumps to that section.

Cost: zero new UI — existing text just becomes navigable.
Pairs with #2 and #3.

### 2. Real browser Back after a jump ✅ *(shipped — all in-page jumps)*
`jumpToSection`, the TOC handler, and the §-heading handler all use
`history.replaceState` ([viewer_template.html:995](viewer_template.html#L995),
[:1173](viewer_template.html#L1173), [:1217](viewer_template.html#L1217)), so
Back never returns to where you were. Switch to `pushState` and handle
`popstate`. Chasing a cross-reference and getting back is the single most
common lookup motion; today it's a dead end.

Cost: zero UI. Arguably a bug fix more than a feature.

### 3. Hover/tap preview of a referenced section ✅ *(shipped — hover devices)*
Hovering a cross-reference (or a TOC entry, or a search result) shows a small
popover with the section number, heading, and first ~40 words. Answers "do I
actually need to go there?" without losing your place.

Cost: transient popover only.

### 4. Offline / installable (PWA)
Add a manifest + service worker that caches the single page. It then works with
no signal — field visits, basements, county counters — and installs as an app
icon on phone/tablet. The page is already fully self-contained, so this is
mostly configuration.

Cost: zero UI.

### 5. Prev / next section navigation
`[` and `]` (or `j`/`k`) walk sections in statute order; optionally a quiet
"§ 66452.6 →" link in the footer of each section. Reading a run of related
sections currently means scrolling or going back to the TOC.

Cost: keyboard-only, or one faint inline link.

### 6. Pinned sections
A star in the existing hover-only `.sec-tools` row. Pinned sections appear as a
collapsible **Pinned** group at the top of the TOC — *rendered only when
non-empty*, so a first-time visitor sees nothing new. `localStorage`.

Cost: one hover icon + a group that hides itself when unused.

---

## Tier 2 — strong value, small visible footprint

### 7. Recently viewed
Automatic, no interaction required: a **Recent** collapsible group in the
sidebar, last ~10 sections. Same self-hiding pattern as Pinned. Cheap to build
once section-visit tracking exists for #6.

### 8. "Cited by" (reverse cross-references) ✅ *(shipped)*
Built at render time by inverting the resolved in-page cross-reference links,
so forward and reverse can never disagree. Each cited section ends with a
faint *Cited by § …* line; lists longer than ten start collapsed behind a
"+N more" toggle. Bonus shipped with it: searching a section number that no
longer exists (e.g. 65852.2) shows where the law went, fed by the change
log's moved/repealed records.

### 9. Smarter copy
Today "Copy text" copies the whole section. Add, in the same hover row:
- **Copy citation** — `Cal. Gov. Code § 66452.6(a)(1)` alone
- **Copy link** — permalink to `#sec-…`
- Select any passage → a small floating "Copy with citation" button appears,
  so pasted quotes arrive already attributed

Cost: reuses the existing hover tools; the selection button is transient.

### 10. Search scoping
A small segmented control — *All / Planning & Zoning / Map Act / Official Maps* —
that appears **only inside the results rail**, which is already conditional on
searching. Searching "map" across all of Title 7 is noisy when you only care
about Division 2.

### 11. Better query syntax
`search()` is plain substring AND ([viewer_template.html:832](viewer_template.html#L832)).
Worth adding:
- `-word` to exclude
- `OR` between terms
- Relevance ordering as an option (currently statute order only)
- A per-division hit tally in the results header, so term clustering is visible

Cost: none — same input, more power. Extend the existing `/` hint text.

### 12. Search history
Recent queries as a dropdown under the search box on focus, and shareable
search URLs (`?q=lot+line+adjustment`) so a link reopens the search state.

### 13. Reading comfort controls
Text size and measure (line width), tucked behind the existing theme button as
a small popover rather than new topbar buttons. Long statute sessions and older
eyes both benefit; the full-width reader is a lot of text per line on a wide
monitor.

---

## Tier 3 — valuable but needs its own surface

These are genuinely useful but would crowd the reader. They belong behind a
keystroke, a second view, or a dedicated page.

### 14. Definitions on hover
The Map Act defines its own vocabulary (§§ 66410–66424.x): *subdivision*,
*tentative map*, *final map*, *lot line adjustment*, *design*, *improvement*.
Dotted-underline defined terms and show the statutory definition on hover.

High value, high crowding risk — dotted underlines everywhere would make the
page look busy. Mitigation: off by default, enabled by a toggle in the settings
popover, or triggered by double-clicking a word.

### 15. Time-limit calculator
The Map Act is full of deadlines (50 days, 30 days, 24 months, extensions). A
small tool: enter a tentative map approval date, get the expiration and the
governing section. This is the highest-differentiation idea on the list and the
one most certain to wreck the reader if inlined — build it as a separate view
or a `?` -opened panel.

### 16. Amendment awareness
`sec.history` is already in the data. Parse it to:
- badge sections amended recently ("2024")
- filter the TOC to "amended since 2022"

Useful when the question is *what changed*. Needs a filter control, so it lives
in the sidebar's existing tools row.

### 17. Version diff ✅ *(shipped as the change log + auto-refresh)*
A daily GitHub Action (`.github/workflows/refresh.yml`) rescrapes leginfo;
`changelog.py` diffs against the last committed data and classifies each
difference (amended / added / repealed / renumbered, with the enacting bill),
and `changes.html` renders the feed patch-notes style. Remaining idea from
this item: per-section inline text diffs on the change page.

### 18. Private notes per section
A note icon in the hover tools; notes render as a small margin block.
`localStorage` with JSON export/import so years of annotations aren't one
cleared cache away from gone. Natural home for agency-specific implementing
ordinance cross-references.

Crowding risk is real once many notes exist — collapse by default.

### 19. Print packet ✅ *(shipped)*
"+ Packet" in each section's hover tools collects sections; a floating bar
(rendered only while non-empty) prints just those as one clean document with
citations and a cover line. Shipped alongside it, at Kyle's request: clean
whole-title exports built at refresh time — `print.html` (print / save as
PDF), `title7.pdf` (bookmark outline; browser print-to-PDF can't make
bookmarks, so fpdf2 builds it directly), `title7.docx` (real Word file,
navigable headings), and `title7.md` (NotebookLM-ready) — linked from the
intro and the sidebar's "Print & downloads" link.

---

## Tier 4 — polish

- **Keyboard help** — `?` opens a compact shortcut overlay; add `t` (theme),
  `g` (go to section), `n`/`p` (matches) alongside the existing `/`.
- **Command palette** — `Ctrl+K` fuzzy jump over section numbers *and* headings.
  Partially covered by typing a section number into search.
- **Persistent breadcrumb** — the scrubber bubble shows Division/Chapter/Article
  transiently; a slim always-on version could reuse the topbar hint space
  rather than adding a row.
- **Faster first paint** — 2.7 MB of HTML. Render the TOC and visible sections
  first, defer the rest. Matters most on mobile data.
- **Mobile gestures** — swipe left/right to move between sections.
- **Accessibility** — `aria-live` on the result count, audit focus order through
  the slide-over panels.
- **CI link checker** — Title 7-range references that don't exist are already
  left unlinked, but ~1,700 outbound links to *other* codes could still go
  stale when those codes are amended. A CI pass could verify each distinct
  target once (cached in a committed JSON) and unlink the dead ones.

---

## Suggested first slice

1, 2, 3, 5 together are one coherent piece of work — *make the statute
navigable by its own cross-references, and make Back work* — and add no
permanent UI at all. 4 (offline) is independent and nearly free. 6 and 7 are
the natural follow-on once section-visit tracking exists.
