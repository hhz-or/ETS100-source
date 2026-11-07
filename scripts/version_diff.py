import hashlib, os, re, difflib

live = r"runtime\scripts\statics.ets100.com_ets-student-pc-web_assets_index-e7d07c24.js.js"
old = None
for f in os.listdir(r"data/frontend\bundles"):
    if "index-dc0257dd" in f:
        old = os.path.join(r"data/frontend\bundles", f)
print("live:", live, os.path.getsize(live))
print("old :", old, os.path.getsize(old) if old else None)

lb = open(live, "rb").read()
ob = open(old, "rb").read() if old else b""
print("live sha256:", hashlib.sha256(lb).hexdigest()[:32])
print("old  sha256:", hashlib.sha256(ob).hexdigest()[:32])

markers = [b"f05323cb91d422b2", b"ldlflfgirerjfkcf", b"encode_api_body_v2", b"sign_protocol_selected",
           b"BEGIN RSA PRIVATE KEY", b"key_id", b"sign_version", b"pcWin", b"grlx", b"202608",
           b"EtsSignatureAdapter", b"wss://", b"eduaiplat", b"api.ets100.com"]
for m in markers:
    print(f"{m.decode():28s} live={lb.count(m):4d} old={ob.count(m):4d}")

# extract chunk filenames referenced
pat = re.compile(rb'([A-Za-z0-9_\-]+-[0-9a-f]{8}\.js)')
lch = set(x.decode() for x in pat.findall(lb))
och = set(x.decode() for x in pat.findall(ob))
print("\nchunk refs: live", len(lch), "old", len(och))
print("added in live:", sorted(lch - och)[:20])
print("removed in live:", sorted(och - lch)[:20])

# version-ish strings around 'VERSION'
for name, b in (("live", lb), ("old", ob)):
    m = re.search(rb'VITE_APP_VERSION[^,;]{0,120}', b)
    print(name, "VITE_APP_VERSION:", m.group(0)[:160] if m else None)
    for mm in list(re.finditer(rb'version\s*[:=]\s*"([0-9]+\.[0-9]+\.[0-9]+)"', b))[:5]:
        print("  ", name, mm.group(0)[:80])

# compare sign adapter region textually
def region(b, marker, before=1500, after=3000):
    i = b.find(marker)
    return b[max(0, i-before):i+after] if i >= 0 else b""
lr = region(lb, b"EtsSignatureAdapter")
orr = region(ob, b"EtsSignatureAdapter")
print("\nEtsSignatureAdapter region equal:", lr == orr, len(lr), len(orr))
if lr != orr and orr:
    sm = difflib.SequenceMatcher(None, orr, lr)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            print(tag, "old:", orr[i1:i2][:200], "live:", lr[j1:j2][:200])
