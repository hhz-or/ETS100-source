import json
ls=json.load(open(r"data\storage\local_storage.json",encoding="utf-8"))
for r in ls:
    print("LS",r.get("key"),"|",r.get("value_encoding"),"|",r.get("value_len"),"|",json.dumps(r.get("value_summary"),ensure_ascii=False)[:200])
