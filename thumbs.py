"""Make 256px square JPEG thumbnails for every event in feed.json.
Image source: the event's `image` field if set, else the page's og:image.
Writes thumbs/<id>.jpg and prints ids that have no image.
Usage: python3 thumbs.py feed.json [events.json]"""
import json, os, re, subprocess, sys, urllib.request, html
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
feed_path = sys.argv[1]; raw_path = sys.argv[2] if len(sys.argv) > 2 else None
feed = json.load(open(feed_path))
raw = {e["id"]: e.get("image", "") for e in json.load(open(raw_path))["events"]} if raw_path and os.path.exists(raw_path) else {}
os.makedirs("thumbs", exist_ok=True); os.makedirs(".dl", exist_ok=True)
def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    with urllib.request.urlopen(req, timeout=25) as r:
        b = r.read(); return b if binary else b.decode("utf-8", "replace")
def og(url):
    try: h = get(url)
    except Exception: return ""
    m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)', h) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']', h)
    return html.unescape(m.group(1)) if m else ""
missing = []
for e in feed["events"]:
    out = f"thumbs/{e['id']}.jpg"
    if os.path.exists(out): continue
    src = e.get("image") or raw.get(e["id"]) or og(e["url"])
    if not src: missing.append(e["id"]); continue
    if src.startswith("//"): src = "https:" + src
    tmp = f".dl/{e['id']}"
    try: open(tmp, "wb").write(get(src, True))
    except Exception: missing.append(e["id"]); continue
    # center-crop to square, then resample to 256
    try:
        info = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", tmp], capture_output=True, text=True).stdout
        w = int(re.search(r"pixelWidth: (\d+)", info).group(1)); h = int(re.search(r"pixelHeight: (\d+)", info).group(1)); m = min(w, h)
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", "--cropToHeightWidth", str(m), str(m), tmp, "--out", out], capture_output=True, check=True)
        subprocess.run(["sips", "-z", "256", "256", out], capture_output=True, check=True)
    except Exception:
        missing.append(e["id"]); continue
print("thumbs:", len([f for f in os.listdir("thumbs") if f.endswith(".jpg")]), "missing:", len(missing))
for i in missing: print("  no image:", i, next(x["title"] for x in feed["events"] if x["id"] == i)[:60])
