import os, re, json

D = r"D:\ets-rea\work\runtime\scripts"
out = []
for f in sorted(os.listdir(D)):
    if "plugins_stic_" not in f and "plugins_clientDB" not in f:
        continue
    p = os.path.join(D, f)
    t = open(p, encoding="utf-8", errors="replace").read()
    cls = re.findall(r"var\s+(\w+)\s*=\s*function", t)
    calls = re.findall(r'sendMessage\([^,]{0,80},\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*([^)]{0,60})\)', t)
    actions = []
    for plugin, action, args in calls:
        args = args.strip()
        if args.startswith("JSON.stringify"):
            ser = "JSON"
        elif args == '""':
            ser = "empty"
        else:
            ser = args[:40]
        actions.append({"plugin": plugin, "action": action, "args": ser})
    out.append({"file": f, "classes": cls, "actions": actions})

json.dump(out, open(r"D:\ets-rea\work\runtime\plugin_stubs_analysis.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

total = 0
for o in out:
    print(f"\n=== {o['file']}  classes={o['classes']}")
    for a in o["actions"]:
        print(f"   {a['plugin']:14s} {a['action']:36s} {a['args']}")
    total += len(o["actions"])
print("\nTOTAL actions:", total)
