import re, os

def strings(p, minlen=6):
    b = open(p, "rb").read()
    asc = [m.group(0).decode("latin1") for m in re.finditer(rb"[ -~]{%d,}" % minlen, b)]
    u16 = [m.group(0).decode("utf-16-le", "ignore") for m in re.finditer(rb"(?:[ -~]\x00){%d,}" % minlen, b)]
    return asc + u16

print("=== Ets.exe ===")
ss = strings(r"D:\ets-rea\ETS\Ets.exe", 5)
pat = re.compile(r"\.exe|mq_|plugin|update|start|path|http|ETS|ets|Shell|dll|cmd|wait|process|Create", re.I)
seen = set()
for s in ss:
    if pat.search(s) and s not in seen:
        seen.add(s)
        if len(seen) > 120:
            break
        print(s[:180])

print("\n=== shell log: command line / cmdline ===")
p = r"D:\ets-rea\ETS\logs\shell_2026-11-4.log"
t = open(p, "rb").read().decode("gbk", "replace")
c = 0
for line in t.split("\n"):
    if re.search(r"cmdline|command line|CommandLine|--type=|argv|参数", line, re.I):
        print(line[:300])
        c += 1
        if c > 40:
            break
