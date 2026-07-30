# Clean full-text exports of Title 7, built from title7.json:
#   print.html  - statute text only, print stylesheet; browser Print gives
#                 paper or a clean PDF
#   title7.md   - Markdown; drops straight into NotebookLM or a wiki
#   title7.docx - real Word document (stdlib zip, no dependencies); the
#                 navigation pane mirrors division/chapter/article/section
#   title7.pdf  - PDF with a bookmark outline (division/chapter/article/
#                 section); browser print-to-PDF cannot produce bookmarks,
#                 so this is built directly (fpdf2 + the fonts/ DejaVu faces)
# Called from build.py so every refresh keeps the downloads in step with
# the page. Can also run standalone: python export.py
import datetime
import html
import io
import json
import zipfile

from fpdf import FPDF

esc = lambda s: html.escape(s, quote=False)


def walk(data):
    for dv in data["divisions"]:
        yield "div", dv["heading"]
        for ch in dv["chapters"]:
            if ch["heading"]:
                yield "chap", ch["heading"]
            for art in ch["articles"]:
                if art["heading"]:
                    yield "art", art["heading"]
                for sec in art["sections"]:
                    yield "sec", sec


def parse_lines(text):
    """Statute text -> [("table", rows), ("p", depth, line), ...] mirroring
    the viewer's rendering: tab depth is subdivision nesting, '| a | b |'
    lines are table rows."""
    out = []
    lines = text.split("\n")
    is_row = lambda ln: ln.startswith("| ") and ln.endswith(" |")
    i = 0
    while i < len(lines):
        if is_row(lines[i]):
            rows = []
            while i < len(lines) and is_row(lines[i]):
                rows.append([c.strip() for c in lines[i][1:-1].split(" | ")])
                i += 1
            out.append(("table", rows))
            continue
        ln = lines[i]
        depth = len(ln) - len(ln.lstrip("\t"))
        out.append(("p", depth, ln.lstrip("\t")))
        i += 1
    return out


# ---------------------------------------------------------------- print.html
PRINT_CSS = """
  * { box-sizing: border-box; }
  body { margin: 0; background: #fff; color: #000;
         font: 11pt/1.55 Charter, "Bitstream Charter", Cambria, Georgia, serif; }
  main { max-width: 7.5in; margin: 0 auto; padding: 2rem 1.2rem 4rem; }
  h1 { font-size: 1.85rem; line-height: 1.2; margin: 0 0 0.4rem; }
  .meta { color: #444; font-size: 0.85rem; margin: 0.2rem 0; }
  h2 { font-size: 1.4rem; line-height: 1.25; border-top: 3px solid #000;
       padding-top: 1.1rem; margin: 2.6rem 0 0.4rem; }
  h3 { font-size: 1.18rem; line-height: 1.3; border-top: 1px solid #999;
       padding-top: 0.9rem; margin: 2.1rem 0 0.3rem; }
  h4 { font-size: 0.8rem; letter-spacing: 0.09em; text-transform: uppercase;
       color: #333; margin: 1.5rem 0 0.2rem; }
  h5 { font-size: 1rem; margin: 1.1rem 0 0.25rem; }
  p { margin: 0 0 0.5rem; }
  .i1 { margin-left: 1.6em; } .i2 { margin-left: 3.2em; }
  .i3 { margin-left: 4.8em; } .i4 { margin-left: 6.4em; }
  .i5 { margin-left: 8em; }   .i6 { margin-left: 9.6em; }
  .hist { font-size: 0.78rem; color: #555; font-style: italic; margin: 0.3rem 0 0; }
  table { border-collapse: collapse; font-size: 0.9em; margin: 0.3rem 0 0.7rem; }
  td { border: 1px solid #888; padding: 0.2rem 0.6rem; text-align: center; }
  tr:first-child td { font-weight: 700; }
  #toolbar { position: sticky; top: 0; background: #F4F5F3;
             border-bottom: 1px solid #ccc; padding: 0.6rem 1rem;
             font: 14px system-ui, "Segoe UI", sans-serif; display: flex;
             gap: 1rem; align-items: center; flex-wrap: wrap; }
  #toolbar a { color: #2A5F97; }
  #toolbar button { border: 1px solid #2A5F97; background: #2A5F97; color: #fff;
                    border-radius: 6px; padding: 0.35rem 0.8rem; font: inherit;
                    cursor: pointer; }
  #toolbar .tip { color: #666; font-size: 0.82rem; }
  @media print {
    #toolbar { display: none; }
    main { max-width: none; padding: 0; }
    h2 { break-before: page; }
    h5 { break-after: avoid; }
  }
"""


