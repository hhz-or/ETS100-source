import os, re, json

main = open(r"runtime\chunks_full\index-e7d07c24.js", encoding="utf-8", errors="replace").read()

# route objects: {path:"/xxx",name:"xxx",component:async()=>await __vitePreload(()=>import("./Comp-hash.js"),[...])}
pat = re.compile(r'\{path:"(/[^"]*)"[^{}]{0,400}?name:"([^"]+)"[^{}]{0,400}?component:async\(\)=>await __vitePreload\(\(\)=>import\("\./([^"]+)"\)')
routes = []
for m in pat.finditer(main):
    routes.append({"path": m.group(1), "name": m.group(2), "component": m.group(3)})
print("live routes parsed:", len(routes))

old = json.load(open(r"data/frontend\routes.json", encoding="utf-8"))
oldpaths = {r["full_path"] for r in old["routes"]}
new = [r for r in routes if r["path"] not in oldpaths]
print("new vs old cached routes:", len(new))
for r in new:
    print("  ", r["path"], "->", r["name"], r["component"])

json.dump({"count": len(routes), "routes": routes},
          open(r"runtime\live_routes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# also list "path:" occurrences without component (children routes)
allpaths = sorted(set(re.findall(r'path:"(/[^"]+)"', main)))
print("\nall path strings:", len(allpaths))
missing = [p for p in allpaths if p not in oldpaths]
print("paths not in old routes:", missing[:40])
json.dump({"paths": allpaths, "not_in_old": missing},
          open(r"runtime\live_paths_routes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
