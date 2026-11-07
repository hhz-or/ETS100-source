import json
ls=json.load(open(r"data\storage\local_storage.json",encoding="utf-8"))
for r in ls:
    if r.get("key") in ("appLogin","resourcePlatformStore"):
        print(r["key"], json.dumps(r["value_summary"],ensure_ascii=False)[:600])
idb=json.load(open(r"data\storage\indexeddb.json",encoding="utf-8"))
print("IDB total",idb["total_records"],"bytes",idb["record_bytes"])
print("LOGIN:",json.dumps(idb["login_records_redacted"],ensure_ascii=False)[:800])
print("DBID:",json.dumps({k:{"count":v["count"],"class":v["value_class"]} for k,v in idb["dbid_stats"].items()},ensure_ascii=False))
print("SCHEMA:",idb["schema_currentSchema"][:800])
