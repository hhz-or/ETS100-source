"""Parse ETS resource download/update events from ets logs; redact PII in work/data JSON outputs."""
import os, re, json, glob

LOG = r"D:\ets-rea\ETS\logs"
OUT = r"D:\ets-rea\work\data\logs"


def dec(b):
    try:
        s = b.decode("utf-8")
        if "\ufffd" not in s:
            return s
    except Exception:
        pass
    return b.decode("gb18030", "replace")


events = []
for name in ["ets_2026-10-28.log", "ets_2026-11-4.log"]:
    s = dec(open(os.path.join(LOG, name), "rb").read())
    for line in s.split("\n"):
        m = re.search(r"^\[([0-9\- :.]+)\] \[(\w+)\] mq_server - received: \[I\] \[PLG_STIC\] (.*)$", line)
        if m:
            ts, lvl, msg = m.groups()
            rec = {"log": name, "time": ts, "msg": msg[:600]}
            # linked JSON payload
            j = re.search(r"(\{.*\})\s*$", msg)
            if j:
                try:
                    rec["payload"] = json.loads(j.group(1))
                except Exception:
                    pass
            events.append(rec)
        else:
            m2 = re.search(r"\[(PLG_STIC|mq_server)\].*(下载|解压|update)", line)
            if m2:
                events.append({"log": name, "raw": line.strip()[:400]})
# dedupe raw fallback
seen = set(); ev = []
for e in events:
    k = json.dumps(e, sort_keys=True, ensure_ascii=False)
    if k not in seen:
        seen.add(k); ev.append(e)
json.dump(ev, open(os.path.join(OUT, "resources_downloads.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# summary table: local_file -> url,size,status
table = {}
for e in ev:
    p = e.get("payload")
    if not p:
        continue
    lf = p.get("local_file")
    if lf:
        t = table.setdefault(lf, {"local_file": lf, "url": p.get("url"), "size": p.get("size"),
                                  "events": []})
        t["events"].append({"time": e["time"], "msg": e["msg"].split("{")[0].strip()})
        if p.get("url"):
            t["url"] = p.get("url")
        if p.get("size"):
            t["size"] = p["size"]
# fill statuses
for e in ev:
    p = e.get("payload")
    if p and p.get("local_file") in table:
        table[p["local_file"]]["status"] = e["msg"].split("：")[0].split(" ")[-1][:30]
json.dump(sorted(table.values(), key=lambda x: x["local_file"]),
          open(os.path.join(OUT, "resources_download_table.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("events:", len(ev), "files:", len(table))
for t in sorted(table.values(), key=lambda x: x["local_file"]):
    print(t["local_file"], t.get("size"), t.get("url"), t.get("status"))

# ---------- redact PII in produced JSON ----------
ACCT = re.compile(r"\bSHM\d{6,}\b")
PHONE = re.compile(r"\b1[3-9]\d{9}\b")
JWT = re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")
PWD_PARAM = re.compile(r"(pwd=)([^&\s\"'\\]+)", re.I)
TOKEN_PARAM = re.compile(r"((?:token|access_token|encryptKey|securityToken|sign)=)([^&\s\"'\\]+)", re.I)

def red(s):
    s = JWT.sub("eyJ***REDACTED", s)
    s = ACCT.sub("SHM*******", s)
    s = PHONE.sub("1**********", s)
    s = PWD_PARAM.sub(r"\1***", s)
    s = TOKEN_PARAM.sub(r"\1***", s)
    return s

def walk(o):
    if isinstance(o, str):
        return red(o)
    if isinstance(o, list):
        return [walk(x) for x in o]
    if isinstance(o, dict):
        return {k: walk(v) for k, v in o.items()}
    return o

targets = []
for pat in ("work/data/logs/*.json", "work/data/storage/*.json", "work/data/db/*.json"):
    targets += glob.glob(os.path.join(r"D:\ets-rea", pat))
for t in targets:
    try:
        d = json.load(open(t, encoding="utf-8"))
        json.dump(walk(d), open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("redacted", os.path.basename(t))
    except Exception as e:
        print("skip", t, e)
