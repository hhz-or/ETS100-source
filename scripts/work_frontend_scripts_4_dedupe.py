import os,json,hashlib,collections
OUT=r'D:\ets-rea\work\frontend'; BUND=os.path.join(OUT,'bundles')
man=json.load(open(os.path.join(OUT,'manifest.json')))
byhash=collections.defaultdict(list)
for m in man:
    p=os.path.join(BUND,m['file'])
    if not os.path.exists(p):
        byhash[m['sha256']].append(m); continue
    byhash[m['sha256']].append(m)
# keeper = lowest index
removed=0
for h,lst in byhash.items():
    lst.sort(key=lambda x:x['index'])
    keeper=lst[0]
    for m in lst[1:]:
        p=os.path.join(BUND,m['file'])
        if os.path.exists(p) and m['file']!=keeper['file']:
            os.remove(p); removed+=1
        m['file']=keeper['file']; m['duplicate_of']=keeper['index']
json.dump(man,open(os.path.join(OUT,'manifest.json'),'w'),ensure_ascii=False,indent=1)
print('removed dup files',removed,'unique',len(set(m['sha256'] for m in man)))
