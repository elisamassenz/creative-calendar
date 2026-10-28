"""Collect SF events for the next N days from Luma + Meetup into events.json.
Usage: python3 collect.py [days=21] [outfile=events.json]"""
import json, re, sys, time, urllib.request, urllib.parse, hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 21
OUT = sys.argv[2] if len(sys.argv) > 2 else "events.json"
NOW = datetime.now(PT)
START = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
END = START + timedelta(days=DAYS + 1)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

# ---- relevance ----------------------------------------------------------
CATS = {
    "design": r"\bdesign|designer|ux\b|\bui\b|figma|typograph|type ?face|lettering|branding|brand identity|creative ?mornings|aiga|illustrat|packaging|motion graphic|letterform|creative director|art direct|portfolio|visual|font",
    "marketing": r"marketing|marketer|growth|brand(?!ing)|\bcmo\b|content creat|creator|social media|seo\b|advertis|\bads?\b|copywrit|storytell|go-to-market|\bgtm\b|demand gen|community build|pr\b|public relations|influencer|newsletter",
    "art": r"\bart\b|\barts\b|artist|gallery|exhibit|museum|sfmoma|photograph|printmak|zine|poster|mural|film|studio|craft|ceramic|risograph|sketch|drawing|paint",
    "mixer": r"network|mixer|happy hour|founder|entrepreneur|small business|startup|meetup|social|coffee|breakfast|chamber|business owner|women in|women who|female|she |girls in tech|lesbians who tech|womxn|cpg|consumer brand|natural products|naturally bay|dtc|ecommerce|e-commerce|shopify|climate|nonprofit|creative (community|professionals)",
}
EXCLUDE = r"hackathon|hack night|\bllm|gpu|kubernetes|devops|inference|\bsql\b|robot|blockchain|crypto|web3|defi|dating|speed dating|singles|yoga|meditation|run club|book club|salsa|bachata|church|bible|poker|trivia|comedy|stand-up|karaoke|party bus|rave|\bdj\b|techno|clubbing|cannabis|religio|prayer|investor only|real estate investing|forex|trading"
WOMEN = r"women|female|she |girls in tech|womxn|lesbians who tech|ladies|her "

def classify(text):
    t = text.lower()
    if re.search(EXCLUDE, t):
        # keep if strongly design/marketing despite an excluded word
        if not re.search(CATS["design"] + "|" + CATS["marketing"], t.split("\n")[0]):
            return None
    tags = [c for c, rx in CATS.items() if re.search(rx, t)]
    if not tags:
        return None
    if re.search(WOMEN, t):
        tags.append("women")
    return tags

def score(tags, title):
    s = 0
    tl = title.lower()
    if "design" in tags: s += 3
    if "marketing" in tags: s += 2
    if "art" in tags: s += 1
    if "mixer" in tags: s += 1
    if re.search(CATS["design"], tl): s += 3
    if re.search(CATS["marketing"], tl): s += 2
    if re.search(r"network|mixer|happy hour", tl): s += 1
    return s

events = {}

def add(src, title, start, end, venue, city, url, desc, host="", image=""):
    try:
        st = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(PT)
    except Exception:
        return
    if not (START <= st < END):
        return
    text = f"{title}\n{desc}\n{host}"
    tags = classify(text)
    if not tags:
        return
    key = re.sub(r"[^a-z0-9]", "", title.lower())[:40] + st.strftime("%Y%m%d")
    if key in events:
        return
    eid = hashlib.sha1(key.encode()).hexdigest()[:16]
    desc = re.sub(r"[*_#\\\[\]]|\(https?://[^)]*\)", "", desc or "")
    desc = re.sub(r"\s+", " ", desc).strip()
    events[key] = dict(
        id=eid, title=title.strip(), start=st.isoformat(),
        end=(datetime.fromisoformat(end.replace("Z", "+00:00")).astimezone(PT).isoformat() if end else None),
        venue=(venue or "").strip(), city=(city or "San Francisco").strip(), url=url,
        source=src, host=(host or "").strip(), tags=tags, score=score(tags, title),
        summary=desc[:260], image=image or "",
    )

# ---- Luma ---------------------------------------------------------------
LUMA_QUERIES = ["", "design", "designer", "branding", "creative", "marketing", "growth", "brand",
    "founders", "networking", "women", "art", "gallery", "startup", "small business", "consumer", "climate", "mixer"]
