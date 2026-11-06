import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

b = open(r"D:\ets-rea\work\lead\cache_f_000002.txt", "rb").read()

def show(a, z, label):
    print("\n=================", label, f"off {a}..{z}")
    print(b[a:z].decode("utf-8", "replace"))

# whole request wrapper around sign body
show(3375500, 3377600, "request wrapper (sign)")

for pat in [b"ets request", b"ets response", b"httphelper", b"sendMessage(", b"HEAD_VERSION", b"V1_PID", b"SIGN_PATTERN"]:
    print("\n####", pat, b.count(pat))
    for m in list(re.finditer(re.escape(pat), b))[:3]:
        print("  off", m.start(), b[max(0, m.start()-160):m.start()+260].decode("utf-8", "replace").replace("\n", " "))
