import json,re
d=json.load(open(r"D:\ets-rea\work\data\logs\resource_events.json",encoding="utf-8"))
for f in d:
    print("="*20,f["file"],f["hit_count"])
    for h in f["hits"]:
        if re.search(r"download|content_|template_|common\.zip|rpk|zip",h,re.I):
            print(h[:300])
