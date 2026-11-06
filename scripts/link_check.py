import os, re

docs = r"D:\ets-rea\docs"
bad = []
for f in sorted(os.listdir(docs)):
    if not f.endswith(".md"):
        continue
    p = os.path.join(docs, f)
    t = open(p, encoding="utf-8").read()
    for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", t):
        link = m.group(1).strip()
        if link.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = link.split("#")[0]
        if not target:
            continue
        # resolve relative to docs dir
        cand = os.path.normpath(os.path.join(docs, target))
        if not os.path.exists(cand):
            # maybe relative to repo root
            cand2 = os.path.normpath(os.path.join(r"D:\ets-rea", target))
            if not os.path.exists(cand2):
                bad.append((f, link))
print("broken links:", len(bad))
for b in bad[:30]:
    print("  ", b)
