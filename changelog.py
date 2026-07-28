# Compares the previous committed title7.json against a freshly scraped one
# and prepends any statute differences to changelog.json (rendered by
# build.py as the changes.html "patch notes" page).
#
# Run after scrape.py and before build.py:
#   python changelog.py                 # old = HEAD:title7.json, new = title7.json
#   python changelog.py old.json new.json   # explicit files (for testing)
import datetime
import difflib
import json
import re
import subprocess
import sys


def flatten(data):
    return {s["num"]: s
            for dv in data["divisions"]
            for c in dv["chapters"]
            for a in c["articles"]
            for s in a["sections"]}


def num_key(num):
    m = re.match(r"[\d.]+", num)
    return (float(m.group().rstrip(".")) if m else 1e12, num)


def first_words(sec, n=14):
    line = sec["text"].split("\n")[0].replace("\t", " ").replace("|", " ")
    words = re.sub(r"\s+", " ", line).strip().split()
    return " ".join(words[:n]) + ("…" if len(words) > n else "")


def bill(history):
    """'Amended by Stats. 2024, Ch. 41, Sec. 41. (SB 164) ...'
    -> 'Stats. 2024, Ch. 41 (SB 164)'"""
    stats = re.search(r"(Stats\. \d{4}(?:, 1st Ex\. Sess\.)?, Ch\. \d+)",
                      history or "")
    measure = re.search(r"\(([A-Z]{2,4} ?\d+)\)", history or "")
    parts = [m.group(1) for m in (stats, measure) if m]
    if len(parts) == 2:
        return f"{parts[0]} ({parts[1]})"
    return parts[0] if parts else ""


def main():
    if len(sys.argv) > 2:
        old = json.load(open(sys.argv[1], encoding="utf-8"))
        new_path = sys.argv[2]
    else:
        r = subprocess.run(["git", "show", "HEAD:title7.json"],
                           capture_output=True, encoding="utf-8")
        if r.returncode != 0:
            print("No committed title7.json to compare against; nothing logged.")
            return
        old = json.loads(r.stdout)
        new_path = "title7.json"
    new = json.load(open(new_path, encoding="utf-8"))

    o, n = flatten(old), flatten(new)
    if len(n) < 0.9 * len(o):
        sys.exit(f"Refusing to log: new scrape has {len(n)} sections vs "
                 f"{len(o)} before - probable scrape failure, not repeals.")

    added = sorted((k for k in n if k not in o), key=num_key)
    removed = sorted((k for k in o if k not in n), key=num_key)
    amended = sorted((k for k in n if k in o and
                      (n[k]["text"] != o[k]["text"] or
                       n[k]["history"] != o[k]["history"])), key=num_key)

    # Pair removals with additions whose text matches closely: those are
    # renumberings/recodifications (e.g. ADU law 65852.2 -> 66310), not
    # a repeal plus an unrelated new law.
    moved = []
    for r_num in list(removed):
        best, best_ratio = None, 0.0
        for a_num in added:
            ratio = difflib.SequenceMatcher(
                None, o[r_num]["text"], n[a_num]["text"]).quick_ratio()
            if ratio > best_ratio:
                best_ratio, best = ratio, a_num
        if best and best_ratio > 0.85 and difflib.SequenceMatcher(
                None, o[r_num]["text"], n[best]["text"]).ratio() > 0.85:
            moved.append((r_num, best))
            removed.remove(r_num)
            added.remove(best)

    if not (added or removed or amended or moved):
        print("No statute changes.")
        return

    parts = [f"{len(lst)} {label}" for lst, label in
             ((amended, "amended"), (added, "added"),
              (removed, "repealed"), (moved, "renumbered")) if lst]
    entry = {
        "date": datetime.date.today().isoformat(),
        "title": "Legislative update — " + ", ".join(parts),
        "amended": [{"num": k, "words": first_words(n[k]),
                     "bill": bill(n[k]["history"])} for k in amended],
        "added": [{"num": k, "words": first_words(n[k]),
                   "bill": bill(n[k]["history"])} for k in added],
        "repealed": [{"num": k, "words": first_words(o[k])} for k in removed],
        "moved": [{"from": f, "to": t, "words": first_words(n[t])}
                  for f, t in moved],
    }

    try:
        log = json.load(open("changelog.json", encoding="utf-8"))
    except FileNotFoundError:
        log = {}
    if "entries" in log:  # migrate pre-split shape
        log = {"statute": log.pop("entries"), "app": log.get("app", [])}
    log.setdefault("statute", [])
    log.setdefault("app", [])
    # Re-running on the same day replaces that day's entry (the diff is
    # always against the last committed data, so it stays complete).
    log["statute"] = [e for e in log["statute"] if e["date"] != entry["date"]]
    log["statute"].insert(0, entry)
    with open("changelog.json", "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print("Logged:", entry["title"])


if __name__ == "__main__":
    main()
