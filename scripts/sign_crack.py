import json, re, hashlib, itertools, collections

SAMPLES = json.load(open(r"D:\ets-rea\work\api\ets_requests.json", encoding="utf-8"))


def md5(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    return hashlib.md5(s).hexdigest()


def split_param(raw):
    # raw = {"body":[...],"head":{...}}
    try:
        i = raw.index('"body":')
        j = raw.index(',"head":')
        body_raw = raw[i + len('"body":'):j]
        head_raw = raw[j + len(',"head":'):]
        if head_raw.endswith("}"):
            head_raw = head_raw
        return body_raw, head_raw
    except ValueError:
        return None, None


def strip_sign(head_raw):
    m = re.search(r'"sign":"[0-9a-fA-F]*",', head_raw)
    if m:
        return head_raw[:m.start()] + head_raw[m.end():]
    return None


samples = []
for s in SAMPLES:
    if not s.get("sign") or "param_raw" not in s:
        continue
    body_raw, head_raw = split_param(s["param_raw"])
    if body_raw is None:
        continue
    head_wo = strip_sign(head_raw)
    if head_wo is None:
        continue
    samples.append({
        "url": s["url"],
        "sign": s["sign"],
        "time": (s.get("head") or {}).get("time"),
        "body_raw": body_raw,
        "head_wo": head_wo,
        "full_wo": '{"body":' + body_raw + ',"head":' + head_wo + '}',
        "param_raw": s["param_raw"],
        "path": re.sub(r"^https?://[^/]+", "", s["url"]),
    })
print("usable samples:", len(samples))

# element variants
def elements(s):
    t = s["time"] or ""
    return {
        "body": s["body_raw"],
        "head": s["head_wo"],
        "full": s["full_wo"],
        "time": t,
        "pid": "pcWin",
        "ver": "1.0",
        "path": s["path"],
        "url": s["url"],
    }

# candidate builders: functions taking sample -> list of (name, string)
cands = []
def add(name, fn):
    cands.append((name, fn))

add("body", lambda s: [("body", s["body_raw"])])
add("head_wo", lambda s: [("head_wo", s["head_wo"])])
add("full_wo", lambda s: [("full_wo", s["full_wo"])])
add("md5(body)", lambda s: [("md5(body)", md5(s["body_raw"]))])
add("md5(full_wo)", lambda s: [("md5(full_wo)", md5(s["full_wo"]))])
# pairs/triples of elements with separators
combos = []
els = ["body", "head", "full", "time", "pid", "ver", "path", "url"]
for r in (2, 3):
    for perm in itertools.permutations(els, r):
        combos.append(perm)
print("combos:", len(combos))

def build_multi(s):
    e = elements(s)
    out = []
    for perm in combos:
        for sep in ("", "&", "|", ":", ""):
            out.append(("+".join(perm) + " sep=" + repr(sep), sep.join(e[k] for k in perm)))
    return out

# try per-sample: find any candidate (single or multi) whose md5 == sign
hit = collections.Counter()
for s in samples:
    target = s["sign"].lower()
    for name, fn in cands:
        for nm, v in fn(s):
            if md5(v) == target:
                hit[(nm, "single")] += 1
    for nm, v in build_multi(s):
        if md5(v) == target:
            hit[(nm, "multi")] += 1
print("hits:", hit.most_common(20))

# also: signature could be md5 of body with time embedded? print first 3 sample canonical strings for manual review
print("=== example ===")
s = samples[0]
print("url", s["url"])
print("sign", s["sign"])
print("body", s["body_raw"][:300])
print("head_wo", s["head_wo"][:300])
