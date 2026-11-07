import re, gzip, os
base = r"ETS\temp\Cache_ETSShell\Cache"
b = open(os.path.join(base, "f_000002"), "rb").read()
print("f_000002 size", len(b))
for pat in [b"vue", b"element-plus", b"ElementPlus", b"pinia", b"vue-router", b"axios", b"ets-student-pc-web", b"cef.message", b"__VUE"]:
    print(pat, b.count(pat))
print("--- version-like strings ---")
for m in list(re.finditer(rb'["\']?version["\']?\s*[:=]\s*["\']([0-9][0-9.]{3,12})["\']', b))[:10]:
    print(b[m.start() - 60:m.start() + 60])
print("--- gz f_000001 ---")
g = open(os.path.join(base, "f_000001"), "rb").read()
try:
    d = gzip.decompress(g)
    print("decompressed", len(d))
    print(d[:400])
except Exception as e:
    print("gz err", e)
print("--- sniff all f_ files ---")
for f in sorted(os.listdir(base)):
    p = os.path.join(base, f)
    if not os.path.isfile(p) or not f.startswith("f_"):
        continue
    h = open(p, "rb").read(8)
    kind = "?"
    if h[:2] == b"\x1f\x8b":
        kind = "gzip"
    elif h[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "png"
    elif h[:3] == b"ID3" or h[:2] == b"\xff\xfb":
        kind = "mp3"
    elif h[:1] in (b"!", b"(", b"v", b"c", b"f", b"i", b"<"):
        kind = "text"
    print(f, os.path.getsize(p), kind, h[:8].hex())
