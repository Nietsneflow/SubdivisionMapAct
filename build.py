# Injects subdivision_map_act.json into viewer_template.html -> index.html
import json

with open("subdivision_map_act.json", encoding="utf-8") as f:
    data = json.load(f)

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
payload = payload.replace("</", "<\\/")  # keep the embedded JSON script-safe

with open("viewer_template.html", encoding="utf-8") as f:
    template = f.read()

out = template.replace("__DATA_JSON__", payload)
with open("index.html", "w", encoding="utf-8") as f:
    f.write(out)

total = sum(len(a["sections"]) for c in data["chapters"] for a in c["articles"])
print(f"index.html written: {len(out)//1024} KB, {total} sections")