def sec_html(sec):
    out = ['<h5>&sect; ' + esc(sec["num"]) + ".</h5>"]
    for part in parse_lines(sec["text"]):
        if part[0] == "table":
            rows = "".join(
                "<tr>" + "".join("<td>" + esc(c) + "</td>" for c in r) + "</tr>"
                for r in part[1])
            out.append("<table>" + rows + "</table>")
        else:
            _, depth, ln = part
            cls = ' class="i%d"' % min(depth, 6) if depth else ""
            out.append("<p%s>%s</p>" % (cls, esc(ln)))
    out.append('<p class="hist">(' + esc(sec["history"]) + ")</p>")
    return "".join(out)


def print_html(data):
    body = []
    for kind, item in walk(data):
        if kind == "div":
            body.append("<h2>" + esc(item) + "</h2>")
        elif kind == "chap":
            body.append("<h3>" + esc(item) + "</h3>")
        elif kind == "art":
            body.append("<h4>" + esc(item) + "</h4>")
        else:
            body.append(sec_html(item))
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
        '<meta name="robots" content="noindex"/>\n'
        "<title>Planning and Land Use (print version)</title>\n"
        "<style>" + PRINT_CSS + "</style>\n</head>\n<body>\n"
        '<div id="toolbar">\n'
        '<a href="index.html">&larr; Back to the reader</a>\n'
        '<button onclick="window.print()">Print / Save as PDF</button>\n'
        '<a href="title7.pdf" download>PDF with bookmarks</a>\n'
        '<a href="title7.docx" download>Word (.docx)</a>\n'
        '<a href="title7.md" download>Markdown (.md)</a>\n'
        '<span class="tip">Statute text only: no search, sidebar, or links. '
        "Good for printing or for NotebookLM. For just a few sections, use "
        "the packet tools in the reader: hover a section for &ldquo;+ "
        "Packet&rdquo;, or &ldquo;Select for packet&rdquo; in its "
        "sidebar.</span>\n</div>\n<main>\n"
        "<h1>Planning and Land Use</h1>\n"
        '<p class="meta">' + esc(data["citation"]) + "</p>\n"
        '<p class="meta">California Government Code, Title 7: the Planning and '
        "Zoning Law (Division 1), the Subdivision Map Act (Division 2), and "
        "Official Maps (Division 3).</p>\n"
        '<p class="meta">Text retrieved from the official California '
        "Legislative Information site on " + esc(data["scraped"]) + ". "
        "Not an official publication; verify current law at "
        "leginfo.legislature.ca.gov.</p>\n"
        + "".join(body) + "\n</main>\n</body>\n</html>\n")


# ----------------------------------------------------------------- title7.md
def markdown(data):
    out = [
        "# Planning and Land Use",
        "",
        data["citation"],
        "",
        "California Government Code, Title 7: the Planning and Zoning Law "
        "(Division 1), the Subdivision Map Act (Division 2), and Official "
        "Maps (Division 3). Text retrieved from the official California "
        "Legislative Information site on " + data["scraped"] + ".",
        "",
    ]
    for kind, item in walk(data):
        if kind == "div":
            out += ["## " + item, ""]
        elif kind == "chap":
            out += ["### " + item, ""]
        elif kind == "art":
            out += ["#### " + item, ""]
        else:
            out += ["##### § " + item["num"] + ".", ""]
            for part in parse_lines(item["text"]):
                if part[0] == "table":
                    rows = part[1]
                    out.append("| " + " | ".join(rows[0]) + " |")
                    out.append("|" + " --- |" * len(rows[0]))
                    for r in rows[1:]:
                        out.append("| " + " | ".join(r) + " |")
                    out.append("")
                else:
                    # Leading tabs would read as Markdown code blocks; the
                    # (a)(1)(A) markers already carry the nesting.
                    out += [part[2], ""]
            out += ["*(" + item["history"] + ")*", ""]
    return "\n".join(out)


