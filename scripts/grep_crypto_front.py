import os, re

root = r"data/frontend\bundles"
if not os.path.isdir(root):
    root = r"work/lead(未发布)"
kws = [b"encrypt", b"decrypt", b"AES", b"aes", b"crypto", b"CryptoJS", b"RSA", b"privateKey",
       b"publicKey", b"forge", b"sm2", b"sm4", b"encrypted_phone", b"encryptPhone", b"password"]
hits = {}
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.lower().endswith((".js", ".txt")):
            continue
        p = os.path.join(dp, f)
        try:
            b = open(p, "rb").read()
        except Exception:
            continue
        c = {}
        for k in kws:
            n = b.count(k)
            if n:
                c[k.decode()] = n
        if c:
            hits[os.path.relpath(p, root)] = c
for f, c in sorted(hits.items(), key=lambda x: -sum(x[1].values()))[:20]:
    print(f, c)

# show contexts for AES / encrypt in the main bundle if present
mp = None
for cand in [r"data/frontend\bundles"]:
    for dp, dn, fn in os.walk(cand):
        for f in fn:
            p = os.path.join(dp, f)
            if os.path.getsize(p) > 3_000_000:
                mp = p
print("\nmain bundle:", mp)
if mp:
    b = open(mp, "rb").read()
    for pat in [b"encrypted_phone", b"AES", b"privateKey"]:
        print("\n####", pat, b.count(pat))
        for m in list(re.finditer(re.escape(pat), b))[:2]:
            print(b[max(0, m.start() - 300):m.start() + 400].decode("utf-8", "replace").replace("\n", " ")[:700])
