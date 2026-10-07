# Builds title7.json: California Government Code Title 7, "Planning and
# Land Use" (Divisions 1-3, Sections 65000-66499.58), from the Legislature's
# official bulk data export at downloads.leginfo.legislature.ca.gov.
#
# This used to scrape the leginfo.legislature.ca.gov pages directly; in
# October 2026 leginfo put a Cloudflare bot challenge in front of the site
# that refuses every non-browser client. The export ("pubinfo") is the
# Legislature's sanctioned route for machine access: a zip of its database
# tables, rebuilt weekly, holding every code section as CAML (an XML
# dialect) plus the table-of-contents tree. The whole zip is ~1.2 GB, so
# zipfile reads it through HTTP Range requests and pulls only what Title 7
# needs: the zip directory, three law tables, and ~1,080 section files
# (about 15 requests, ~30 MB).
import bisect
import email.utils
import html as htmllib
import http.client
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

EXPORTS = "https://downloads.leginfo.legislature.ca.gov/"
# Human-facing link for the viewer ("official current text"); leginfo's
# pages still work in a browser.
SOURCE = ("https://leginfo.legislature.ca.gov/faces/"
          "codes_displayexpandedbranch.xhtml"
          "?tocCode=GOV&division=&title=7.&part=&chapter=&article=")
UA = {"User-Agent": "SubdivisionMapAct-refresh "
                    "(+https://github.com/Nietsneflow/SubdivisionMapAct)"}

# Column order of the export's tab-delimited .dat files, from the LOAD DATA
# statements in pubinfo_load.zip.
COLUMNS = {
    "LAW_SECTION_TBL": (
        "id law_code section_num op_statues op_chapter op_section "
        "effective_date version_id division title part chapter article "
        "history lob active_flg trans_uid trans_update").split(),
    "LAW_TOC_TBL": (
        "law_code division title part chapter article heading active_flg "
        "trans_uid trans_update node_sequence node_level node_position "
        "node_treepath contains_law_sections history_note op_statues "
        "op_chapter op_section").split(),
    "LAW_TOC_SECTIONS_TBL": (
        "id law_code node_treepath section_num section_order title "
        "op_statues op_chapter op_section trans_uid trans_update "
        "version_id seq_num").split(),
}


def fetch(url, byte_range=None, attempts=7):
    """GET url (optionally one or more byte ranges), retrying transient
    failures: read timeouts, dropped connections, 5xx. Backoff 15s doubling
    to a 4-minute cap rides out roughly 19 minutes of outage per request.
    Returns (headers, body)."""
    headers = dict(UA)
    if byte_range:
        headers["Range"] = "bytes=" + byte_range
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                # A server that ignores Range would start sending all
                # 1.2 GB; stop before reading the body.
                if byte_range and r.status != 206:
                    raise RuntimeError(f"{url}: Range request answered "
                                       f"with HTTP {r.status}, not 206")
                return r.headers, r.read()
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == attempts:
                raise
            err = e
        except (OSError, http.client.HTTPException) as e:
            if attempt == attempts:
                raise
            err = e
        wait = min(15 * 2 ** (attempt - 1), 240)
        print(f"  fetch failed ({err!r}); retry {attempt}/{attempts - 1} "
              f"in {wait}s: {url}", flush=True)
        time.sleep(wait)


