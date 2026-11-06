"""Dump ETS Chromium storage artifacts to work/data/storage/*.json with PII redaction."""
import sys, os, json, sqlite3, re, hashlib, struct
sys.path.insert(0, r"D:\ets-rea\work\data\_scripts")
import leveldb_reader as L

BASE = r"D:\ets-rea\ETS\temp\Cache_ETSShell"
OUT = r"D:\ets-rea\work\data\storage"
os.makedirs(OUT, exist_ok=True)

SENSITIVE = re.compile(r"(token|pwd|password|passwd|phone|mobile|account|secret|key|signature|authorization|cookie|session|credential|eCard|ecard|login|real_name|nickname|username|user_name|email|idcard|id_card|serial|mac|^ip$|device_?id|user_?id|student_no|birthday)", re.I)
PHONE = re.compile(r"\b1[3-9]\d{9}\b")
ACCT = re.compile(r"\bSHM\d+\b")
JWT = re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")
URLTOK = re.compile(r"(token|key|secret|sign|pwd|password)=([^&\s\"']+)", re.I)

def redact_val(s, depth=0):
    if not isinstance(s, str):
        return s
    s = JWT.sub("eyJ***.[JWT-REDACTED]", s)
    s = PHONE.sub("1**********", s)
    s = ACCT.sub("SHM*******", s)
    s = URLTOK.sub(lambda m: m.group(1) + "=***", s)
    return s

