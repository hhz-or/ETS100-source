import os, json, shutil, re

ROOT = r"D:\ets-rea"
PUB = os.path.join(ROOT, "publish")
if os.path.exists(PUB):
    shutil.rmtree(PUB)
os.makedirs(PUB)

# ---------- 1. docs ----------
shutil.copytree(os.path.join(ROOT, "docs"), os.path.join(PUB, "docs"))
# remove assets dir if empty
for d in ["docs/assets"]:
    p = os.path.join(PUB, d)
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)

# ---------- 2. scripts ----------
os.makedirs(os.path.join(PUB, "scripts"))
for src in ["work/scripts", "work/frontend/scripts", "work/data/_scripts", "work/native/_tools"]:
    sp = os.path.join(ROOT, src)
    if not os.path.isdir(sp):
        continue
    for f in os.listdir(sp):
        p = os.path.join(sp, f)
        if os.path.isfile(p) and os.path.getsize(p) < 400_000:
            dst = os.path.join(PUB, "scripts", f if src == "work/scripts" else src.replace("/", "_") + "_" + f)
            shutil.copy2(p, dst)

# ---------- 3. data ----------
os.makedirs(os.path.join(PUB, "data/api"))
os.makedirs(os.path.join(PUB, "data/frontend"))
os.makedirs(os.path.join(PUB, "data/native"))
os.makedirs(os.path.join(PUB, "data/db"))
os.makedirs(os.path.join(PUB, "runtime/plugin_js_stubs"))

def copy(rel, dst_rel=None, maxsize=5_000_000):
    src = os.path.join(ROOT, rel)
    dst = os.path.join(PUB, dst_rel or rel.replace("work/", "data/"))
    if os.path.isfile(src) and os.path.getsize(src) <= maxsize:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return True
    return False

copy("work/inventory.json", "data/inventory.json")
copy("work/inventory_hashes.json", "data/inventory_hashes.json")
copy("work/api/endpoints.csv", "data/api/endpoints.csv")
copy("work/api/ets_sign.py", "data/api/ets_sign.py")
copy("work/api/update_sign_proof.json", "data/api/update_sign_proof.json")
copy("work/frontend/routes.json", "data/frontend/routes.json")
copy("work/frontend/action_keys.json", "data/frontend/action_keys.json")
copy("work/runtime/plugin_stubs_analysis.json", "data/frontend/plugin_stubs_analysis.json")
copy("work/runtime/routes_live.json", "data/frontend/routes_live.json")
copy("work/runtime/chunks_manifest.json", "data/frontend/chunks_manifest.json")
copy("work/native/plugin_abi.json", "data/native/plugin_abi.json")
copy("work/native/_summary.json", "data/native/_summary.json")
for name in ["appcontroller", "etshelper", "filehelper", "sevenzip", "shellhelper", "soundhelper", "sqlitepln", "window_control", "httphelper"]:
    for fn in ["exports.json", "imports.json", "dispatch.json"]:
        copy(f"work/native/{name}/{fn}", f"data/native/{name}_{fn}")
copy("work/data/db/ETS_db_Config_rows.json", "data/db/ETS_db_Config_rows.json")
copy("work/data/db/ETS_db_dump.json", "data/db/ETS_db_dump.json")
copy("work/api/sign_samples.json", "data/api/sign_samples.json")

# runtime plugin stubs (vendor JS wrappers)
stubdir = os.path.join(ROOT, "work/runtime/scripts")
for f in os.listdir(stubdir):
    if "plugins_stic_" in f or "plugins_clientDB" in f or "plugins_crypto-js" in f:
        shutil.copy2(os.path.join(stubdir, f), os.path.join(PUB, "runtime/plugin_js_stubs", f.replace("statics.ets100.com_ets-student-pc-web_plugins_", "")))

# live requests: metadata only (no bodies / no responses) to avoid personal data
try:
    lr = json.load(open(os.path.join(ROOT, "work/runtime/live_requests.json"), encoding="utf-8"))
    pub = []
    for r in lr.get("requests", []):
        h = r.get("head") or {}
        pub.append({"url": r.get("url"), "path": __import__("re").sub(r"^https?://[^/]+", "", r.get("url", "")).split("?")[0],
                    "method": "POST", "sign": h.get("sign"), "pid": h.get("pid"), "time": h.get("time"),
                    "body_len": len(json.dumps(r.get("body"), ensure_ascii=False))})
    json.dump({"note": "仅元数据；原始请求/响应体含个人信息，未发布", "requests": pub},
              open(os.path.join(PUB, "runtime/live_requests.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
except Exception as e:
    print("live requests meta err", e)

# ---------- 4. sanitize ----------
JWT = re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}(?:\.[A-Za-z0-9_\-]{8,})?")
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
STS = re.compile(r"STS\.[A-Za-z0-9]{8,}")
AK = re.compile(r"LTAI[A-Za-z0-9]{8,}")
USERPATH = re.compile(r"C:\\\\?Users\\\\?[^\\\\\"'; ]+")
KNOWN = re.compile(r"1**********|***|***")

def sanitize_text(t):
    t = JWT.sub("<JWT>", t)
    t = STS.sub("<STS>", t)
    t = AK.sub("<AK>", t)
    t = PHONE.sub("1**********", t)
    t = USERPATH.sub(r"C:\Users\***", t)
    t = KNOWN.sub("***", t)
    for fld in ["token", "password", "phone", "encrypted_phone", "bind_mobile", "accessKeySecret",
                "access_key_secret", "secret", "uid", "device_code", "sn"]:
        t = re.sub(r'("%s"\s*:\s*")[^"]{4,}(")' % fld, r"\1***\2", t)
    # name / school / org-ish fields holding CJK text
    for fld in ["name", "user_name", "nickname", "real_name", "parent_name", "school_name",
                "class_name", "teacher_name", "student_name", "account_name", "display_name",
                "area", "region", "school", "klass", "class"]:
        t = re.sub(r'("%s"\s*:\s*")([^"]*[\u4e00-\u9fff][^"]*)(")' % fld, r"\1***\3", t)
    t = t.replace("***", "***").replace("***", "***").replace("***", "***")
    return t

changed = 0
for dp, dn, fn in os.walk(PUB):
    for f in fn:
        p = os.path.join(dp, f)
        if os.path.getsize(p) > 6_000_000:
            continue
        try:
            t = open(p, encoding="utf-8").read()
        except Exception:
            continue
        n = sanitize_text(t)
        if n != t:
            open(p, "w", encoding="utf-8").write(n)
            changed += 1
print("sanitized files:", changed)

# ---------- 5. sizes ----------
tot = 0
for dp, dn, fn in os.walk(PUB):
    for f in fn:
        tot += os.path.getsize(os.path.join(dp, f))
print("publish size MB:", round(tot / 1048576, 2))
for dp, dn, fn in os.walk(PUB):
    for f in sorted(fn)[:200]:
        p = os.path.join(dp, f)
        if os.path.getsize(p) > 300_000:
            print("big:", os.path.relpath(p, PUB), os.path.getsize(p))
