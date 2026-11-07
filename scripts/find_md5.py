import re

p = r"work/ghidra_out(未发布)\etshelper.pln\decompiled.c"
txt = open(p, encoding="utf-8", errors="replace").read()
lines = txt.split("\n")
print("lines", len(lines))

targets = ["0x67452301", "0xefcdab89", "0x98badcfe", "0x10325476"]
for t in targets:
    for i, l in enumerate(lines):
        if t in l:
            # find function header above
            h = i
            while h > 0 and not lines[h].startswith("// ===="):
                h -= 1
            print(f"\n### {t} at line {i+1}; function header: {lines[h]}")
            print("\n".join(lines[h:h+3]))

# list all function headers with line numbers, find those around md5 constants
heads = [(i, l) for i, l in enumerate(lines) if l.startswith("// ====")]
def head_for(i):
    cur = None
    for h, l in heads:
        if h <= i:
            cur = (h, l)
        else:
            break
    return cur

seen = set()
for t in targets:
    for i, l in enumerate(lines):
        if t in l:
            h = head_for(i)
            if h and h[1] not in seen:
                seen.add(h[1])
                print("\nFOUND FUNC:", h[1], "at line", h[0] + 1)
                # print whole function up to next header
                start = h[0]
                end = start + 1
                while end < len(lines) and not lines[end].startswith("// ===="):
                    end += 1
                print("\n".join(lines[start:min(end, start + 400)]))