def redact(obj, depth=0):
    if depth > 30:
        return "[depth]"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if SENSITIVE.search(str(k)) and isinstance(v, (str, int, float)) and str(v):
                out[k] = {"_redacted": True, "len": len(str(v)),
                          "sha256_8": hashlib.sha256(str(v).encode()).hexdigest()[:8],
                          "prefix": str(v)[:6] + "..." if len(str(v)) > 8 else "***"}
            else:
                out[k] = redact(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [redact(x, depth + 1) for x in obj[:200]] + (["...%d more" % (len(obj) - 200)] if len(obj) > 200 else [])
    if isinstance(obj, str):
        return redact_val(obj)
    return obj

def try_json(b):
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:
        pass
    try:
        return json.loads(b.decode("utf-16le"))
    except Exception:
        return None

def dict_summary(d, maxdepth=2, maxitems=60):
    """keys + type/len instead of full values, for huge JSON"""
    if isinstance(d, dict):
        out = {}
        for i, (k, v) in enumerate(d.items()):
            if i >= maxitems:
                out["..."] = f"{len(d) - maxitems} more keys"
                break
            if isinstance(v, (dict, list)) and maxdepth > 0:
                out[k] = dict_summary(v, maxdepth - 1, maxitems)
            elif isinstance(v, str):
                out[k] = {"type": "str", "len": len(v), "sample": redact_val(v[:120])}
            else:
                out[k] = {"type": type(v).__name__, "value": v if not isinstance(v, str) else redact_val(v)}
        return out
    if isinstance(d, list):
        return {"_list": len(d), "sample": dict_summary(d[0], maxdepth - 1, maxitems) if d else None}
    return d

# ---------------- Local Storage ----------------
ls_dir = os.path.join(BASE, "Local Storage", "leveldb")
m = L.read_db(ls_dir)
ls_rows = []
for k, (seq, typ, val, src) in m.items():
    if k.startswith(b"META:"):
        ls_rows.append({"origin": k[5:].decode("utf-8", "replace"), "key": "<META>",
                        "value_summary": {"value_hex_head": val[:24].hex(), "value_len": len(val)}})
        continue
    if k == b"VERSION":
        ls_rows.append({"origin": None, "key": "VERSION", "value_summary": {"value": val.decode("latin1")}})
        continue
    if not k.startswith(b"_"):
        ls_rows.append({"origin": None, "key": k.decode("utf-8", "replace"), "raw_key_hex": k.hex()})
        continue
    rest = k[1:]
    if b"\x00" in rest:
        origin, key = rest.split(b"\x00", 1)
    else:
        origin, key = rest, b""
    origin = origin.decode("utf-8", "replace")
    if key.startswith(b"\x01"):
        enc = "utf-8(0x01)"
        key = key[1:]
    else:
        enc = "?"
    if val[:1] == b"\x01":
        body = val[1:]
        enc_val = "utf-8(0x01)"
        text = body.decode("utf-8", "replace")
    elif val[:1] == b"\x00":
        body = val[1:]
        enc_val = "utf-16le(0x00)"
        text = body.decode("utf-16le", "replace")
    else:
        body = val
        enc_val = "?"
        text = val.decode("utf-8", "replace")
    key_s = key.decode("utf-8", "replace")
    try:
        j = json.loads(text)
        summ = {"content_type": "json", "redacted_keys": dict_summary(j, 2)}
    except Exception:
        summ = {"content_type": "text", "value": redact_val(text[:300])}
    ls_rows.append({"origin": origin, "key": key_s, "key_encoding": enc,
                    "value_encoding": enc_val, "value_len": len(val),
                    "seq": seq, "deleted": typ == 0, "value_summary": summ})
json.dump(ls_rows, open(os.path.join(OUT, "local_storage.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------- Session Storage ----------------
ss_dir = os.path.join(BASE, "Session Storage")
m = L.read_db(ss_dir)
ss_rows = []
for k, (seq, typ, val, src) in m.items():
    ss_rows.append({"key": k.decode("utf-8", "replace"), "key_hex": k.hex(),
                    "value_len": len(val), "deleted": typ == 0,
                    "value_text": L.summarize(val, 200)})
json.dump(ss_rows, open(os.path.join(OUT, "session_storage.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------- IndexedDB ----------------
idb_dir = os.path.join(BASE, "IndexedDB", "https_statics.ets100.com_0.indexeddb.leveldb")
m = L.read_db(idb_dir)
stores = {}
schema_obj = None
login_recs = []
samples = {}
for k, (seq, typ, val, src) in m.items():
    txt = L.summarize(val, 3000)
    if "currentSchema" in txt and schema_obj is None:
        # extract the JSON schema text from between "value" marker and final '}'
        i = txt.find('{"composition"')
        if i >= 0:
            schema_obj = txt[i:i + 3000]
    if k.startswith(b"\x00\x01") and len(k) >= 4:
        dbid = k[2]
        osid = k[3]
        keyhex = k.hex()
        keytxt = L.extract_strings(k, 2)[:4]
        if "rememberMe" in txt or "SHM" in txt or "token" in txt:
            login_recs.append({"key_hex": keyhex, "key_text": keytxt, "value_len": len(val),
                               "value_text_redacted": redact_val(txt)[:600]})
        st = stores.setdefault(dbid, {"count": 0, "value_bytes": 0, "key_samples": [],
                                      "value_class": {}})
        st["count"] += 1
        st["value_bytes"] += len(val)
        cls = "wordDict" if ("AudioUrl_EN" in txt or "Spell_EN" in txt) else (
            "eval_upload" if "upload_file_url" in txt else (
                "login" if ("rememberMe" in txt or "SHM" in txt) else (
                    "config" if "currentSchema" in txt else ("empty" if not txt else "other"))))
        st["value_class"][cls] = st["value_class"].get(cls, 0) + 1
        if len(st["key_samples"]) < 8 and txt:
            st["key_samples"].append({"key_hex": keyhex[:120], "key_text": keytxt,
                                      "value_len": len(val), "value_summary": txt[:200]})
        if cls != "empty" and cls not in samples:
            samples[cls] = {"key_hex": keyhex, "value_len": len(val), "value_summary": txt[:400]}
idb = {
    "dir": idb_dir,
    "database": "https_statics.ets100.com_0 (origin https://statics.ets100.com, bucket 0)",
    "total_records": len(m),
    "record_bytes": sum(len(v[2]) for v in m.values()),
    "schema_currentSchema": schema_obj,
    "dbid_stats": {hex(k): {"count": v["count"], "bytes": v["value_bytes"],
                            "value_class": v["value_class"],
                            "key_samples": v["key_samples"]} for k, v in sorted(stores.items())},
    "login_records_redacted": login_recs[:6],
    "class_samples": samples,
    "key_layout_notes": {
        "00 01 <dbid> <osid> ...": "object-store data record (observed)",
        "00 00 ...": "metadata / deleted-marker entries (observed empty values)",
        "key type 0x01 = string (len + enc byte 0x00 + UTF-16LE), 0x03 = number (8-byte LE double)": "observed key encoding",
    },
}
json.dump(idb, open(os.path.join(OUT, "indexeddb.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------- Cookies ----------------
cp = os.path.join(BASE, "Cookies")
con = sqlite3.connect("file:" + cp.replace("\\", "/") + "?mode=ro", uri=True)
cur = con.cursor()
cookies = []
for row in cur.execute("select creation_utc,host_key,name,value,path,expires_utc,is_secure,is_httponly,last_access_utc,is_persistent,priority,encrypted_value,samesite,source_scheme,source_port,is_same_party from cookies"):
    (creation, host, name, value, path, expires, secure, httponly, last, persist, prio, enc, samesite, scheme, port, sameparty) = row
    ev = enc if isinstance(enc, (bytes, bytearray)) else b""
    cookies.append({
        "host_key": host, "name": name, "path": path,
        "value": redact_val(value) if value else "",
        "value_present": bool(value), "value_len": len(value or ""),
        "encrypted_value_len": len(ev),
        "encrypted_value_prefix_hex": bytes(ev[:3]).hex() if ev else "",
        "encrypted_value_sha256_8": hashlib.sha256(bytes(ev)).hexdigest()[:8] if ev else "",
        "creation_utc": creation, "expires_utc": expires, "is_persistent": persist,
        "is_secure": secure, "is_httponly": httponly, "priority": prio,
        "samesite": samesite, "source_scheme": scheme, "source_port": port,
        "is_same_party": sameparty,
    })
meta = dict(cur.execute("select key,value from meta"))
json.dump({"file": cp, "meta": meta, "cookie_count": len(cookies), "cookies": cookies},
          open(os.path.join(OUT, "cookies.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------- Databases.db ----------------
dp = os.path.join(BASE, "databases", "Databases.db")
con = sqlite3.connect("file:" + dp.replace("\\", "/") + "?mode=ro", uri=True)
cur = con.cursor()
ddb = {"file": dp, "tables": {}}
for (t,) in cur.execute("select name from sqlite_master where type='table'"):
    cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{t}")')]
    rows = [dict(zip(cols, r)) for r in cur.execute(f'select * from "{t}"')]
    ddb["tables"][t] = {"columns": cols, "rows": rows}
json.dump(ddb, open(os.path.join(OUT, "databases_db.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------------- misc files ----------------
misc = {}
for name in ["LocalPrefs.json", "Network Persistent State", "DevToolsActivePort", "LOG", "LOG.old",
             "CURRENT", "MANIFEST-000001"]:
    p = os.path.join(BASE, name)
    if os.path.exists(p):
        b = open(p, "rb").read()
        try:
            j = json.loads(b.decode("utf-8"))
            misc[name] = {"type": "json", "content": j}
        except Exception:
            misc[name] = {"type": "raw", "len": len(b), "text": b.decode("utf-8", "replace")[:1500]}
# Visited Links: binary; extract URLs
vp = os.path.join(BASE, "Visited Links")
vb = open(vp, "rb").read()
urls = re.findall(rb"https?://[ -~]{4,300}", vb)
misc["Visited Links"] = {"type": "binary", "len": len(vb), "magic_hex": vb[:8].hex(),
                         "url_count": len(urls),
                         "urls": sorted(set(u.decode("latin1") for u in urls))[:200]}
json.dump(misc, open(os.path.join(OUT, "chromium_misc.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("done: ls=%d ss=%d idb=%d cookies=%d" % (len(ls_rows), len(ss_rows), len(m), len(cookies)))
