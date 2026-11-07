import os,re,json,collections
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
lines=txt.split('\n')
# api endpoints
eps=collections.OrderedDict()
for i,l in enumerate(lines,1):
    for m in re.finditer(r'(?:postIt|postJoin|getIt|get)\(\s*"([^"]+)"',l):
        u=m.group(1)
        if u.startswith('/') or re.match(r'^[a-z]+/',u) or u.startswith('http'):
            if u not in eps: eps[u]=i
    for m in re.finditer(r'url:\s*"([^"]+)"',l):
        u=m.group(1)
        if u not in eps: eps[u]=i
print('endpoints',len(eps))
for u,i in eps.items(): print(i,u)
json.dump([{'url':u,'line':i} for u,i in eps.items()],open(os.path.join(OUT,'api_endpoints.json'),'w'),ensure_ascii=False,indent=1)
# stores
stores=[]
for m in re.finditer(r'defineStore\("([^"]+)"',txt):
    stores.append((txt.count('\n',0,m.start())+1,m.group(1)))
print('stores',len(stores),stores)
json.dump([{'name':n,'line':l} for l,n in stores],open(os.path.join(OUT,'stores.json'),'w'),ensure_ascii=False,indent=1)
