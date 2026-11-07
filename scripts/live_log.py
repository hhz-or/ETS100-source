import re, json, base64, hashlib, collections

P = r"ETS\logs\ets_2026-11-6.log"
t = open(P, "rb").read().decode("utf-8", "replace")
lines = t.split("\n")
print("lines", len(lines), "bytes", len(t))

req_re = re.compile(r"\[API_ETS\] ets request \$api_name=(\S+) param=(\{.*\})\s*$")
resp_re = re.compile(r"\[API_ETS\] (\d+)ms ets response \$api_name=(\S+) requestId=(\S+) return=(.*?)\s*$")
tags = collections.Counter()
paths = collections.Counter()
protos = collections.Counter()
reqs = []
resps = []
for ln, line in enumerate(lines, 1):
    m = req_re.search(line)
    if m:
        url, raw = m.group(1), m.group(2)
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        reqs.append({"line": ln, "url": url, "body": obj.get("body"), "head": obj.get("head"),
                     "raw": raw})
        paths[re.sub(r"^https?://[^/]+", "", url)] += 1
        continue
    m = resp_re.search(line)
    if m:
        resps.append({"line": ln, "ms": int(m.group(1)), "url": m.group(2), "ret": m.group(4)[:500]})
        continue
    m = re.search(r"received: \[[IE]\] \[([A-Z_]+)\]", line)
    if m:
        tags[m.group(1)] += 1
    m = re.search(r"ets_sign_protocol_selected protocol=(\w+)", line)
    if m:
        protos[m.group(1)] += 1

print("requests", len(reqs), "responses", len(resps))
print("tags", dict(tags))
print("protocols", dict(protos))
print("distinct paths", len(paths))
K1 = "94cfbda3fbfef02b93693f8bc153be82"
ok = bad = 0
for r in reqs:
    if not r["head"] or not r["head"].get("sign"):
        continue
    body_json = json.dumps(r["body"], ensure_ascii=False, separators=(",", ":"))
    b64 = base64.b64encode(body_json.encode()).decode()
    calc = hashlib.md5((r["head"].get("pid", "") + str(r["head"].get("time", "")) + b64 + K1).encode()).hexdigest()
    if calc == r["head"]["sign"]:
        ok += 1
    else:
        bad += 1
print(f"sign verify on live log: {ok} ok / {bad} bad")

json.dump({"requests": reqs, "responses": resps,
           "paths": paths.most_common()}, open(r"runtime\live_requests.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("\n--- new paths (not in previous 51) ---")
prev = set()
try:
    import csv
    for row in csv.DictReader(open(r"data/api\endpoints.csv", encoding="utf-8-sig")):
        prev.add((row.get("path") or "").strip())
except Exception as e:
    print("csv err", e)
for p, c in paths.most_common():
    if p not in prev:
        print(" NEW?", c, p)

print("\n--- sample request ---")
if reqs:
    s = reqs[0]
    print(json.dumps({k: (v[:300] if isinstance(v, str) else v) for k, v in s.items()}, ensure_ascii=False)[:1200])
