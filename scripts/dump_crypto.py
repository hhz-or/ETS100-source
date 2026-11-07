p = r"work/ghidra_out(未发布)\etshelper.pln\decompiled.c"
lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
heads = [(i, l) for i, l in enumerate(lines) if l.startswith("// ====")]

def dump(name, maxlines=400):
    for i, l in enumerate(lines):
        if l.startswith("// ====") and name in l:
            end = i + 1
            while end < len(lines) and not lines[end].startswith("// ===="):
                end += 1
            print("\n" + "=" * 110)
            print("\n".join(lines[i:min(end, i + maxlines)]))
            return
    print("not found", name)

for n in ["FUN_10013e00", "FUN_10014050", "FUN_10013fc0", "FUN_10023870", "FUN_10014110", "FUN_1000a410", "FUN_10009e60"]:
    dump(n, 260)

def func_of(i):
    cur = None
    for h, l in heads:
        if h <= i:
            cur = (h, l)
        else:
            break
    return cur

print("\n\n##### references to FUN_1000a410 and FUN_10009e60 #####")
for t in ["FUN_1000a410", "FUN_10009e60", "FUN_10013e00", "FUN_10013fc0"]:
    print("\n##", t)
    for i, l in enumerate(lines):
        if t in l and not l.startswith("// ===="):
            h = func_of(i)
            print(f"  line {i+1} in {h[1] if h else '?'}: {l.strip()[:200]}")
