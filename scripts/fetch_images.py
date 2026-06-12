import json, time, urllib.parse, urllib.request, yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "vn.neva.beauty" / "assets" / "img"
IMG.mkdir(parents=True, exist_ok=True)

def access_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("UNSPLASH_ACCESS_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env: UNSPLASH_ACCESS_KEY not found")

KEY = access_key()
imgs = yaml.safe_load((ROOT / "generator" / "data" / "images.yml").read_text())["images"]
credits = []
used_ids = set()  # глобальный дедуп — каждая картинка уникальна

def search(query, orientation):
    url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
        {"query": query, "orientation": orientation, "per_page": 12, "content_filter": "high"})
    req = urllib.request.Request(url, headers={"Authorization": f"Client-ID {KEY}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["results"]

for name, cfg in imgs.items():
    dst = IMG / f"{name}.jpg"
    if dst.exists():
        print("skip", name); continue
    res = search(cfg["query"], cfg["orientation"])
    pick = next((r for r in res if r["id"] not in used_ids), None)
    if pick is None:
        print("NO UNIQUE RESULT", name, cfg["query"]); continue
    used_ids.add(pick["id"])
    w = 900 if cfg["orientation"] == "portrait" else 1200
    raw = pick["urls"]["raw"] + f"&w={w}&q=80&fm=jpg&fit=crop"
    dst.write_bytes(urllib.request.urlopen(raw, timeout=60).read())
    credits.append(f"{name}: {pick['user']['name']} (@{pick['user']['username']}) {pick['links']['html']}")
    print("saved", name)
    time.sleep(1)

if credits:
    p = IMG / "CREDITS.txt"
    prev = p.read_text() if p.exists() else ""
    p.write_text(prev + "\n".join(credits) + "\n")
print("done")
