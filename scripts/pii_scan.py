import os, re, json

root = r".\docs"
patterns = {
    "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "sts": re.compile(r"STS\.[A-Za-z0-9]{10,}"),
    "accesskey": re.compile(r"LTAI[A-Za-z0-9]{8,}"),
    "known_plain": re.compile(r"1**********|***|***"),
    "b64_cred": re.compile(r"access_key_secret"),
    "at": re.compile(r"[\w.+-]+@(?!example)[\w-]+\.[\w.]+"),
}
for dp, dn, fn in os.walk(root):
    for f in fn:
        p = os.path.join(dp, f)
        if not f.endswith(".md"):
            continue
        t = open(p, encoding="utf-8", errors="replace").read()
        found = {}
        for k, rx in patterns.items():
            ms = rx.findall(t)
            if ms:
                found[k] = list(dict.fromkeys(ms))[:5]
        print(os.path.relpath(p, root), found if found else "clean")
