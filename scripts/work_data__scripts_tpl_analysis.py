import json, collections, os, re
b=r"data\extracted"
# 1) diff content vs content2
def diff(a,b,path=""):
    out=[]
    if type(a)!=type(b): return [(path,type(a).__name__,type(b).__name__)]
    if isinstance(a,dict):
        for k in set(a)|set(b):
            if k not in a: out.append((path+"/"+k,"<absent>",str(b[k])[:60]))
            elif k not in b: out.append((path+"/"+k,str(a[k])[:60],"<absent>"))
            else: out+=diff(a[k],b[k],path+"/"+k)
    elif isinstance(a,list):
        if len(a)!=len(b): out.append((path,f"len={len(a)}",f"len={len(b)}"))
        for i,(x,y) in enumerate(zip(a,b)): out+=diff(x,y,path+f"/{i}")
    else:
        if a!=b: out.append((path,str(a)[:80],str(b)[:80]))
    return out
diffs={}
for d in os.listdir(b+r"\content"):
    p=b+r"\content"+os.sep+d
    c=json.load(open(p+r"\content.json",encoding="utf-8"))
    c2=json.load(open(p+r"\content2.json",encoding="utf-8"))
    if c!=c2:
        diffs[d]=diff(c,c2)[:20]
print("DIFFS:",json.dumps(diffs,ensure_ascii=False,indent=1))

# 2) template analysis
tpl=b+r"\template_686"
res=json.load(open(tpl+r"\res.json",encoding="utf-8"))
ctrl=json.load(open(tpl+r"\ctrl.json",encoding="utf-8"))
info=json.load(open(tpl+r"\info.json",encoding="utf-8"))
print("\nres keys:",list(res.keys()))
print("exam types:")
for et in res["exam_type_list"]:
    print(" ",et["exam_type_order"],et["exam_type_name"],et["exam_type_collect"],"score",et["exam_type_score"],"count",et["exam_type_count"],"exams",len(et["exam_list"]))
    for ex in et["exam_list"]:
        print("    exam_order",ex["exam_order"],"id",ex["exam_id"],"score",ex["exam_score"],"questions",[q["evaluation_type"] for q in ex["question_list"]], [q["engine_area"] for q in ex["question_list"]])
ctrl_fields=collections.Counter()
for e in ctrl: ctrl_fields.update(e.keys())
print("\nctrl entries:",len(ctrl),"fields:",dict(ctrl_fields))
print("filetype:",collections.Counter(e["filetype"] for e in ctrl))
print("dirtype:",collections.Counter(e["dirtype"] for e in ctrl))
models=collections.Counter()
for e in ctrl: models[e.get("model_pc",{}).get("htmlmodel")]+=1
print("htmlmodel:",dict(models))
cls=collections.Counter()
for e in ctrl:
    for j in e.get("model_pc",{}).get("jsparam",[]): cls[(j.get("classname"),j.get("source"))]+=1
print("jsparam classname/source:",dict(cls))
subids=collections.Counter(e["subid"] for e in ctrl)
print("subids:",dict(subids))
ph=sorted(set(re.findall(r"\{\{[a-z0-9]+\}\}",json.dumps(res)+json.dumps(ctrl))))
print("placeholders:",ph)
print("info code_ids:",[x["code_id"] for x in info])
json.dump({"res":res,"ctrl_stats":{"entries":len(ctrl),"filetype":dict(collections.Counter(e['filetype'] for e in ctrl)),
     "dirtype":dict(collections.Counter(e['dirtype'] for e in ctrl)),"htmlmodel":dict(models),
     "jsparam":{f"{k[0]}|{k[1]}":v for k,v in cls.items()},"subids":dict(subids),
     "fields":list(ctrl[0].keys())},"placeholders":ph,"info":info},
     open(r"data\resources_template_analysis.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
