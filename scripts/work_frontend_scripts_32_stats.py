import os,re,json,collections
OUT=r'data/frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
print('manifest entries',len(man),'unique sha',len(set(m['sha256'] for m in man)))
c=collections.Counter(m['type'] for m in man)
print('types(entries)',dict(c))
uniq=len(set(m['sha256'] for m in man))
print('bundle files',len(os.listdir(os.path.join(OUT,'bundles'))))
tot=sum(os.path.getsize(os.path.join(OUT,'bundles',f)) for f in os.listdir(os.path.join(OUT,'bundles')))
print('bundles MB',round(tot/1048576,2))
pt=sum(os.path.getsize(os.path.join(OUT,'pretty',f)) for f in os.listdir(os.path.join(OUT,'pretty')))
print('pretty MB',round(pt/1048576,2),'files',len(os.listdir(os.path.join(OUT,'pretty'))))
print('gzip-decompressed count',sum(1 for m in man if m.get('gzip')))
print('huge files',[(m['size'],m['url'][:60]) for m in sorted(man,key=lambda x:-x['size'])[:5]])
# stores
st=json.load(open(os.path.join(OUT,'stores.json')))
print('stores',len(st),[s['name'] for s in st])
# dynamic sendMessage (3rd arg not literal) in plugin files
PRETTY=os.path.join(OUT,'pretty')
dyn=[]
for f in os.listdir(PRETTY):
    if 'plugins__stic' not in f and 'plugins__clientDB' not in f: continue
    txt=open(os.path.join(PRETTY,f),encoding='utf-8',errors='replace').read()
    for m in re.finditer(r'cef\.message\.sendMessage\(([^;]{0,300}?)\)\s*(?=[,;}]|$)',txt):
        a=m.group(1)
        parts=[p.strip() for p in a.split(',')]
        if len(parts)>=3 and not parts[1].startswith('"'):
            dyn.append((f,parts[1],parts[2],txt.count('\n',0,m.start())+1))
print('dynamic channel sends',len(dyn))
for d in dyn[:12]: print(d)
# routes summary
r=json.load(open(os.path.join(OUT,'routes.json')))
print('routes',r['summary'])
