import json, base64, hashlib, itertools, collections, re

SAMPLES = json.load(open(r"D:\ets-rea\work\api\ets_requests.json", encoding="utf-8"))
OUT = r"D:\ets-rea\work\api"


def md5(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    return hashlib.md5(s).hexdigest()


def hmac_md5(key, msg):
    import hmac
    return hmac.new(key.encode() if isinstance(key, str) else key,
                    msg.encode() if isinstance(msg, str) else msg,
                    hashlib.md5).hexdigest()


recs = []
for s in SAMPLES:
    if not s.get("sign") or s.get("body") is None:
        continue
    body_json = json.dumps(s["body"], ensure_ascii=False, separators=(",", ":"))
    b64 = base64.b64encode(body_json.encode("utf-8")).decode("ascii")
    recs.append({
        "day": s["day"], "line": s["line"], "url": s["url"],
        "pid": (s.get("head") or {}).get("pid"),
        "time": str((s.get("head") or {}).get("time")),
        "sign": s["sign"].lower(),
        "body_json": body_json,
        "b64": b64,
    })
print("records:", len(recs))
json.dump(recs[:60], open(OUT + r"\sign_samples_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# --- candidate generators ---
def build_strings(r):
    b64 = r["b64"]
    js = r["body_json"]
    t = r["time"]
    return {
        "b64": b64, "json": js, "time": t,
        "pid": r["pid"] or "pcWin", "v2": "v2", "two": "2",
        "ver": "1.0", "url": r["url"], "path": re.sub(r"^https?://[^/]+", "", r["url"]),
    }

KEYS = ["pcWin", "v2", "2", "ets", "ETS", "iflytek", "stic", "ets100", "E听说",
        "stic@iflytek.com", "ets@iflytek.com", "ets_sign", "etsapi", "key",
        "pc_stic_tools", "5.7.9", "1.0"]

hits = collections.Counter()
names = ["b64", "json", "time", "pid", "v2", "two", "ver", "url", "path"]
perm_cache = []
for r_ in (1, 2, 3):
    perm_cache.extend(itertools.permutations(names, r_))
print("permutations:", len(perm_cache))
seps = ["", "&", "|", ":", "\n", "_"]

for r in recs:
    e = build_strings(r)
    target = r["sign"]
    # single / pair / triple concatenations
    for perm in perm_cache:
        base = [e[k] for k in perm]
        for sep in ([""] if len(base) == 1 else seps):
            v = sep.join(base)
            if md5(v) == target:
                hits["md5(" + "+".join(perm) + " sep=" + repr(sep) + ")"] += 1
            # md5 of md5
            if md5(md5(v)) == target:
                hits["md5(md5(" + "+".join(perm) + "))"] += 1
            # hmac with common keys
            for k in KEYS:
                if hmac_md5(k, v) == target:
                    hits["hmac_md5(" + k + "," + "+".join(perm) + ")"] += 1
                if md5(k + v) == target:
                    hits["md5(" + k + "+" + "+".join(perm) + ")"] += 1
                if md5(v + k) == target:
                    hits["md5(" + "+".join(perm) + "+" + k + ")"] += 1
print("hits:", hits.most_common(10))

# Show one record for manual analysis
print("\nexample:", json.dumps(recs[0], ensure_ascii=False)[:600])
