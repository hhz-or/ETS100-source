import re, os, glob

root = r"data/frontend\bundles"
cands = glob.glob(os.path.join(root, "*Login-*.js")) + glob.glob(os.path.join(root, "*ECardLogin*.js"))
print("files:", [os.path.basename(c) for c in cands])
for p in cands:
    b = open(p, "rb").read()
    print("\n========", os.path.basename(p), len(b))
    for pat in [b"encrypt", b"encrypted_phone", b"AES", b"key", b"iv"]:
        ms = list(re.finditer(re.escape(pat), b))
        print(f"  {pat.decode()}: {len(ms)}")
    for m in list(re.finditer(rb"encrypt", b))[:6]:
        s = b[max(0, m.start() - 500):m.start() + 500].decode("utf-8", "replace")
        print("  ---", s.replace("\n", " ")[:1000])
