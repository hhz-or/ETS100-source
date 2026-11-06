import json
ls=json.load(open(r"D:\ets-rea\work\data\storage\local_storage.json",encoding="utf-8"))
for r in ls:
    if r.get("key") in ("appLogin","resourcePlatformStore","clientConfig","systemConfig","userInfo","syncLessionStore","appConfig","appOssStore"):
        print("="*15,r["key"],r.get("value_len"))
        print(json.dumps(r["value_summary"],ensure_ascii=False,indent=1)[:1500])
