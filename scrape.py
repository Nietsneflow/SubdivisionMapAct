# Scrapes the California Subdivision Map Act (Gov. Code, Title 7, Division 2)
# from leginfo.legislature.ca.gov into subdivision_map_act.json.
import datetime
import html as htmllib
import json
import re
import time
import urllib.request

BASE = "https://leginfo.legislature.ca.gov/faces/"
TOC_URL = (BASE + "codes_displayexpandedbranch.xhtml"
           "?tocCode=GOV&division=2.&title=7.&part=&chapter=&article=")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_tags(fragment):
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"</p>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    text = htmllib.unescape(fragment)
    text = text.replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def parse_page(page_html):
    """Return (chapter_heading, article_heading, [sections]) for one text page."""
    body = page_html[page_html.find('id="manylawsections"'):]

    chap = None
    m = re.search(r"<h[45][^>]*><b>(CHAPTER[^<]*)</b></h[45]>", body)
    if m:
        chap = htmllib.unescape(m.group(1)).strip()

    art = None
    m = re.search(r"<h5[^>]*><b>(ARTICLE[^<]*)</b></h5>", body)
    if m:
        art = htmllib.unescape(m.group(1)).strip()

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
    return chap, art, sections


def main():
    toc = fetch(TOC_URL)
    urls = []
    for m in re.finditer(
            r'codes_displayText\.xhtml\?lawCode=GOV&amp;division=2\.&amp;'
            r'title=7\.&amp;part=&amp;chapter=([0-9.]*)&amp;article=([0-9.]*)',
            toc):
        pair = (m.group(1), m.group(2))
        if pair not in urls:
            urls.append(pair)
    print(f"{len(urls)} text pages found")

    chapters = []  # ordered: {heading, articles: [{heading, sections}]}
    for chapter, article in urls:
        url = (BASE + f"codes_displayText.xhtml?lawCode=GOV&division=2."
               f"&title=7.&part=&chapter={chapter}&article={article}")
        page = fetch(url)
        chap_h, art_h, secs = parse_page(page)
        print(f"chapter={chapter} article={article or '-'} -> "
              f"{len(secs)} sections  ({chap_h})")
        if not chapters or chapters[-1]["heading"] != chap_h:
            chapters.append({"heading": chap_h, "articles": []})
        chapters[-1]["articles"].append(
            {"heading": art_h, "sections": secs})
        time.sleep(1)

    total = sum(len(a["sections"])
                for c in chapters for a in c["articles"])
    data = {
        "title": "Subdivision Map Act",
        "citation": "California Government Code, Title 7, Division 2 "
                    "(Sections 66410-66499.41)",
        "source": TOC_URL,
        "scraped": datetime.date.today().isoformat(),
        "chapters": chapters,
    }
    with open("subdivision_map_act.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"TOTAL: {total} sections -> subdivision_map_act.json")


if __name__ == "__main__":
    main()
