import json, os

base = r"runtime"
m = json.load(open(os.path.join(base, "scripts_manifest.json"), encoding="utf-8"))
print("scripts:", len(m))
for x in m:
    u = x.get("url", "")
    if "ets100" in u:
        print(f"{x.get('bytes',0):9d}  {u}")

nm = json.load(open(os.path.join(base, "net_manifest.json"), encoding="utf-8"))
print("\nnet bodies:", len(nm))
for x in nm:
    if "api" in x.get("url", "") or x.get("mime", "").find("json") >= 0:
        print(f"{x.get('status','')} {x.get('mime','')[:30]:30s} {x.get('url','')[:150]}")

s = json.load(open(os.path.join(base, "page_state.json"), encoding="utf-8"))
print("\n=== page_state ===")
for k, v in s.items():
    print("---", k, ":", str(v)[:400])
