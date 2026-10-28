"""Rule-based curation so the agent only has to choose picks.
Run from the repo root.
  python3 _src/curate.py prep     # _work/events.json + _work/extras.json + feed.json -> _work/draft.json, prints compact list
  python3 _src/curate.py final    # _work/draft.json + _work/picks.json -> feed.json
extras.json: [{"title","start","end","venue","city","url","source","category","summary"}] from hand-checked sites.
picks.json: {"picks": {"<n>": "one-sentence note"}, "drop": [<n>, ...]} using the numbers printed by prep."""
import json, re, sys, os, hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
W = "_work"
NOW = datetime.now(PT)
END = (NOW + timedelta(days=21)).date()
MAX = 100

DROP = re.compile(r"hackathon|hack night|sketch ?walk|photo ?walk|life drawing|drawing class|painting class|"
    r"watercolor|docent|guided tour|highlights tour|\bkids?\b|family|toddler|teen|storytime|yoga|fitness|run club|"
    r"figure drawing|ciso|cyber|security|journal club|bio ?ml|biotech|deep tech|\bspace\b|\bsdr\b|data \+ eng|syntax|"
    r"online|virtual|webinar|zoom|investor[- ]only|\blps?\b|limited partner|speed dating|singles", re.I)
DESIGN = re.compile(r"design|branding|typograph|type ?face|letter|creative ?mornings|aiga|packaging|motion|art direct|illustrat", re.I)
NEAR = re.compile(r"oakland|berkeley|san mateo|emeryville|sausalito", re.I)
SF = re.compile(r"san francisco|^sf$|^$", re.I)
MUSEUMS = {"SFMOMA", "YBCA", "Asian Art Museum", "Museum of Craft and Design", "SF Station", "Letterform Archive"}

def norm(t): return re.sub(r"[^a-z]", "", re.sub(r"\d+", "", t.lower()))[:30]

def category(e):
    tags = e.get("tags", [])
    if e.get("category"): return e["category"]
    if "women" in tags: return "women"
    if e["source"] in MUSEUMS or ("art" in tags and "design" not in tags and "marketing" not in tags): return "art"
    if "design" in tags: return "design"
    if "marketing" in tags: return "marketing"
    return "mixer"

def prep():
    raw = json.load(open(f"{W}/events.json"))["events"]
    extras = json.load(open(f"{W}/extras.json")) if os.path.exists(f"{W}/extras.json") else []
    old = {e["id"]: e for e in json.load(open("feed.json"))["events"]} if os.path.exists("feed.json") else {}
    for x in extras:
        x.setdefault("id", hashlib.sha1((x["title"] + x["start"]).encode()).hexdigest()[:16])
        x.setdefault("score", 4 if x.get("category") != "art" else 3)
        x["extra"] = True
    out, seen = [], set()
    for e in sorted(raw + extras, key=lambda e: -e.get("score", 0)):
        st = datetime.fromisoformat(e["start"])
        if not (NOW.date() <= st.date() <= END): continue
        text = f"{e['title']} {e.get('summary', '')}"
        if DROP.search(text) and not (DESIGN.search(e["title"]) and "hack" not in e["title"].lower()): continue
        city = (e.get("city") or "").strip()
        if not SF.search(city) and not (NEAR.search(city) and e.get("score", 0) >= 5): continue
        key = norm(e["title"]) + st.strftime("%G%V")
        if key in seen: continue
        seen.add(key)
        cat = category(e)
        prev = old.get(e["id"], {})
        out.append(dict(id=e["id"], title=e["title"].strip(), start=e["start"], end=e.get("end"),
            venue=e.get("venue", ""), city=city or "San Francisco", url=e["url"], source=e["source"],
            host=e.get("host", ""), tags=[cat], category=cat, pick=False, note=prev.get("note", ""),
            summary=(e.get("summary") or "")[:260], women=cat == "women", image=e.get("image", ""),
            _keep=e.get("extra", False), _score=e.get("score", 0)))
    out.sort(key=lambda e: (not e["_keep"], -e["_score"]))
    out = sorted(out[:MAX], key=lambda e: e["start"])
    json.dump(out, open(f"{W}/draft.json", "w"))
    print(f"{len(out)} events. n|date|cat|title|host  (* = was a pick last week)")
    for i, e in enumerate(out):
        d = datetime.fromisoformat(e["start"]).strftime("%a %m/%d %-I%p")
        star = "*" if old.get(e["id"], {}).get("pick") else ""
        print(f"{i}|{d}|{e['category']}|{star}{e['title'][:70]}|{e['host'][:30]}")

def final():
    out = json.load(open(f"{W}/draft.json"))
    p = json.load(open(f"{W}/picks.json")); picks = p.get("picks", {})
    for k, note in picks.items():
        e = out[int(k)]; e["pick"] = True; e["note"] = note
    drop = {int(i) for i in p.get("drop", [])}
    out = [e for i, e in enumerate(out) if i not in drop]
    for e in out:
        e.pop("_keep", None); e.pop("_score", None)
        if not e["image"]: e.pop("image")
    feed = {"updated": NOW.isoformat(timespec="seconds"), "windowEnd": END.isoformat(), "events": out}
    json.dump(feed, open("feed.json", "w"), separators=(",", ":"))
    print("feed.json:", len(out), "events,", len(picks), "picks")

{"prep": prep, "final": final}[sys.argv[1]]()
