import hashlib, base64, itertools

b64 = "W3siciI6ImNsaWVudC9tb2JpbGUtdXBkYXRlIiwicGFyYW1zIjp7ImNsaWVudF92ZXJzaW9uIjo1MDc5LCJvc190eXBlIjoiMTAiLCJ0YWciOiJwY19yZWZhY3RvciIsInNuIjoidGVzdCJ9fV0="
raw = base64.b64decode(b64).decode()
time_s = "1793184962"
sign = "b5a4daff3924782a8410d03a9e07e5b2"
KEY1 = "355ffbe95ccf4e9535a110170b445ab8"
KEY2 = "94cfbda3fbfef02b93693f8bc153be82"

print("raw:", raw)

parts = {"pid": "grlx", "time": time_s, "b64": b64, "raw": raw, "ver": "1.0",
         "K1": KEY1, "K2": KEY2, "keyid": "202608"}
hits = []
names = list(parts)
for r in (1, 2, 3, 4):
    for perm in itertools.permutations(names, r):
        s = "".join(parts[k] for k in perm)
        if hashlib.md5(s.encode()).hexdigest() == sign:
            hits.append("+".join(perm))
        for sep in ("&", "|", ":"):
            s2 = sep.join(parts[k] for k in perm)
            if hashlib.md5(s2.encode()).hexdigest() == sign:
                hits.append(("+".join(perm)) + f" sep={sep!r}")
print("hits:", hits[:20])

# print a few digests for comparison
for label, s in [("grlx+time+b64", "grlx" + time_s + b64),
                 ("grlx+time+b64+K1", "grlx" + time_s + b64 + KEY1),
                 ("time+b64", time_s + b64),
                 ("b64", b64),
                 ("raw", raw)]:
    print(label, hashlib.md5(s.encode()).hexdigest(), s[:40])
