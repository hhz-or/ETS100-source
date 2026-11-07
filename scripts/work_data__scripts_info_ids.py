import json,os,collections
b=r"data\extracted\content"
seen={}
for d in sorted(os.listdir(b)):
    p=os.path.join(b,d,"info.json")
    if not os.path.exists(p): continue
    ij=json.load(open(p,encoding="utf-8"))
    cj=json.load(open(os.path.join(b,d,"content.json"),encoding="utf-8"))
    st=cj.get("structure_type")
    key=(st,tuple(x["code_id"] for x in ij))
    if key not in seen: seen[key]=(d,[ (x['code_id'],x['code_type'],len(str(x['code_value']))) for x in ij])
for k,v in seen.items(): print(k[0],"|",v)
