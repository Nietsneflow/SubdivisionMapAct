# Planning and Land Use (Gov. Code Title 7) — Searchable Reference

A fast, searchable, single-page mirror of **California Government Code Title 7,
Planning and Land Use** (Divisions 1–3, §§ 65000–66499.58) — the Planning and
Zoning Law, the Subdivision Map Act, and Official Maps — built for day-to-day
lookup work that the official site makes painful.

**Live page:** https://nietsneflow.github.io/SubdivisionMapAct/

## Features

- Instant full-text search — multiple words (AND), `"quoted phrases"`, or type a
  section number (e.g. `66412`) to jump straight to it. Press `/` to focus search.
- Persistent results panel with highlighted snippets; clicking a result scrolls
  the reader to that section with every match marked (Prev/Next navigation).
- Collapsible division/chapter/article table of contents.
- Every section links back to its official page on leginfo.legislature.ca.gov,
  plus a copy-to-clipboard citation button.
- Cross-references in the text are clickable: "Section 66424" jumps in-page;
  references to other California codes and the Constitution open the official
  text. Ambiguous references (federal law, Statutes chapters, Code of
  Regulations) are left unlinked rather than linked wrong.
- Hovering an in-page cross-reference or a TOC entry previews the target
  section in a small popover, so you can decide whether to follow it without
  losing your place.
- The browser's Back button works after every jump — cross-references, TOC
  clicks, and search results all push history entries.
- Automatic staleness banner once a January 1 passes after the retrieval date
  (California amendments generally take effect Jan 1).
- Light/dark theme, mobile layout, print-friendly.

## Updating the text

The Legislature amends this code; regenerate the page from the official source:

```
python scrape.py    # re-pulls all chapter/article pages -> title7.json
python build.py     # injects the JSON into viewer_template.html -> index.html
```

Commit and push; GitHub Pages redeploys automatically.

## Files

| File | Purpose |
| --- | --- |
| `scrape.py` | Scrapes Title 7 from the official Legislative Information site |
| `title7.json` | Extracted text (all sections, with history notes) |
| `viewer_template.html` | The viewer app (search UI, TOC, reader) |
| `build.py` | Embeds the JSON into the template, producing `index.html` |
| `index.html` | The self-contained page served by GitHub Pages |

The text is mirrored verbatim from the official source and is not legal advice;
verify anything load-bearing against the linked official pages.