LUMA_CATEGORIES = ["cat-AzVAf6VmE9JEre4", "cat-0Km9ZnuBjFAjwFl", "cat-C1VaNLnt25w9t6c"]
BAY = re.compile(r"san francisco|oakland|berkeley|sf\b|emeryville|sausalito", re.I)
def _luma_page(q):
    d = json.loads(get("https://api.lu.ma/discover/get-paginated-events?" + urllib.parse.urlencode(q)))
    return d.get("entries", [])
def _luma_add(e, require_bay=False):
    ev = e["event"]; g = ev.get("geo_address_info") or {}
    city = g.get("city") or ""
    if require_bay and not BAY.search(city + " " + (g.get("city_state") or "")): return
    if ev.get("location_type") == "online": return
    hosts = ", ".join((h.get("name") or "") for h in (e.get("hosts") or [])[:2])
    cal = (e.get("calendar") or {}).get("name", "")
    if cal and cal != "Personal": hosts = cal
    add("Luma", ev["name"], ev["start_at"], ev.get("end_at"),
        g.get("address") or g.get("sublocality") or "", city or "San Francisco",
        "https://luma.com/" + ev["url"], e.get("description_short") or "", hosts, ev.get("cover_url"))
def luma():
    n = 0
    for qq in LUMA_QUERIES:
        q = {"discover_place_api_id": "discplace-BDj7GNbGlsF7Cka", "pagination_limit": 50}
        if qq: q["query"] = qq
        try:
            for e in _luma_page(q): _luma_add(e); n += 1
        except Exception as ex: print("luma fail", qq, ex)
        time.sleep(0.3)
    for c in LUMA_CATEGORIES:
        try:
            for e in _luma_page({"discover_category_api_id": c, "pagination_limit": 50}): _luma_add(e, True); n += 1
        except Exception as ex: print("luma cat fail", c, ex)
    return n

# ---- Meetup -------------------------------------------------------------
MEETUP_KEYWORDS = ["design", "graphic design", "branding", "UX design", "marketing", "growth marketing",
    "creative networking", "women in business", "women entrepreneurs", "small business owners",
    "startup founders networking", "art", "illustration", "photography", "entrepreneurs"]
def meetup():
    n = 0
    s = START.strftime("%Y-%m-%dT00:00:00-07:00"); e = END.strftime("%Y-%m-%dT00:00:00-08:00")
    for kw in MEETUP_KEYWORDS:
        url = ("https://www.meetup.com/find/?" + urllib.parse.urlencode({
            "location": "us--ca--San Francisco", "source": "EVENTS", "keywords": kw,
            "eventType": "inPerson", "distance": "tenMiles",
            "customStartDate": s, "customEndDate": e, "dateRange": "custom"}))
        try:
            h = get(url)
        except Exception as ex:
            print("meetup fail", kw, ex); continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
        if not m: continue
        st = json.loads(m.group(1))["props"]["pageProps"].get("__APOLLO_STATE__", {})
        for k, v in st.items():
            if not k.startswith("Event:"): continue
            grp = st.get((v.get("group") or {}).get("__ref", ""), {})
            venue = st.get((v.get("venue") or {}).get("__ref", ""), {}) if isinstance(v.get("venue"), dict) else {}
            img = ""
            fp = v.get("featuredEventPhoto")
            if isinstance(fp, dict):
                ph = st.get(fp.get("__ref", ""), fp); img = ph.get("highResUrl") or ph.get("baseUrl") or ""
            if v.get("eventType") == "ONLINE": continue
            add("Meetup", v.get("title", ""), v.get("dateTime", ""), v.get("endTime"),
                venue.get("name", ""), venue.get("city", "San Francisco"), v.get("eventUrl", ""),
                v.get("description", ""), grp.get("name", ""), img)
            n += 1
        time.sleep(0.6)
    return n

if __name__ == "__main__":
    for name, fn in [("luma", luma), ("meetup", meetup)]:
        try: print(name, "scanned", fn())
        except Exception as ex: print(name, "FAILED", ex)
    out = sorted(events.values(), key=lambda x: x["start"])
    json.dump({"generated": NOW.isoformat(), "events": out}, open(OUT, "w"), indent=1)
    print("kept", len(out))
