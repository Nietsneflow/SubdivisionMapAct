# Subdivision Map Act — Searchable Reference

A fast, searchable, single-page mirror of the **California Subdivision Map Act**
(Government Code, Title 7, Division 2, §§ 66410–66499.41), built for day-to-day
lookup work that the official site makes painful.

**Live page:** https://nietsneflow.github.io/SubdivisionMapAct/

## Features

- Instant full-text search — multiple words (AND), `"quoted phrases"`, or type a
  section number (e.g. `66412`) to jump straight to it. Press `/` to focus search.
- Persistent results panel with highlighted snippets; clicking a result scrolls
  the reader to that section with every match marked (Prev/Next navigation).
- Collapsible chapter/article table of contents.
- Every section links back to its official page on leginfo.legislature.ca.gov,
  plus a copy-to-clipboard citation button.
- Automatic staleness banner once a January 1 passes after the retrieval date
  (California amendments generally take effect Jan 1).
- Light/dark theme, mobile layout, print-friendly.

## Updating the text

The Legislature amends this code; regenerate the page from the official source:

```
python scrape.py    # re-pulls all chapter/article pages -> subdivision_map_act.json
python build.py     # injects the JSON into viewer_template.html -> index.html
```

Commit and push; GitHub Pages redeploys automatically.

## Files

| File | Purpose |
| --- | --- |
| `scrape.py` | Scrapes the Act from the official Legislative Information site |
| `subdivision_map_act.json` | Extracted text (280 sections, with history notes) |
| `viewer_template.html` | The viewer app (search UI, TOC, reader) |
| `build.py` | Embeds the JSON into the template, producing `index.html` |
| `index.html` | The self-contained page served by GitHub Pages |

The text is mirrored verbatim from the official source and is not legal advice;
verify anything load-bearing against the linked official pages.
