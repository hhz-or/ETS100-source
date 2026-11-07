import glob, re, json, hashlib

K_UPDATE = "555ffbe95ccf4e9535a110170b445ab8"
ok = 0
total = 0
samples = []
for f in glob.glob(r"ETS\temp\update\log\INFO_uLOG_*"):
    t = open(f, "rb").read().decode("utf-8", "replace")
    for line in t.split("\n"):
        if "update_info.h" not in line:
            continue
        m = re.search(r'(\{[^\n]*"head"[^\n]*\})', line)
        if not m:
            continue
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        head = obj.get("head", {})
        body = obj.get("body", "")
        sign = head.get("sign")
        tm = str(head.get("time"))
        pid = head.get("pid")
        if not (sign and body):
            continue
        total += 1
        calc = hashlib.md5((pid + tm + body + K_UPDATE).encode()).hexdigest()
        samples.append({"file": f.split("\\")[-1], "pid": pid, "time": tm,
                        "sign": sign, "calc": calc, "match": calc == sign})
        if calc == sign:
            ok += 1
    # also capture sign/body pairs nested (request then response on separate lines)
print(f"update sign verify: {ok}/{total}")
for s in samples:
    print(s)
