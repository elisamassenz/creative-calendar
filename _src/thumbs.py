"""Make 256px square JPEG thumbs/<id>.jpg for events in feed.json that lack one, then drop stale thumbs
and set imageId="static" on events that have a thumb (the static page only checks it's truthy).
Image source: the event's `image` field, else the page's og:image. Run from the repo root:
  python3 _src/thumbs.py"""
import json, os, re, io, urllib.request, html
from PIL import Image
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
os.makedirs("thumbs", exist_ok=True)
feed = json.load(open("feed.json"))
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    with urllib.request.urlopen(req, timeout=25) as r: return r.read()
def og(url):
    try: h = get(url).decode("utf-8", "replace")
    except Exception: return ""
    m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)', h) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']', h)
    return html.unescape(m.group(1)) if m else ""
made = missing = 0
for e in feed["events"]:
    out = f"thumbs/{e['id']}.jpg"
    if not os.path.exists(out):
        src = e.get("image") or og(e["url"])
        if src.startswith("//"): src = "https:" + src
        try:
            im = Image.open(io.BytesIO(get(src))).convert("RGB")
            m = min(im.size); l, t = (im.width - m) // 2, (im.height - m) // 2
            im.crop((l, t, l + m, t + m)).resize((256, 256), Image.LANCZOS).save(out, "JPEG", quality=78)
            made += 1
        except Exception:
            missing += 1
    e.pop("image", None)
    if os.path.exists(out): e["imageId"] = "static"
    else: e.pop("imageId", None)
keep = {e["id"] + ".jpg" for e in feed["events"]}
for f in os.listdir("thumbs"):
    if f not in keep: os.remove("thumbs/" + f)
json.dump(feed, open("feed.json", "w"), separators=(",", ":"))
print("thumbs: new", made, "missing", missing)