class RemoteFile(io.RawIOBase):
    """Seekable, read-only view of a remote file backed by HTTP Range
    requests, so zipfile can open the export without downloading it.
    Reads are served from cached spans; prefetch() fills many small spans
    in a few multi-range requests."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        self.starts, self.blobs = [], []
        headers, _ = fetch(url, "0-0")
        self.size = int(headers["Content-Range"].rsplit("/", 1)[1])
        self.modified = email.utils.parsedate_to_datetime(
            headers["Last-Modified"]).date()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        self.pos = (offset, self.pos + offset, self.size + offset)[whence]
        return self.pos

    def _keep(self, lo, data):
        i = bisect.bisect(self.starts, lo)
        self.starts.insert(i, lo)
        self.blobs.insert(i, data)

    def _cached(self, lo, n):
        i = bisect.bisect(self.starts, lo) - 1
        if i >= 0 and lo + n <= self.starts[i] + len(self.blobs[i]):
            off = lo - self.starts[i]
            return self.blobs[i][off:off + n]
        return None

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        if n <= 0:
            return 0
        data = self._cached(self.pos, n)
        if data is None:
            # zipfile probes headers a few bytes at a time; fetch a little
            # extra so neighbouring probes hit the cache.
            hi = min(self.pos + max(n, 1 << 16), self.size)
            _, blob = fetch(self.url, f"{self.pos}-{hi - 1}")
            self._keep(self.pos, blob)
            data = blob[:n]
        buf[:n] = data
        self.pos += n
        return n

    def prefetch(self, spans, per_request=100):
        # Apache refuses (with the whole file) past MaxRanges, default 200.
        spans = sorted(spans)
        for k in range(0, len(spans), per_request):
            batch = spans[k:k + per_request]
            headers, body = fetch(
                self.url, ",".join(f"{lo}-{hi - 1}" for lo, hi in batch))
            ctype = headers.get("Content-Type", "")
            if not ctype.startswith("multipart/byteranges"):
                lo = int(re.search(r"bytes (\d+)-",
                                   headers["Content-Range"]).group(1))
                self._keep(lo, body)
                continue
            boundary = b"--" + ctype.split("boundary=")[1].strip('"').encode()
            for part in body.split(boundary)[1:-1]:
                head, _, payload = part.partition(b"\r\n\r\n")
                m = re.search(rb"bytes (\d+)-(\d+)/", head, re.I)
                lo, hi = int(m.group(1)), int(m.group(2))
                self._keep(lo, payload[:hi - lo + 1])


def member_span(info):
    # Local header (30 bytes + name + extra field) then the data; 64 bytes
    # of slack covers the extra field, which the central directory doesn't
    # size. An undersized guess just costs one more Range request.
    start = info.header_offset
    return start, start + 30 + len(info.filename) + 64 + info.compress_size


def open_export():
    """The newest session export that carries the code tables."""
    _, index = fetch(EXPORTS)
    years = sorted(set(re.findall(rb'href="pubinfo_(\d{4})\.zip"', index)),
                   reverse=True)
    for year in years[:2]:
        url = f"{EXPORTS}pubinfo_{year.decode()}.zip"
        remote = RemoteFile(url)
        z = zipfile.ZipFile(remote)
        if "LAW_SECTION_TBL.dat" in z.namelist():
            print(f"{url} (exported {remote.modified})")
            return remote, z
        print(f"{url} has no code tables; trying the previous session")
    sys.exit("No pubinfo export with code tables found at " + EXPORTS)


def read_table(z, name, keep):
    """Rows of one .dat file as dicts, filtered by keep(row)."""
    cols = COLUMNS[name]
    rows = []
    for line in z.read(name + ".dat").decode("utf-8").split("\n"):
        if not line:
            continue
        row = dict(zip(cols, (None if c == "NULL" else c.strip("`")
                              for c in line.split("\t"))))
        if keep(row):
            rows.append(row)
    return rows


# --- CAML section text -> the viewer's plain-text encoding ----------------
#
# One line per paragraph; leading tabs give a nested subdivision's indent
# depth; statute tables become pipe-delimited lines ("| a | b |"). The
# rules below reproduce what leginfo's pages render (checked section by
# section against the last HTML scrape: identical except where leginfo
# mis-indented a clause).

ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
         "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix",
         "xx", "xxi", "xxii", "xxiii", "xxiv", "xxv", "xxvi", "xxvii",
         "xxviii", "xxix", "xxx"]
LABEL = re.compile(r"\(([A-Za-z0-9]+)(?:\.\d+)?\)")


def label_depths(lines):
    """Indent depth for each paragraph, from its leading label:
    (a)/(1) -> 0, (A) -> 1, (i) -> 2, (I) -> 3, (ia) -> 4, (Ia) -> 5.

    CAML doesn't record nesting. (i), (v), (x) and their capitals can be
    either the letter after (h), (u), (w) or a roman numeral; the labels
    that follow decide: (ii) means roman, (j) means letter, and so does a
    child a roman clause could not have ((1) or (A) under a lowercase
    label, (i) under a capital)."""
    labels = []
    for ln in lines:
        found, rest = [], ln
        while (m := LABEL.match(rest)):
            found.append(m.group(1))
            rest = rest[m.end():].lstrip()
        labels.append(found)
    last, depths = {}, []
    for k, found in enumerate(labels):
        if not found or found[0].isdigit():
            depths.append(0)
            continue
        lab = found[0]
        low, upper = lab.lower(), lab[0].isupper()
        letter, roman, base = ("U", "R", 1) if upper else ("l", "r", 0)
        if low not in ROMAN and low[:-1] in ROMAN and low[-1].isalpha():
            depths.append(base + 4)        # (ia), (Ia)
            continue
        prev = last.get(letter)
        is_roman = low in ROMAN
        if (is_roman and len(low) == 1 and prev and len(prev) == 1
                and ord(low) == ord(prev) + 1):
            is_roman = roman_by_lookahead(
                lab, upper, found[1:] + [f[0] for f in labels[k + 1:] if f])
        last[roman if is_roman else letter] = low
        depths.append(base + (2 if is_roman else 0))
    return depths


def roman_by_lookahead(lab, upper, after):
    case = str.upper if upper else str.lower
    low = lab.lower()
    next_roman = case(ROMAN[ROMAN.index(low) + 1])
    next_letter = case(chr(ord(low) + 1))
    for nxt in after:
        if nxt == next_roman:
            return True
        if nxt == next_letter:
            return False
        if upper and nxt in ROMAN:
            return False
        if not upper and (nxt.isdigit()
                          or (nxt.isupper() and nxt.lower() not in ROMAN)):
            return False
    return False


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


def section_text(xml):
    # Whitespace in the source is line-wrapping, not structure; only
    # <p>/<br> become line breaks.
    x = re.sub(r"[\r\n\t]+", " ", xml)
    x = x.replace('<span class="EnSpace"/>', " ")
    x = x.replace('<span class="EmSpace"/>', "")
    x = x.replace('<span class="ThinSpace"/>', " ")
    x = x.replace('<span class="SpacedLeaders"/>', " _____ ")   # form blanks
    x = x.replace('<span class="UnderlinedLeaders"/>', "")
    x = x.replace("</caml:Numerator><caml:Denominator>", "/")   # 2/3
    x = re.sub(r"<table[^>]*>(.*?)</table>", table_lines, x, flags=re.S)
    x = re.sub(r"<br\s*/?>|<p[^>]*/>|<p[^>]*>|</p>", "\n", x)
    x = re.sub(r"<[^>]+>", "", x)
    text = htmllib.unescape(x).replace("\xa0", " ")
    lines = [ln for ln in (re.sub(r"[ \t]+", " ", raw).strip()
                           for raw in text.split("\n")) if ln]
    return "\n".join("\t" * depth + ln
                     for depth, ln in zip(label_depths(lines), lines))


def heading(h):
    # "ARTICLE 1. Name [66499.11. - 66499.20.3.]" -> "... [66499.11 - 66499.20.3]"
    return re.sub(r"\.(?=\]| -)", "", h) if h else None


def main():
    remote, z = open_export()
    names = ["LAW_TOC_TBL.dat", "LAW_TOC_SECTIONS_TBL.dat",
             "LAW_SECTION_TBL.dat"]
    remote.prefetch([member_span(z.getinfo(n)) for n in names])

    toc = read_table(z, "LAW_TOC_TBL", lambda r: r["law_code"] == "GOV"
                     and r["title"] == "7." and r["active_flg"] == "Y")
    placed = read_table(z, "LAW_TOC_SECTIONS_TBL",
                        lambda r: r["law_code"] == "GOV")
    law = {r["version_id"]: r for r in read_table(
        z, "LAW_SECTION_TBL", lambda r: r["law_code"] == "GOV"
        and r["title"] == "7." and r["active_flg"] == "Y")}
    remote.prefetch([member_span(z.getinfo(r["lob"])) for r in law.values()])

    heads = {(r["division"], r["chapter"], r["article"]): heading(r["heading"])
             for r in toc}
    by_node = {}
    for p in placed:
        by_node.setdefault(p["node_treepath"], []).append(p)

    # ordered: divisions -> chapters -> articles -> sections; a level with
    # no heading (e.g. Division 3 has no chapters) is kept as a single
    # unnamed child so the shape stays uniform. A section with two
    # versions (conditional amendments) appears twice, as on leginfo.
    divisions = []
    for node in sorted(toc, key=lambda r: int(r["node_sequence"])):
        if node["contains_law_sections"] != "Y":
            continue
        secs = []
        for p in sorted(by_node.get(node["node_treepath"], []),
                        key=lambda p: int(p["section_order"])):
            row = law.get(p["version_id"])
            if row:
                secs.append({
                    "num": row["section_num"].rstrip("."),
                    "text": section_text(z.read(row["lob"]).decode("utf-8")),
                    "history": row["history"] or ""})
        if not secs:
            continue
        div, chap, art = node["division"], node["chapter"], node["article"]
        div_h = heads[(div, None, None)]
        chap_h = heads[(div, chap, None)] if chap else None
        art_h = heads[(div, chap, art)] if art else None
        print(f"division={div} chapter={chap or '-'} "
              f"article={art or '-'} -> {len(secs)} sections")
        if not divisions or divisions[-1]["heading"] != div_h:
            divisions.append({"heading": div_h, "chapters": []})
        chaps = divisions[-1]["chapters"]
        if not chaps or chaps[-1]["heading"] != chap_h:
            chaps.append({"heading": chap_h, "articles": []})
        chaps[-1]["articles"].append({"heading": art_h, "sections": secs})

    all_secs = [s for d in divisions for c in d["chapters"]
                for a in c["articles"] for s in a["sections"]]
    if not all_secs:
        sys.exit("No Title 7 sections found in the export")
    data = {
        "title": "Planning and Land Use",
        "citation": ("California Government Code, Title 7, Divisions 1-3 "
                     f"(Sections {all_secs[0]['num']}-{all_secs[-1]['num']})"),
        "source": SOURCE,
        # The date the Legislature built the export: what the text is
        # current as of.
        "scraped": remote.modified.isoformat(),
        "divisions": divisions,
    }
    with open("title7.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"TOTAL: {len(all_secs)} sections -> title7.json")


if __name__ == "__main__":
    main()
