import os, json, hashlib, glob, collections
base=r"data\extracted\content"
tpl=r"data\extracted\template_686"
out={}
for d in sorted(os.listdir(base)):
    p=os.path.join(base,d)
    if not os.path.isdir(p): continue
    rec={"id":d.split("_")[1],"files":{}}
    for root,_,fs in os.walk(p):
        for f in fs:
            fp=os.path.join(root,f)
            rel=os.path.relpath(fp,p).replace("\\","/")
            rec["files"][rel]={"size":os.path.getsize(fp),"sha256":hashlib.sha256(open(fp,'rb').read()).hexdigest()[:16]}
    cj=json.load(open(os.path.join(p,"content.json"),encoding="utf-8"))
    rec["structure_type"]=cj.get("structure_type")
    rec["info_keys"]=sorted(cj.get("info",{}).keys()) if isinstance(cj.get("info"),dict) else type(cj.get("info")).__name__
    rec["stid"]=cj.get("info",{}).get("stid") if isinstance(cj.get("info"),dict) else None
    c2=json.load(open(os.path.join(p,"content2.json"),encoding="utf-8")) if os.path.exists(os.path.join(p,"content2.json")) else None
    rec["content_eq_content2"]= (cj==c2)
    ij=json.load(open(os.path.join(p,"info.json"),encoding="utf-8"))
    rec["info_json"]=[{"code_id":x.get("code_id"),"code_type":x.get("code_type"),"val_len":len(str(x.get("code_value","")))} for x in ij]
    rec["content_json_full"]=cj if len(json.dumps(cj))<3000 else {"_truncated":True}
    out[d]=rec
json.dump(out,open(r"data\resources_content_index.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)

# aggregate
st=collections.Counter(v["structure_type"] for v in out.values())
keysets=collections.Counter(tuple(v["info_keys"]) for v in out.values() if isinstance(v["info_keys"],list))
print("structure_types:",dict(st))
print("info keysets:")
for k,c in keysets.items(): print("  ",c,k)
print("content==content2:",sum(1 for v in out.values() if v["content_eq_content2"]),"/",len(out))
for k,v in out.items(): print(k, v["stid"], v["structure_type"], v["files"].keys(), "eq2=",v["content_eq_content2"])
