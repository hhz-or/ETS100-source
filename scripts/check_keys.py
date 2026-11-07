import re

keys = [b"94cfbda3fbfef02b93693f8bc153be82", b"355ffbe95ccf4e9535a110170b445ab8",
        b"202608", b"pcWin", b"grlx"]
for path in [r"ETS\EtsUpdate.exe", r"ETS\ETSShell.exe",
             r"ETS\Ets.exe", r"ETS\plugins\httphelper\httphelper.pln",
             r"ETS\plugins\etshelper\etshelper.pln"]:
    b = open(path, "rb").read()
    print(path.split("\\")[-1], len(b))
    for k in keys:
        print("   ", k.decode(), b.count(k))
    # also UTF-16
    for k in keys:
        ku = k.decode().encode("utf-16-le")
        if b.count(ku):
            print("    utf16", k.decode(), b.count(ku))

print("\n=== response lines containing sign ===")
for lp in [r"ETS\logs\ets_2026-10-28.log", r"ETS\logs\ets_2026-11-4.log"]:
    t = open(lp, "rb").read().decode("utf-8", "replace")
    n = 0
    for line in t.split("\n"):
        if "ets response" in line and "sign" in line.lower():
            print(line[:400])
            n += 1
            if n > 6:
                break
