#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract targeted lines from shipped ETS logs (read-only) for evidence."""
import os, re, sys

root = r"ETS\logs"
out = []
pats = [
    ("plugin-load", re.compile(r"Pln|plugin|Plugin|\.pln|StiCorePln", re.I)),
    ("action", re.compile(r"actionKey|pluginKey|OnTaskAction|sendMessage|EXEC_CALLBACK|action->", re.I)),
    ("sign", re.compile(r"sign|encode_api|md5|hmac", re.I)),
    ("mq", re.compile(r"mq_server|suspensionBall|4000\d|websocket", re.I)),
    ("update", re.compile(r"update|upgrade|version", re.I)),
    ("error", re.compile(r"error|fail|exception", re.I)),
]
for fn in ["shell_2026-11-4.log", "ets_2026-11-4.log", "shell_2026-10-28.log", "ets_2026-10-28.log"]:
    p = os.path.join(root, fn)
    if not os.path.exists(p):
        continue
    data = open(p, "rb").read()
    # decode tolerant: try utf-8, else gbk, else latin-1
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except Exception:
            text = data.decode("latin-1")
    lines = text.splitlines()
    out.append("=" * 80)
    out.append("## %s  lines=%d" % (fn, len(lines)))
    for label, pat in pats:
        hits = [(i + 1, l) for i, l in enumerate(lines) if pat.search(l)]
        out.append("### %s  hits=%d" % (label, len(hits)))
        for ln, l in hits[:25]:
            out.append("%7d| %s" % (ln, l.strip()[:240]))
    out.append("")
open(r"data/native\_logs_excerpt.txt", "w", encoding="utf-8").write("\n".join(out))
print("wrote", len(out), "lines")
