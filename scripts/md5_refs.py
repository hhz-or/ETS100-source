import re
p = r"work/ghidra_out(未发布)\etshelper.pln\decompiled.c"
txt = open(p, encoding="utf-8", errors="replace").read()
lines = txt.split("\n")
heads = [(i, l) for i, l in enumerate(lines) if l.startswith("// ====")]

def func_of(i):
    cur = None
    for h, l in heads:
        if h <= i:
            cur = (h, l)
        else:
            break
    return cur

def dump(name, maxlines=500):
    for i, l in enumerate(lines):
        if l.startswith("// ====") and name in l:
            end = i + 1
            while end < len(lines) and not lines[end].startswith("// ===="):
                end += 1
            print("\n" + "=" * 100)
            print(l)
            print("\n".join(lines[i:min(end, i + maxlines)]))
            return
    print("not found", name)

for n in ["FUN_10014110", "FUN_10014230"]:
    dump(n, 220)

# find all references to these functions
for target in ["FUN_10014110", "FUN_10014230"]:
    print("\n\n########## references to", target)
    for i, l in enumerate(lines):
        if target in l and not l.startswith("// ====") and not l.strip().startswith("//"):
            h = func_of(i)
            print(f"  line {i+1} in {h[1] if h else '?'}: {l.strip()[:180]}")
