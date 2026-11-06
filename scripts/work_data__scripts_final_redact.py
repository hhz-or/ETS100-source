import os,re,json
D=r"D:\ets-rea\work\data"
ACCT=re.compile(r"SHM\d{6,}")
JWT=re.compile(r"eyJ[A-Za-z0-9_\-]{6,}(?:\.[A-Za-z0-9_\-]*){0,3}")
PHONE=re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
def red(s):
    s=JWT.sub("eyJ***REDACTED",s)
    s=ACCT.sub("SHM*******",s)
    s=PHONE.sub("1**********",s)
    return s
def walk(o):
    if isinstance(o,str): return red(o)
    if isinstance(o,list): return [walk(x) for x in o]
    if isinstance(o,dict): return {k:walk(v) for k,v in o.items()}
    return o
n=0
for sub in ("storage","logs","soundfiles","db"):
    for f in os.listdir(os.path.join(D,sub)):
        p=os.path.join(D,sub,f)
        if not f.endswith(".json"): continue
        d=json.load(open(p,encoding="utf-8"))
        json.dump(walk(d),open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
        n+=1
for f in ("resources_content_index.json","resources_template_analysis.json","resources_common_index.json"):
    p=os.path.join(D,f)
    d=json.load(open(p,encoding="utf-8"))
    json.dump(walk(d),open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=1); n+=1
print("re-redacted",n)
