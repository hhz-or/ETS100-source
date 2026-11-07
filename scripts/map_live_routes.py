import os, re, json, collections

CH = r"runtime\chunks_full"
live = {}
for f in os.listdir(CH):
    if f.endswith(".js"):
        m = re.match(r"(.+)-([0-9a-f]{8})\.js$", f)
        if m:
            live.setdefault(m.group(1), []).append(f)

routes = json.load(open(r"data/frontend\routes.json", encoding="utf-8"))
old_chunks = set()
for r in routes["routes"]:
    for c in r.get("chunks", []):
        old_chunks.add(c)

def base(c):
    m = re.match(r"(.+)-([0-9a-f]{8})\.js$", c)
    return m.group(1) if m else c

missing = []
mapped = {}
for c in sorted(old_chunks):
    b = base(c)
    if b in live:
        mapped[c] = live[b][0]
    else:
        missing.append(c)
print(f"old distinct chunks: {len(old_chunks)}  mapped: {len(mapped)}  missing: {len(missing)}")
print("missing (basename not in live):", missing[:30])

out = {"summary": {"old_routes": routes["summary"]["total"],
                   "old_chunks": len(old_chunks), "mapped": len(mapped), "missing": len(missing),
                   "live_files": sum(len(v) for v in live.values())},
       "routes": []}
for r in routes["routes"]:
    chips = []
    for c in r.get("chunks", []):
        b = base(c)
        chips.append(live[b][0] if b in live else None)
    if r.get("component"):
        b = base(r["component"])
        comp = live[b][0] if b in live else None
    else:
        comp = None
    out["routes"].append({"path": r.get("full_path"), "name": r.get("name"),
                          "component_live": comp, "chunks_live": chips})
json.dump(out, open(r"runtime\routes_live.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# live-only chunks not referenced by old routes (new features?)
used = {v for v in mapped.values()}
allchunks = {f for v in live.values() for f in v}
extra = sorted(allchunks - used)
print("\nlive chunks not in old routes:", len(extra))
for e in extra[:40]:
    print("  ", e)
