import re, json, os, collections

LOGS = [r"ETS\logs\ets_2026-10-28.log", r"ETS\logs\ets_2026-11-4.log"]
OUT = r"data/api"
os.makedirs(OUT, exist_ok=True)

req_re = re.compile(r"\[API_ETS\] ets request \$api_name=(\S+) param=(\{.*\})\s*$")
resp_re = re.compile(r"\[API_ETS\] (\d+)ms ets response \$api_name=(\S+) requestId=(\S+) return=(.*?)\s*$")
proto_re = re.compile(r"\[API_ETS\] ets_sign_protocol_selected protocol=(\w+)")
other_re = re.compile(r"received: \[I\] \[([A-Z_]+)\] (.*)$")

samples = []
responses = []
protos = collections.Counter()
tags = collections.Counter()
ratelog = []

for lp in LOGS:
    day = os.path.basename(lp)
    txt = open(lp, "rb").read().decode("utf-8", "replace")
    for ln, line in enumerate(txt.split("\n"), 1):
        m = req_re.search(line)
        if m:
            url, param = m.group(1), m.group(2)
            try:
                obj = json.loads(param)
            except Exception as e:
                samples.append({"day": day, "line": ln, "url": url, "parse_error": str(e), "raw_param": param})
                continue
            samples.append({
                "day": day, "line": ln, "url": url,
                "body": obj.get("body"), "head": obj.get("head"),
                "param_raw": param,
                "sign": (obj.get("head") or {}).get("sign"),
                "time": (obj.get("head") or {}).get("time"),
            })
            continue
        m = resp_re.search(line)
        if m:
            responses.append({"day": day, "line": ln, "ms": int(m.group(1)), "url": m.group(2),
                              "requestId": m.group(3), "ret": m.group(4)[:2000]})
            continue
        m = proto_re.search(line)
        if m:
            protos[m.group(1)] += 1
            continue
        m = other_re.search(line)
        if m:
            tags[m.group(1)] += 1
            ratelog.append({"day": day, "line": ln, "tag": m.group(1), "msg": m.group(2)[:300]})

json.dump(samples, open(os.path.join(OUT, "ets_requests.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(responses, open(os.path.join(OUT, "ets_responses.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# quick stat
paths = collections.Counter()
for s in samples:
    if "url" in s:
        u = s["url"].split("?")[0]
        # strip scheme+host
        p = re.sub(r"^https?://[^/]+", "", u)
        paths[p] += 1
print("requests:", len(samples), "responses:", len(responses))
print("protocols:", dict(protos))
print("tags:", dict(tags.most_common(20)))
print("distinct paths:", len(paths))
for p, c in paths.most_common(40):
    print(f"  {c:4d} {p}")
