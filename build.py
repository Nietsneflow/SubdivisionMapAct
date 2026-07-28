# Injects title7.json into viewer_template.html -> index.html
import json

with open("title7.json", encoding="utf-8") as f:
    data = json.load(f)

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
payload = payload.replace("</", "<\\/")  # keep the embedded JSON script-safe

# Tombstones: sections that no longer exist, from the change log's moved and
# repealed records (newest entry wins), so searching an old number explains
# what happened to it.
with open("changelog.json", encoding="utf-8") as f:
    log = json.load(f)
gone = {}
for e in log["statute"]:
    for it in e.get("moved", []):
        gone.setdefault(it["from"], {"to": it["to"], "date": e["date"]})
    for it in e.get("repealed", []):
        gone.setdefault(it["num"], {"date": e["date"]})
gone_payload = json.dumps(gone, ensure_ascii=False,
                          separators=(",", ":")).replace("</", "<\\/")

with open("viewer_template.html", encoding="utf-8") as f:
    template = f.read()

out = (template.replace("__DATA_JSON__", payload)
               .replace("__GONE_JSON__", gone_payload))

# Wrap in a full document (the template's <title>/<style> belong in <head>).
head_end = out.index("</style>") + len("</style>")
out = (
    '<!doctype html>\n<html lang="en">\n<head>\n'
    '<meta charset="utf-8"/>\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
    '<meta name="description" content="Searchable full text of California '
    'Government Code Title 7, Planning and Land Use (§§ 65000-66499.58) - '
    'the Planning and Zoning Law, Subdivision Map Act, and Official Maps"/>\n'
    + out[:head_end] + "\n</head>\n<body>"
    + out[head_end:] + "\n</body>\n</html>\n"
)
with open("index.html", "w", encoding="utf-8") as f:
    f.write(out)

total = sum(len(a["sections"]) for d in data["divisions"]
            for c in d["chapters"] for a in c["articles"])
print(f"index.html written: {len(out)//1024} KB, {total} sections")

# Change-log page (Steam-patch-notes style feed of legislative changes).
with open("changelog.json", encoding="utf-8") as f:
    log = json.load(f)
log_payload = json.dumps(log, ensure_ascii=False, separators=(",", ":"))
log_payload = log_payload.replace("</", "<\\/")

with open("changes_template.html", encoding="utf-8") as f:
    changes = f.read()
changes = (changes.replace("__CHANGELOG_JSON__", log_payload)
                  .replace("__SCRAPED__", data["scraped"]))
with open("changes.html", "w", encoding="utf-8") as f:
    f.write(changes)
print(f"changes.html written: {len(log['statute'])} statute entries, "
      f"{len(log['app'])} site entries")
