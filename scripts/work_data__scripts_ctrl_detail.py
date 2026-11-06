import json,collections
ctrl=json.load(open(r"D:\ets-rea\work\data\extracted\template_686\ctrl.json",encoding="utf-8"))
by=collections.defaultdict(list)
for e in ctrl: by[e["filetype"]].append(e)
for k,v in by.items():
    print("="*25,k,len(v))
    print(json.dumps(v[0],ensure_ascii=False)[:1200])
print("\nplayhint values:",collections.Counter(e["playhint"] for e in ctrl if e["playhint"]))
print("playparams:",collections.Counter(e["playparams"] for e in ctrl if e["playparams"]))
print("fileparams:",collections.Counter(e["fileparams"] for e in ctrl if e["fileparams"]))
print("synchro:",collections.Counter(e["synchro"] for e in ctrl if e["synchro"]))
print("extended nonempty:",[(e["order"],e["Extendedfield1"],e["Extendedfield2"],e["Extendedfield3"],e["Extendedfield4"]) for e in ctrl if any(e[f"Extendedfield{i}"] for i in range(1,5))][:10])
# content.json info samples for picture/dialogue res fields
c=json.load(open(r"D:\ets-rea\work\data\extracted\content\content_811847\content.json",encoding="utf-8"))
print("\npicture info keys:",list(c["info"].keys()))
print("std entry keys:",list(c["info"]["std"][0].keys()))
q=json.load(open(r"D:\ets-rea\work\data\extracted\content\content_811846\content.json",encoding="utf-8"))
print("dialogue info keys:",list(q["info"].keys()),"question0 keys:",list(q["info"]["question"][0].keys()),"std0 keys:",list(q["info"]["question"][0]["std"][0].keys()))
