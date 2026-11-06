import glob, re, json, hashlib

K_UPDATE = "555ffbe95ccf4e9535a110170b445ab8"
out = []
for f in glob.glob(r"D:\ets-rea\ETS\temp\update\log\INFO_uLOG_*"):
    t = open(f, "rb").read().decode("utf-8", "replace")
    for line in t.split("\n"):
        if "update_info.h" not in line:
            continue
        m = re.search(r'(\{[^\n]*"head"[^\n]*\})', line)
        if not m:
            continue
        obj = json.loads(m.group(1))
        head = obj["head"]; body = obj["body"]
        calc = hashlib.md5((head["pid"] + str(head["time"]) + body + K_UPDATE).encode()).hexdigest()
        out.append({"log": f.split("\\")[-1], "pid": head["pid"], "time": str(head["time"]),
                    "body_b64": body, "sign": head["sign"], "calc": calc, "match": calc == head["sign"]})
json.dump(out, open(r"D:\ets-rea\work\api\update_sign_proof.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", len(out), "samples; all match:", all(o["match"] for o in out))
