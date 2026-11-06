#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""peek into a dumped disassembly section: filter interesting lines."""
import sys

path = sys.argv[1]
sec = sys.argv[2]           # substring of section header
what = sys.argv[3] if len(sys.argv) > 3 else "calls"
lines = open(path, encoding="utf-8").read().splitlines()
# section boundaries are lines starting with '# etshelper'
idx = [i for i, l in enumerate(lines) if l.startswith("# ")]
if not idx:
    idx = [0]
sel = None
for k, i in enumerate(idx):
    if sec in lines[i]:
        sel = (i, idx[k + 1] if k + 1 < len(idx) else len(lines))
        break
if sel is None:
    print("section not found; headers:")
    for i in idx:
        print("  ", lines[i])
    sys.exit(1)
a, b = sel
body = lines[a:b]
print(body[0])
n = 0
for l in body:
    keep = False
    if what == "calls":
        keep = ("call " in l) or ("; " in l) or ("jmp " in l)
    elif what == "strings":
        keep = "; " in l
    elif what == "all":
        keep = True
    elif what == "consts":
        keep = ("0x1006" in l) or ("0x1007" in l) or ("; " in l)
    if keep:
        print(l)
        n += 1
print("# lines:", n)
