import re

p = r"D:\ets-rea\work\ghidra_out\EtsUpdate.exe\decompiled.c"
lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
heads = [(i, l) for i, l in enumerate(lines) if l.startswith("// ====")]
print("lines", len(lines), "funcs", len(heads))

def func_of(i):
    cur = None
    for h, l in heads:
        if h <= i:
            cur = (h, l)
        else:
            break
    return cur

for pat in ["0x67452301", "0x811c9dc5", "grlx", "key_id", "sign_version", "202608",
            "mobile-update", "\"sign\"", "sign\":"]:
    idxs = [i for i, l in enumerate(lines) if pat in l]
    fs = []
    for i in idxs:
        h = func_of(i)
        if h and h[1] not in fs:
            fs.append(h[1])
    print(f"{pat}: {len(idxs)} refs, funcs: {fs[:10]}")
