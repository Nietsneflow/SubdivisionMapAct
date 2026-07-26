# Injects subdivision_map_act.json into viewer_template.html -> index.html
import json

with open("subdivision_map_act.json", encoding="utf-8") as f:
    data = json.load(f)

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
payload = payload.replace("</", "<\\/")  # keep the embedded JSON script-safe

with open("viewer_template.html", encoding="utf-8") as f:
    template = f.read()

out = template.replace("__DATA_JSON__", payload)

# Wrap in a full document (the template's <title>/<style> belong in <head>).
head_end = out.index("</style>") + len("</style>")
out = (
    '<!doctype html>\n<html lang="en">\n<head>\n'
    '<meta charset="utf-8"/>\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
    '<meta name="description" content="Searchable full text of the California '
    'Subdivision Map Act (Gov. Code §§ 66410-66499.41)"/>\n'
    + out[:head_end] + "\n</head>\n<body>"
    + out[head_end:] + "\n</body>\n</html>\n"
)
with open("index.html", "w", encoding="utf-8") as f:
    f.write(out)

total = sum(len(a["sections"]) for c in data["chapters"] for a in c["articles"])
print(f"index.html written: {len(out)//1024} KB, {total} sections")
