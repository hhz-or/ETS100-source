import hashlib, itertools

def md5(s):
    return hashlib.md5(s.encode()).hexdigest()

body_b64 = "W3siciI6InN5c3RlbS90aW1lIiwicGFyYW1zIjp7InNuIjoidGVzdCJ9fV0="
import base64
body_raw = base64.b64decode(body_b64).decode()
t = "1793971732563"
K1 = "355ffbe95ccf4e9535a110170b445ab8"
K2 = "94cfbda3fbfef02b93693f8bc153be82"

# ---- v1 body oracle ----
target = "b0eb949d3f1bc869751594fc013099cb"
parts = {
    "grlx": "grlx", "pcWin": "pcWin", "time": t, "b64": body_b64, "raw": body_raw,
    "K1": K1, "K2": K2, "202608": "202608", "ver": "1.0", "empty": "",
}
names = list(parts)
hits = []
for r in range(2, 6):
    for perm in itertools.permutations(names, r):
        s = "".join(parts[k] for k in perm)
        if md5(s) == target:
            hits.append("+".join(perm))
print("v1 body hits:", hits[:10], "count", len(hits))

# ---- resp v2 oracle ----
rt = "6d3d82172ce30999a4b3890a022619bb"
rsp_b64 = "W10="
rsp_raw = base64.b64decode(rsp_b64).decode()
parts2 = {
    "pcWin": "pcWin", "grlx": "grlx", "time": t, "rsp_b64": rsp_b64, "rsp_raw": rsp_raw,
    "K1": K1, "K2": K2, "202608": "202608", "ver": "1.0", "empty": "",
    "response": "response",
}
hits2 = []
for r in range(2, 6):
    for perm in itertools.permutations(parts2, r):
        s = "".join(parts2[k] for k in perm)
        if md5(s) == rt:
            hits2.append("+".join(perm))
print("resp v2 hits:", hits2[:10], "count", len(hits2))

# ---- print a few candidate digests for reference ----
print("sample v1:", md5("grlx" + t + body_b64 + K1))
print("sample resp:", md5("pcWin" + t + rsp_b64 + K2))
