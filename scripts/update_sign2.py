import hashlib, base64, itertools

b64 = "W3siciI6ImNsaWVudC9tb2JpbGUtdXBkYXRlIiwicGFyYW1zIjp7ImNsaWVudF92ZXJzaW9uIjo1MDc5LCJvc190eXBlIjoiMTAiLCJ0YWciOiJwY19yZWZhY3RvciIsInNuIjoidGVzdCJ9fV0="
raw = base64.b64decode(b64).decode()
time_s = "1793184962"
sign = "b5a4daff3924782a8410d03a9e07e5b2"
K33 = "555ffbe95ccf4e9535a110170b445ab8"
K32 = "355ffbe95ccf4e9535a110170b445ab8"
K1v2 = "94cfbda3fbfef02b93693f8bc153be82"

parts = {"pid": "grlx", "time": time_s, "b64": b64, "raw": raw, "ver": "1.0",
         "K33": K33, "K32": K32, "K2": K1v2}
names = list(parts)
hits = []
for r in (2, 3, 4):
    for perm in itertools.permutations(names, r):
        s = "".join(parts[k] for k in perm)
        if hashlib.md5(s.encode()).hexdigest() == sign:
            hits.append("+".join(perm))
        for sep in ("&", "|", ":", "\n", "_"):
            if hashlib.md5(sep.join(parts[k] for k in perm).encode()).hexdigest() == sign:
                hits.append("+".join(perm) + f" sep={sep!r}")
print("hits:", hits[:20])

# also try md5(body_b64+time+pid+K) etc already covered; try reversed key
for label, s in [("grlx+time+b64+K33", "grlx" + time_s + b64 + K33),
                 ("time+b64+K33", time_s + b64 + K33),
                 ("b64+time+K33", b64 + time_s + K33),
                 ("K33+time+b64", K33 + time_s + b64),
                 ("grlx+time+b64+K32", "grlx" + time_s + b64 + K32)]:
    print(label, hashlib.md5(s.encode()).hexdigest())
