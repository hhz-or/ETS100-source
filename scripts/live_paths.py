import json, re, collections

d = json.load(open(r"D:\ets-rea\work\runtime\live_requests.json", encoding="utf-8"))
reqs = d["requests"]
paths = collections.Counter()
for r in reqs:
    p = re.sub(r"^https?://[^/]+", "", r["url"])
    p = p.split("?")[0]
    paths[p] += 1
print("live session paths:", len(paths))
for p, c in paths.most_common():
    print(f"  {c:2d} {p}")

# old endpoints from endpoints.csv
old = set()
import csv
try:
    for row in csv.DictReader(open(r"D:\ets-rea\work\api\endpoints.csv", encoding="utf-8-sig")):
        old.add((row.get("path") or "").strip())
except Exception as e:
    print("csv err", e)
print("\nold endpoint count:", len(old))
newp = [p for p in paths if p not in old]
print("live paths not in old endpoint list:", len(newp))
for p in sorted(newp):
    print("  NEW", p)

# requests without sign
nosign = [r for r in reqs if not (r.get("head") or {}).get("sign")]
print("\nno-sign requests:", len(nosign))
for r in nosign[:5]:
    print("  ", r["url"][:160])
