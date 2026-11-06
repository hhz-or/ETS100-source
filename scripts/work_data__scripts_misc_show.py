import json
d=json.load(open(r"D:\ets-rea\work\data\storage\chromium_misc.json",encoding="utf-8"))
for k,v in d.items():
    if k in ("LocalPrefs.json","Network Persistent State"): continue
    print("="*10,k, json.dumps(v,ensure_ascii=False)[:600])
print("=== LocalPrefs keys:", list(d["LocalPrefs.json"]["content"].keys()))
print("=== NetState servers:", [s["server"] for s in d["Network Persistent State"]["content"]["net"]["http_server_properties"]["servers"]])
# visited links url sample
vl=d["Visited Links"]
print("visited urls:",vl["url_count"],vl["urls"][:15])
