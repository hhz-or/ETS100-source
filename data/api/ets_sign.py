"""
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
    recs = json.load(open(r"data/api\sign_samples.json", encoding="utf-8"))
    n = 0
    for r in recs:
        if sign_v2(r["body_json_exact"], r["time"]) == r["sign"].lower():
            n += 1
    print(f"self-test {n}/{len(recs)}")
