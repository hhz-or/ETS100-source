import os, re, json, hashlib, time
import requests
from concurrent.futures import ThreadPoolExecutor

BASE = "https://statics.ets100.com/ets-student-pc-web/"
ASSETS = BASE + "assets/"
OUT = r"D:\ets-rea\work\runtime\chunks_full"
os.makedirs(OUT, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36"}

sess = requests.Session()
sess.headers.update(HEADERS)

# start from index.html
r = sess.get(BASE + "index.html", timeout=20)
open(os.path.join(OUT, "index.html"), "wb").write(r.content)
print("index.html", r.status_code, len(r.content))

names = set()
pat = re.compile(r"[A-Za-z0-9_\-]+-[0-9a-f]{8}\.js")
text = r.content.decode("utf-8", "replace")
for m in pat.findall(text):
    names.add(m)
print("from index.html:", len(names))

# main bundle
main = None
for m in re.findall(r"assets/([A-Za-z0-9_\-]+-[0-9a-f]{8}\.js)", text):
    if m.startswith("index-"):
        main = m
print("main bundle:", main)
if main:
    rr = sess.get(ASSETS + main, timeout=30)
    data = rr.content
    open(os.path.join(OUT, main), "wb").write(data)
    for x in pat.findall(data.decode("utf-8", "replace")):
        names.add(x)

manifest = {}
for n in sorted(names):
    manifest[n] = {"url": ASSETS + n, "status": None, "size": 0, "sha256": None}

def fetch(n):
    p = os.path.join(OUT, n)
    try:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            data = open(p, "rb").read()
            st = 200
        else:
            r = sess.get(ASSETS + n, timeout=30)
            st = r.status_code
            data = r.content
            if st == 200:
                open(p, "wb").write(data)
        return n, st, len(data), hashlib.sha256(data).hexdigest()
    except Exception as e:
        return n, -1, 0, str(e)[:100]

with ThreadPoolExecutor(max_workers=8) as ex:
    for n, st, sz, sha in ex.map(fetch, list(manifest)):
        manifest[n].update({"status": st, "size": sz, "sha256": sha if st == 200 else None})

# BFS: chunks referenced by chunks
new = set()
for n, info in manifest.items():
    if info["status"] != 200:
        continue
    p = os.path.join(OUT, n)
    try:
        d = open(p, "rb").read().decode("utf-8", "replace")
    except Exception:
        continue
    for x in pat.findall(d):
        if x not in manifest:
            new.add(x)
print("second-wave refs:", len(new))
for n in sorted(new):
    manifest[n] = {"url": ASSETS + n, "status": None, "size": 0, "sha256": None}
with ThreadPoolExecutor(max_workers=8) as ex:
    for n, st, sz, sha in ex.map(fetch, list(new)):
        manifest[n].update({"status": st, "size": sz, "sha256": sha if st == 200 else None})

ok = sum(1 for v in manifest.values() if v["status"] == 200)
print(f"downloaded {ok}/{len(manifest)} chunks, total {sum(v['size'] for v in manifest.values())/1048576:.1f} MB")
json.dump(manifest, open(r"D:\ets-rea\work\runtime\chunks_manifest.json", "w", encoding="utf-8"), indent=1)
bad = {k: v for k, v in manifest.items() if v["status"] != 200}
print("failed:", len(bad), list(bad)[:10])
