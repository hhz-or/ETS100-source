import json
b=r"D:\ets-rea\work\data\extracted\content"
def load(p): return json.load(open(p,encoding="utf-8"))
c=load(b+r"\content_811862\content.json"); c2=load(b+r"\content_811862\content2.json")
print("content 811862:",json.dumps(c,ensure_ascii=False)[:1200])
print()
print("content2 811862:",json.dumps(c2,ensure_ascii=False)[:1200])
print()
c=load(b+r"\content_811847\content.json")
print("content 811847 keys/struct:",json.dumps({k:(v if k!='info' else {kk:(str(vv)[:80]) for kk,vv in v.items()}) for k,v in c.items()},ensure_ascii=False)[:1500])
print()
c=load(b+r"\content_811848\content.json")
print("content 811848:",json.dumps({k:(v if k!='info' else {kk:(str(vv)[:60]) for kk,vv in v.items()}) for k,v in c.items()},ensure_ascii=False)[:1500])