# --------------------------------------------------------------- title7.docx
def x(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def w_para(text, style=None, indent=0, italic=False, bold=False,
           size=None, color=None):
    ppr = ""
    if style:
        ppr += '<w:pStyle w:val="%s"/>' % style
    if indent:
        ppr += '<w:ind w:left="%d"/>' % indent
    rpr = ""
    if italic:
        rpr += "<w:i/>"
    if bold:
        rpr += "<w:b/>"
    if size:
        rpr += '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size)
    if color:
        rpr += '<w:color w:val="%s"/>' % color
    return ("<w:p>" + ("<w:pPr>" + ppr + "</w:pPr>" if ppr else "") +
            "<w:r>" + ("<w:rPr>" + rpr + "</w:rPr>" if rpr else "") +
            '<w:t xml:space="preserve">' + x(text) + "</w:t></w:r></w:p>")


def w_table(rows):
    borders = "".join(
        '<w:%s w:val="single" w:sz="4" w:space="0" w:color="888888"/>' % side
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    out = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>'
           "<w:tblBorders>" + borders + "</w:tblBorders></w:tblPr>"]
    for ri, row in enumerate(rows):
        out.append("<w:tr>")
        for cell in row:
            out.append("<w:tc><w:tcPr/>" +
                       w_para(cell, bold=(ri == 0)) + "</w:tc>")
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Cambria" w:hAnsi="Cambria" w:cs="Cambria"/>
<w:sz w:val="22"/><w:szCs w:val="22"/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
<w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title">
<w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:after="60"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="52"/><w:szCs w:val="52"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="480" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2">
<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="360" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3">
<w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="280" w:after="80"/><w:outlineLvl w:val="2"/></w:pPr>
<w:rPr><w:b/><w:smallCaps/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading4">
<w:name w:val="heading 4"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:spacing w:before="220" w:after="40"/><w:outlineLvl w:val="3"/></w:pPr>
<w:rPr><w:b/></w:rPr></w:style>
</w:styles>
"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>
"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

CORE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Planning and Land Use (Cal. Gov. Code Title 7)</dc:title>
<dc:description>Full text of California Government Code Title 7, retrieved %s from leginfo.legislature.ca.gov</dc:description>
</cp:coreProperties>
"""


def docx_bytes(data):
    body = [
        w_para("Planning and Land Use", style="Title"),
        w_para(data["citation"], italic=True, size=18, color="555555"),
        w_para("California Government Code, Title 7: the Planning and Zoning "
               "Law (Division 1), the Subdivision Map Act (Division 2), and "
               "Official Maps (Division 3).", size=18, color="555555"),
        w_para("Text retrieved from the official California Legislative "
               "Information site on " + data["scraped"] + ". Not an official "
               "publication; verify current law at leginfo.legislature.ca.gov.",
               size=18, color="555555"),
    ]
    for kind, item in walk(data):
        if kind == "div":
            body.append(w_para(item, style="Heading1"))
        elif kind == "chap":
            body.append(w_para(item, style="Heading2"))
        elif kind == "art":
            body.append(w_para(item, style="Heading3"))
        else:
            body.append(w_para("§ " + item["num"] + ".", style="Heading4"))
            for part in parse_lines(item["text"]):
                if part[0] == "table":
                    body.append(w_table(part[1]))
                    # A table must not end flush against the next paragraph
                    body.append(w_para(""))
                else:
                    _, depth, ln = part
                    body.append(w_para(ln, indent=360 * depth))
            body.append(w_para("(" + item["history"] + ")",
                               italic=True, size=18, color="555555"))
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + "".join(body) +
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>")
    buf = io.BytesIO()
    files = [
        ("[Content_Types].xml", CONTENT_TYPES),
        ("_rels/.rels", RELS),
        ("docProps/core.xml", CORE_XML % data["scraped"]),
        ("word/_rels/document.xml.rels", DOC_RELS),
        ("word/document.xml", document),
        ("word/styles.xml", STYLES_XML),
    ]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files:
            # Fixed timestamp keeps rebuilds byte-identical, so a refresh
            # with no statute changes produces no docx diff.
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, content.encode("utf-8"))
    return buf.getvalue()


# ---------------------------------------------------------------- title7.pdf
GRAY = (85, 85, 85)
INK = (0, 0, 0)


class TitlePDF(FPDF):
    def footer(self):
        self.set_y(-40)
        self.set_font("serif", "", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 10, str(self.page_no()), align="C")


def pdf_bytes(data):
    pdf = TitlePDF(orientation="P", unit="pt", format="letter")
    pdf.set_margins(72, 64, 72)
    pdf.set_auto_page_break(True, margin=64)
    for style, fname in (("", "DejaVuSerif.ttf"),
                         ("B", "DejaVuSerif-Bold.ttf"),
                         ("I", "DejaVuSerif-Italic.ttf")):
        pdf.add_font("serif", style=style, fname="fonts/" + fname)
    pdf.set_title("Planning and Land Use (Cal. Gov. Code Title 7)")
    pdf.set_lang("en")
    # Fixed metadata date: rebuilds with unchanged statute text stay
    # byte-identical, so date-only refresh commits carry no pdf churn.
    y, m, d = (int(p) for p in data["scraped"].split("-"))
    pdf.set_creation_date(datetime.datetime(y, m, d,
                                            tzinfo=datetime.timezone.utc))

    def para(text, size, style="", color=INK, indent=0, before=0, lh=1.45):
        if before:
            pdf.ln(before)
        pdf.set_font("serif", style, size)
        pdf.set_text_color(*color)
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(0, size * lh, text, new_x="LMARGIN", new_y="NEXT")

    pdf.add_page()
    para("Planning and Land Use", 26, "B")
    para(data["citation"], 10, "I", GRAY, before=6)
    para("California Government Code, Title 7: the Planning and Zoning Law "
         "(Division 1), the Subdivision Map Act (Division 2), and Official "
         "Maps (Division 3).", 10, "", GRAY, before=4)
    para("Text retrieved from the official California Legislative "
         "Information site on " + data["scraped"] + ". Not an official "
         "publication; verify current law at leginfo.legislature.ca.gov.",
         10, "", GRAY, before=4)

    # Outline levels adapt to missing tiers (Division 3 has no chapters)
    # because a bookmark nested more than one level below its parent would
    # break the outline tree.
    for dv in data["divisions"]:
        pdf.add_page()
        pdf.start_section(dv["heading"], level=0)
        para(dv["heading"], 16, "B", before=6, lh=1.3)
        for ch in dv["chapters"]:
            lvl = 1
            if ch["heading"]:
                pdf.start_section(ch["heading"], level=1)
                para(ch["heading"], 13, "B", before=18, lh=1.3)
                lvl = 2
            for art in ch["articles"]:
                sec_lvl = lvl
                if art["heading"]:
                    pdf.start_section(art["heading"], level=lvl)
                    para(art["heading"], 10.5, "B", GRAY, before=14, lh=1.3)
                    sec_lvl = lvl + 1
                for sec in art["sections"]:
                    pdf.start_section("§ " + sec["num"], level=sec_lvl)
                    para("§ " + sec["num"] + ".", 11, "B", before=10)
                    for part in parse_lines(sec["text"]):
                        if part[0] == "table":
                            pdf.set_font("serif", "", 9)
                            pdf.set_text_color(*INK)
                            with pdf.table(line_height=13,
                                           text_align="CENTER") as tbl:
                                for row in part[1]:
                                    r = tbl.row()
                                    for c in row:
                                        r.cell(c)
                            pdf.ln(4)
                        else:
                            _, depth, ln = part
                            para(ln, 10.5, indent=18 * depth)
                    para("(" + sec["history"] + ")", 8.5, "I", GRAY)
    return bytes(pdf.output())


def build(data):
    with open("print.html", "w", encoding="utf-8") as f:
        f.write(print_html(data))
    md = markdown(data)
    with open("title7.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    docx = docx_bytes(data)
    with open("title7.docx", "wb") as f:
        f.write(docx)
    pdf = pdf_bytes(data)
    with open("title7.pdf", "wb") as f:
        f.write(pdf)
    print("exports written: print.html, title7.md (%d KB), title7.docx "
          "(%d KB), title7.pdf (%d KB)"
          % (len(md) // 1024, len(docx) // 1024, len(pdf) // 1024))


if __name__ == "__main__":
    with open("title7.json", encoding="utf-8") as f:
        build(json.load(f))
