import os,re,json
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
main=[m for m in json.load(open(os.path.join(OUT,'manifest.json'))) if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
lines=txt.split('\n')
for i,l in enumerate(lines,1):
    if 'getModuleRoutes' in l:
        print(i, l[:400])
print('total lines',len(lines))
