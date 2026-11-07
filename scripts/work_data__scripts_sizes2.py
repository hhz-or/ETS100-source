import json,os,collections,hashlib
# sizes
def du(p):
    t=0;n=0
    for dp,dn,fn in os.walk(p):
        for f in fn:
            try: t+=os.path.getsize(os.path.join(dp,f)); n+=1
            except: pass
    return t,n
for p in [r"data", r"data\extracted"]:
    t,n=du(p); print(p, n, "files", round(t/1024/1024,1),"MB")
# cache
c=r"ETS\temp\Cache_ETSShell\Cache"
print("cache f_ files:",len([f for f in os.listdir(c) if f.startswith('f_')]),
      "sum MB", round(sum(os.path.getsize(os.path.join(c,f)) for f in os.listdir(c))/1024/1024,2))
# LS table
ls=json.load(open(r"data\storage\local_storage.json",encoding="utf-8"))
for r in ls:
    print("LS",r.get("origin"),"|",r.get("key"),"|",r.get("value_encoding"),"|",r.get("value_len"),"|",json.dumps(r.get("value_summary"),ensure_ascii=False)[:160])
