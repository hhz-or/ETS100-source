import json,collections
ctrl=json.load(open(r"data\extracted\template_686\ctrl.json",encoding="utf-8"))
c=collections.Counter()
for e in ctrl:
    for j in e.get("model_pc",{}).get("jsparam",[]):
        c[(j.get("source"),j.get("code_id"),j.get("classname"))]+=1
for k,v in c.items(): print(k,v)
print("\ndirtype=content entries:")
for e in ctrl:
    if e["dirtype"]=="content": print(e["order"],e["subid"],e["filetype"],e["filename"],e["playhint"])
print("\ndirtype=templet filenames:")
print(collections.Counter(e["filename"] for e in ctrl if e["dirtype"]=="templet"))
print("\nall html filenames:")
print(sorted(set(e["filename"] for e in ctrl if e["filetype"]=="view.html")))
