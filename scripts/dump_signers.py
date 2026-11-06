import re
p = r"D:\ets-rea\work\ghidra_out\etshelper.pln\decompiled.c"
lines = open(p, encoding="utf-8", errors="replace").read().split("\n")

def dump(name, maxlines=600):
    for i, l in enumerate(lines):
        if l.startswith("// ====") and name in l:
            end = i + 1
            while end < len(lines) and not lines[end].startswith("// ===="):
                end += 1
            print("\n" + "=" * 110)
            print(l)
            print("\n".join(lines[i:min(end, i + maxlines)]))
            return
    print("not found", name)

for n in ["FUN_1000a410", "FUN_10009e60"]:
    dump(n, 700)
