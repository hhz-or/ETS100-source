import json, base64, hashlib

KS1 = bytes.fromhex("3934636662646133666266656630326239333639336638626331353362653832").decode()  # 94cf...
KS0 = bytes.fromhex("3335356666626539356363663465393533356131313031373062343435616238").decode()  # 355f...
assert KS1 == "94cfbda3fbfef02b93693f8bc153be82"
assert KS0 == "355ffbe95ccf4e9535a110170b445ab8"

recs = json.load(open("data/api/sign_samples.json", encoding="utf-8"))
ok = 0
bad = []
for r in recs:
    b64 = base64.b64encode(r["body_json_exact"].encode("utf-8")).decode("ascii")
    msg = "pcWin" + r["time"] + b64 + KS1
    d = hashlib.md5(msg.encode("utf-8")).hexdigest()
    if d == r["sign"].lower():
        ok += 1
    else:
        bad.append((r["n"], r["sign"], d, r["ref"]))
print(f"v2 verify: {ok}/{len(recs)} match")
for b in bad[:10]:
    print("MISMATCH", b)

# ---- write reference implementation ----
impl = '''"""
ETS API 请求签名（v2，2026-08 密钥）—— 从 etshelper.pln 反编译还原并 334/334 验证
用法:
    sign_v2(body_json_str, time_ms_str) -> 32hex
其中 body_json_str 是前端 JSON.stringify([{r, params}]) 的结果（无空格），
time_ms_str 是 String(Date.now())。
"""
import hashlib, base64

KEY_V2 = "94cfbda3fbfef02b93693f8bc153be82"   # selector=1, key_id="202608"
KEY_V1 = "355ffbe95ccf4e9535a110170b445ab8"   # selector=0, pid="grlx"
PID_V2 = "pcWin"
PID_V1 = "grlx"


def sign_v2(body_json_str: str, time_ms_str: str) -> str:
    b64 = base64.b64encode(body_json_str.encode("utf-8")).decode("ascii")
    return hashlib.md5((PID_V2 + time_ms_str + b64 + KEY_V2).encode("utf-8")).hexdigest()


def sign_v1(body_json_str: str, time_ms_str: str) -> str:
    b64 = base64.b64encode(body_json_str.encode("utf-8")).decode("ascii")
    return hashlib.md5((PID_V1 + time_ms_str + b64 + KEY_V1).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    import json, sys
    # self-test against captured samples
    recs = json.load(open("data/api/sign_samples.json", encoding="utf-8"))
    n = 0
    for r in recs:
        if sign_v2(r["body_json_exact"], r["time"]) == r["sign"].lower():
            n += 1
    print(f"self-test {n}/{len(recs)}")
'''
open("ets_sign.generated.py", "w", encoding="utf-8").write(impl)
print("wrote ets_sign.py")

# also produce a compact proof table
proof = []
for r in recs[:20]:
    b64 = base64.b64encode(r["body_json_exact"].encode("utf-8")).decode("ascii")
    proof.append({
        "n": r["n"], "ref": r["ref"], "time": r["time"],
        "body_b64": b64, "sign": r["sign"],
        "md5(pcWin+time+b64+KEY)": hashlib.md5(("pcWin" + r["time"] + b64 + KS1).encode()).hexdigest(),
    })
json.dump(proof, open("sign_proof.generated.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote sign_proof.json")
