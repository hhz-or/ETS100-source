import os, re, json, hashlib

CH = r"D:\ets-rea\work\runtime\chunks_full"
stub = open(r"D:\ets-rea\work\runtime\scripts_manifest.json", encoding="utf-8").read()

# 1. collect action calls across all live chunks
act_pat = re.compile(r'sendMessage\([^,]{0,120},\s*"([A-Za-z0-9_]+)"\s*,\s*"([A-Za-z0-9_]+)"')
actions = {}
for f in os.listdir(CH):
    if not f.endswith(".js"):
        continue
    t = open(os.path.join(CH, f), encoding="utf-8", errors="replace").read()
    for m in act_pat.finditer(t):
        actions.setdefault((m.group(1), m.group(2)), set()).add(f)
# also plugin stubs (already separate)
for f in os.listdir(r"D:\ets-rea\work\runtime\scripts"):
    if "plugins_stic" not in f:
        continue
    t = open(os.path.join(r"D:\ets-rea\work\runtime\scripts", f), encoding="utf-8", errors="replace").read()
    for m in act_pat.finditer(t):
        actions.setdefault((m.group(1), m.group(2)), set()).add("stub:" + f)
print("distinct (plugin,action):", len(actions))
plugins = {}
for (p, a) in actions:
    plugins.setdefault(p, []).append(a)
for p in sorted(plugins):
    print(f"  {p:14s} {len(plugins[p]):3d} actions")

# 2. API endpoint-ish strings across chunks
ep = set()
path_pat = re.compile(r'"(/?[a-zA-Z][a-zA-Z0-9_\-]*(?:/[a-zA-Z0-9_\-{}.$]+){1,6})"')
for f in os.listdir(CH):
    if not f.endswith(".js"):
        continue
    t = open(os.path.join(CH, f), encoding="utf-8", errors="replace").read()
    for m in path_pat.finditer(t):
        s = m.group(1)
        if s.startswith("/") and not s.startswith("//") and len(s) < 90:
            ep.add(s)
print("\npath-like strings:", len(ep))

old = {"api_endpoints": set()}
try:
    d = json.load(open(r"D:\ets-rea\work\frontend\api_endpoints.json", encoding="utf-8"))
    if isinstance(d, dict):
        items = d.get("endpoints") or d.get("api_endpoints") or []
    else:
        items = d
    for it in items:
        s = it.get("path") if isinstance(it, dict) else it
        if isinstance(s, str):
            old["api_endpoints"].add(s)
except Exception as e:
    print("old endpoints load err", e)
print("old endpoints:", len(old["api_endpoints"]))
neweps = sorted(ep - old["api_endpoints"])
missing = sorted(old["api_endpoints"] - ep)
print("new vs old (sample):", neweps[:30])
print("old missing in new live set (sample):", missing[:20])

json.dump({"actions": {f"{p}|{a}": sorted(v) for (p, a), v in actions.items()},
           "plugins": {p: sorted(set(v)) for p, v in plugins.items()},
           "path_strings": sorted(ep)},
          open(r"D:\ets-rea\work\runtime\live_analysis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 3. version markers
for f in ["index-e7d07c24.js"]:
    t = open(os.path.join(CH, f), encoding="utf-8", errors="replace").read()
    for pat in [r'"5\.7\.\d+"', r'VITE_APP_VERSION[^,;]{0,40}', r'appVersion[^,;]{0,40}']:
        ms = re.findall(pat, t)
        print(f, pat, ms[:5])
