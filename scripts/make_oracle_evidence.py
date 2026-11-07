import json, glob, hashlib, os

OUT = r"runtime"
files = sorted(glob.glob(os.path.join(OUT, "native_probe_*.json")))
probe1 = json.load(open(files[0], encoding="utf-8")) if files else []
body_b64 = "W3siciI6InN5c3RlbS90aW1lIiwicGFyYW1zIjp7InNuIjoidGVzdCJ9fV0="
t = "1793971732563"
K2 = "94cfbda3fbfef02b93693f8bc153be82"
computed = hashlib.md5(("pcWin" + t + body_b64 + K2).encode()).hexdigest()

rec = {
    "note": "运行时 oracle：在真实页面中直接调用原生插件 EtsHelper.encode_api_body_v2，验证签名公式",
    "input": {"body_b64": body_b64, "time": t},
    "native_result": None,
    "formula": "md5('pcWin' + time + body_b64 + KEY_V2)",
    "computed": computed,
    "match": None,
    "all_probes": probe1,
}
for p in probe1:
    if p.get("action") == "encode_api_body_v2":
        try:
            rec["native_result"] = json.loads(p["result"])
        except Exception:
            rec["native_result"] = p["result"]
if isinstance(rec["native_result"], dict):
    rec["match"] = rec["native_result"].get("sign") == computed
json.dump(rec, open(os.path.join(OUT, "sign_oracle.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("match:", rec["match"], "native:", rec["native_result"], "computed:", computed)
