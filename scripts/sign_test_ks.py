import json, base64, hashlib, itertools

KS1 = "94cfbda3fbfef02b93693f8bc153be82"   # selector 1 (v2)
KS0 = "355ffbe95ccf4e9535a110170b445ab8"   # selector 0 (v1)

recs = json.load(open(r"data/api\sign_samples.json", encoding="utf-8"))
print("records:", len(recs))
for r in recs:
    r["b64"] = base64.b64encode(r["body_json_exact"].encode("utf-8")).decode("ascii")


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


prefixes = ["", "pcWin", "202608", "grlx", "body", "response", "etshelper", "ets",
            "5.7.9", "1.0", "test", "sn", "appid", "iflytek", "stic", "ET", "E听说",
            "pc_stic_tools", "key_id", "sign_version", "2"]

# simple formula family: concat(prefix, time, b64body, ks) with ks at end
formulas = []
for p in prefixes:
    formulas.append((f"{p!r}+time+b64+KS1", lambda r, p=p: p + r["time"] + r["b64"] + KS1))
    formulas.append((f"{p!r}+time+b64", lambda r, p=p: p + r["time"] + r["b64"]))
    formulas.append((f"{p!r}+b64+time", lambda r, p=p: p + r["b64"] + r["time"]))
    formulas.append((f"{p!r}+time+json+KS1", lambda r, p=p: p + r["time"] + r["body_json_exact"] + KS1))

# also KS0 variants (v1)
for p in prefixes:
    formulas.append((f"{p!r}+time+b64+KS0", lambda r, p=p: p + r["time"] + r["b64"] + KS0))

hits = {}
for name, fn in formulas:
    ok = 0
    for r in recs[:40]:
        if md5(fn(r)) == r["sign"].lower():
            ok += 1
    if ok:
        hits[name] = ok
print("hits:", hits)

# if no hit, print a couple of candidate digests for manual comparison
r = recs[0]
print("\nexample target:", r["sign"])
print("time", r["time"], "pid", r["pid"])
print("body_json_exact:", r["body_json_exact"][:160])
b64 = base64.b64encode(r["body_json_exact"].encode()).decode()
print("b64:", b64[:80], "len", len(b64))
for label, s in [("time+b64+KS1", r["time"] + b64 + KS1),
                 ("b64+time+KS1", b64 + r["time"] + KS1),
                 ("time+b64", r["time"] + b64),
                 ("b64+time", b64 + r["time"]),
                 ("b64", b64)]:
    print(label, md5(s))
