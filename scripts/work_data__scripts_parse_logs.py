"""Extract URLs, update info and resource download events from ETS logs (GBK decoded)."""
import os, re, json, base64, collections

LOG = r"ETS\logs"
UPD = r"ETS\temp\update\log"
OUT = r"data\logs"
os.makedirs(OUT, exist_ok=True)

def decode(b):
    for enc in ("utf-8", "gb18030"):
        try:
            s = b.decode(enc)
            bad = s.count("\ufffd")
            if enc == "utf-8" and bad > 0:
                continue
            return s, enc
        except Exception:
            continue
    return b.decode("latin1"), "latin1"

URL = re.compile(r"https?://[^\s\"'<>\)\]]+")
all_urls = collections.Counter()
per_file = {}
for name in sorted(os.listdir(LOG)):
    p = os.path.join(LOG, name)
    if not os.path.isfile(p):
        continue
    raw = open(p, "rb").read()
    s, enc = decode(raw)
    urls = URL.findall(s)
    per_file[name] = {"encoding": enc, "bytes": len(raw), "lines": s.count("\n"),
                      "url_count": len(urls),
                      "unique_urls": len(set(urls)),
                      "urls_top": collections.Counter(urls).most_common(30)}
    all_urls.update(urls)
json.dump({"per_file": per_file, "all_urls_top": all_urls.most_common(200)},
          open(os.path.join(OUT, "log_urls.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# resource / download / update event lines
KEY = re.compile(r"(content_\d+|template_\d+|common\.zip|pc_xst_dict|clear_cache|temp[\\/]resources|"
                 r"unzip|download|md5|check_update|client/mobile-update|update_info|rpk|资源|下载|解压)", re.I)
events = []
for name in ["shell_2026-11-4.log", "shell_2026-10-28.log", "ets_2026-11-4.log",
             "ets_2026-10-28.log", "cef_2026-11-4.log", "cef_2026-10-28.log"]:
    p = os.path.join(LOG, name)
    if not os.path.exists(p):
        continue
    s, enc = decode(open(p, "rb").read())
    lines = s.split("\n")
    hits = []
    for i, line in enumerate(lines):
        if KEY.search(line):
            hits.append(line.strip()[:400])
    events.append({"file": name, "encoding": enc, "hit_count": len(hits), "hits": hits[:400]})
json.dump(events, open(os.path.join(OUT, "resource_events.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# update logs: decode base64 request body + collect update links
upd_rows = []
for name in sorted(os.listdir(UPD)):
    p = os.path.join(UPD, name)
    s, enc = decode(open(p, "rb").read())
    rec = {"file": name, "encoding": enc, "lines": []}
    for line in s.split("\n"):
        rec["lines"].append(line.strip()[:500])
        if line.strip().startswith("I") and ("update_info.h" in line or "WndUpdateFrame" in line):
            continue
    # decode base64 bodies
    m = re.search(r'"body":"([A-Za-z0-9+/=]+)"', s)
    if m:
        try:
            dec = base64.b64decode(m.group(1)).decode("utf-8")
            rec["decoded_request_body"] = dec
        except Exception as e:
            rec["decoded_request_body"] = "ERR " + str(e)
    links = re.findall(r"https?://[^\s\"']+", s)
    rec["links"] = links
    # json update response (line with update_info.h:29)
    for line in s.split("\n"):
        if "update_info.h:29" in line:
            i = line.find("[")
            if i >= 0:
                try:
                    rec["update_response"] = json.loads(line[i:].strip())
                except Exception:
                    rec["update_response_raw"] = line.strip()[:1000]
    upd_rows.append(rec)
json.dump(upd_rows, open(os.path.join(OUT, "update_logs.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# summary of interesting hosts
hosts = collections.Counter(re.sub(r"^https?://([^/:]+).*$", r"\1", u) for u in all_urls)
print("hosts:", dict(hosts.most_common(40)))
print("total unique urls:", len(all_urls))
for e in events:
    print(e["file"], e["encoding"], e["hit_count"])
print(json.dumps([{k: v for k, v in r.items() if k in ("file", "decoded_request_body", "links")} for r in upd_rows],
                 ensure_ascii=False, indent=1)[:3000])
