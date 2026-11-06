import hashlib, base64, itertools

K2 = "94cfbda3fbfef02b93693f8bc153be82"
K1 = "355ffbe95ccf4e9535a110170b445ab8"
body_b64 = "W3siciI6InN5c3RlbS90aW1lIiwicGFyYW1zIjp7InNuIjoidGVzdCJ9fV0="
t = "1793971732563"
pid2, pid1 = "pcWin", "grlx"

def md5(s):
    return hashlib.md5(s.encode()).hexdigest()

print("body v2 target 7960a6bda26ffa4b2ec84725036488e0")
for name, s in [("pid+time+b64+K2", pid2 + t + body_b64 + K2),
                ("pid+time+b64", pid2 + t + body_b64),
                ("time+b64+K2", t + body_b64 + K2)]:
    print("  ", name, md5(s), "MATCH" if md5(s) == "7960a6bda26ffa4b2ec84725036488e0" else "")

print("body v1 target b0eb949d3f1bc869751594fc013099cb")
for name, s in [("pid+time+b64+K1", pid1 + t + body_b64 + K1),
                ("pid+time+b64", pid1 + t + body_b64),
                ("pid+time+b64+K2", pid1 + t + body_b64 + K2),
                ("pid+time+b64+K1+5", pid1 + t + body_b64 + "5" + K1)]:
    print("  ", name, md5(s), "MATCH" if md5(s) == "b0eb949d3f1bc869751594fc013099cb" else "")

# response v2 target 6d3d82172ce30999a4b3890a022619bb, rsp b64 W10=
rsp = "W10="
target = "6d3d82172ce30999a4b3890a022619bb"
cands = {
    "pid+time+rsp+K2": pid2 + t + rsp + K2,
    "pid+rsp+time+K2": pid2 + rsp + t + K2,
    "pid+time+response+K2": pid2 + t + "response" + K2,
    "pid+time+rsp": pid2 + t + rsp,
    "rsp+pid+time+K2": rsp + pid2 + t + K2,
    "pid+time+K2+rsp": pid2 + t + K2 + rsp,
    "pid+response+time+K2": pid2 + "response" + t + K2,
    "pid+time+rsp+202608+K2": pid2 + t + rsp + "202608" + K2,
}
print("resp v2 target", target)
for name, s in cands.items():
    print("  ", name, md5(s), "MATCH" if md5(s) == target else "")

# response v1 target 086a94f6c8b8638b93c02023336ec2f2
t1 = "086a94f6c8b8638b93c02023336ec2f2"
print("resp v1 target", t1)
for name, s in [("grlx+time+rsp+K1", pid1 + t + rsp + K1), ("grlx+rsp+time+K1", pid1 + rsp + t + K1),
                ("grlx+time+rsp", pid1 + t + rsp)]:
    print("  ", name, md5(s), "MATCH" if md5(s) == t1 else "")
