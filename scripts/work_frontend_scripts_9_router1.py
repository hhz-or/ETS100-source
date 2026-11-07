import os,re,json
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
main=[m for m in json.load(open(os.path.join(OUT,'manifest.json'))) if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
lines=txt.split('\n')
print('router lines:')
for i,l in enumerate(lines,1):
    if 'createRouter' in l or 'createWebHistory' in l or 'createWebHashHistory' in l:
        print(i, l[:300])
print()
print('path occurrences',txt.count('path:"'))
# sample first 6 path contexts
n=0
for m in re.finditer(r'path:"',txt):
    s=max(0,m.start()-80); e=m.start()+320
    print('...',txt[s:e].replace('\n','|')[:400])
    n+=1
    if n>=6: break
