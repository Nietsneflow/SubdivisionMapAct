# Scrapes California Government Code Title 7, "Planning and Land Use"
# (Divisions 1-3, Sections 65000-66499.58) from leginfo.legislature.ca.gov
# into title7.json.
import datetime
import html as htmllib
import json
import re
import time
import urllib.request

BASE = "https://leginfo.legislature.ca.gov/faces/"
TOC_URL = (BASE + "codes_displayexpandedbranch.xhtml"
           "?tocCode=GOV&division=&title=7.&part=&chapter=&article=")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def para_break(m):
    """Turn an opening <p> tag into a newline plus tabs encoding the
    paragraph's indent depth. leginfo indents nested subdivisions
    ((a) -> (1) -> (A) -> (i)) with margin-left: 1em, 2.5em, 4em, ..."""
    ml = re.search(r"margin-left:\s*([\d.]+)em", m.group(1) or "")
    if not ml:
        return "\n"
    level = max(0, round((float(ml.group(1)) - 1) / 1.5))
    return "\n" + "\t" * level


def table_lines(m):
    """Turn a <table> into pipe-delimited lines, one per row: | a | b |
    (the viewer renders runs of these as a real table)."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if any(cells):
            rows.append("| " + " | ".join(cells) + " |")
    return "\n" + "\n".join(rows) + "\n"


def strip_tags(fragment):
    # Whitespace in the source HTML is line-wrapping, not structure; only
    # <br>/<p> tags (below) become line breaks, and only the tabs injected
    # by para_break carry indent depth.
    fragment = re.sub(r"[\r\n\t]+", " ", fragment)
    fragment = re.sub(r"<table[^>]*>(.*?)</table>", table_lines, fragment,
                      flags=re.S)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"<p([^>]*)>", para_break, fragment)
    fragment = re.sub(r"</p>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    text = htmllib.unescape(fragment)
    text = text.replace("\xa0", " ")
    lines = []
    for ln in text.split("\n"):
        tabs = len(ln) - len(ln.lstrip("\t"))
        core = re.sub(r"[ \t]+", " ", ln).strip()
        if core:
            lines.append("\t" * tabs + core)
    return "\n".join(lines)


def parse_page(page_html):
    """Return (division, chapter, article, [sections]) for one text page.

    Heading tags vary between pages (a DIVISION heading may be h4 or h5,
    depending on nesting), so headings are classified by their text.
    """
    body = page_html[page_html.find('id="manylawsections"'):]

    div_h = chap_h = art_h = None
    for m in re.finditer(r"<h[3-6][^>]*>\s*<b>\s*((?:DIVISION|CHAPTER|ARTICLE)[^<]*)</b>",
                         body):
        heading = htmllib.unescape(m.group(1)).strip()
        if heading.startswith("DIVISION"):
            div_h = heading
        elif heading.startswith("CHAPTER"):
            chap_h = heading
        elif heading.startswith("ARTICLE"):
            art_h = heading

    sections = []
    # Each section starts with an <h6> containing the section-number link.
    blocks = re.split(r'<h6 style="float:left;">', body)[1:]
    for block in blocks:
        num_m = re.search(r">\s*([0-9][0-9a-z.]*)\s*</a>", block)
        if not num_m:
            continue
        num = num_m.group(1).rstrip(".")
        content = block[block.find("</h6>") + 5:]
        # Trim at the start of the next section's containing div if present.
        content = re.split(r'<div align="left"><p>', content)[0]

        hist = ""
        hist_m = re.search(
            r'<p style="margin:0 0 2em 0;font-size:0\.9em;"><i>\(([^<]*)\)</i>',
            content)
        if hist_m:
            hist = htmllib.unescape(hist_m.group(1)).strip()
            content = content[:hist_m.start()]

        text = strip_tags(content)
        sections.append({"num": num, "text": text, "history": hist})
    return div_h, chap_h, art_h, sections


def main():
    toc = fetch(TOC_URL)
    pages = []
    for m in re.finditer(
            r'codes_displayText\.xhtml\?lawCode=GOV&amp;division=([0-9.]*)&amp;'
            r'title=7\.&amp;part=&amp;chapter=([0-9.]*)&amp;article=([0-9.]*)',
            toc):
        triple = (m.group(1), m.group(2), m.group(3))
        if triple[0] and triple not in pages:
            pages.append(triple)
    print(f"{len(pages)} text pages found")

    # ordered: divisions -> chapters -> articles -> sections; a level with no
    # heading on the source page (e.g. Division 3 has no chapters) is kept as
    # a single unnamed child so the shape stays uniform.
    divisions = []
    for division, chapter, article in pages:
        url = (BASE + f"codes_displayText.xhtml?lawCode=GOV"
               f"&division={division}&title=7.&part="
               f"&chapter={chapter}&article={article}")
        page = fetch(url)
        div_h, chap_h, art_h, secs = parse_page(page)
        print(f"division={division} chapter={chapter or '-'} "
              f"article={article or '-'} -> {len(secs)} sections")
        if not secs:
            continue
        if not divisions or divisions[-1]["heading"] != div_h:
            divisions.append({"heading": div_h, "chapters": []})
        chaps = divisions[-1]["chapters"]
        if not chaps or chaps[-1]["heading"] != chap_h:
            chaps.append({"heading": chap_h, "articles": []})
        chaps[-1]["articles"].append({"heading": art_h, "sections": secs})
        time.sleep(0.7)

    all_secs = [s for d in divisions for c in d["chapters"]
                for a in c["articles"] for s in a["sections"]]
    data = {
        "title": "Planning and Land Use",
        "citation": ("California Government Code, Title 7, Divisions 1-3 "
                     f"(Sections {all_secs[0]['num']}-{all_secs[-1]['num']})"),
        "source": TOC_URL,
        "scraped": datetime.date.today().isoformat(),
        "divisions": divisions,
    }
    with open("title7.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"TOTAL: {len(all_secs)} sections -> title7.json")


if __name__ == "__main__":
    main()
