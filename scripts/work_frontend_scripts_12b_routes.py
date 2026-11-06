import os,re,json
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
match={}; st=[]
for i,c in enumerate(txt):
    if c=='{': st.append(i)
    elif c=='}':
        if st: match[st.pop()]=i
# module array name boundaries
mods=[]
for m in re.finditer(r'__vite_glob_0_(\d+)\$2=Object.freeze',txt):
    mods.append((m.start(),'module_%s'%m.group(1)))
# extract route objects
route_objs=[]
for m in re.finditer(r'\bpath:"',txt):
    p=m.start(); j=txt.rfind('{',max(0,p-200),p)
    if j<0: continue
    end=match.get(j)
    if end is None: continue
    obj=txt[j:end+1]
    if '__vitePreload' not in obj and 'component:' not in obj: continue
    if 'routeRecordRedirectOption' in obj or 'matched:' in obj: continue
    route_objs.append(dict(start=j,end=end,obj=obj,path=re.search(r'path:"([^"]*)"',obj).group(1)))
def meta_of(obj):
    mo=re.search(r'meta:\{',obj)
    if not mo: return {}
    s=mo.end()-1; e=match.get(s)
    if not e: return {}
    t=obj[s:e+1]; d={}
    for k in ['keepAlive','showMax','showFont','back','show','handleZoom','title','hideHeader','needLogin','noAuth','footer']:
        mm=re.search(k+r':(!0|!1|"[^"]*"|\d+)',t)
        if mm:
            v=mm.group(1)
            if v=='!0': v=True
            elif v=='!1': v=False
            elif v.startswith('"'): v=v[1:-1]
            d[k]=v
    return d
def parent_of(r):
    best=None
    for o in route_objs:
        if o is r: continue
        if o['start']<r['start'] and o['end']>r['end'] and 'children:[' in txt[o['start']:r['start']]:
            if best is None or o['start']>best['start']: best=o
    return best
def mod_of(pos):
    cur=None
    for p,name in mods:
        if p<pos: cur=name
    # module arrays appear before the freeze; map by nearest preceding __vite_glob N? simplistic
    return cur
routes=[]
for r in route_objs:
    par=parent_of(r)
    obj=r['obj']
    nm=re.search(r'name:([A-Za-z0-9_$.]+|"[^"]*")',obj)
    name=nm.group(1).strip('"') if nm else None
    imports=re.findall(r'import\("\./([^"]+)"\)',obj)
    preload=list(dict.fromkeys(re.findall(r'"\./([^"]+\.(?:js|css))"',obj)))
    redirect=re.search(r'redirect:\{[^}]*\}',obj)
    routes.append(dict(path=r['path'],name=name,parent=(par['path'] if par else None),
        component=imports[0] if imports else None,chunks=preload,meta=meta_of(obj),
        redirect=redirect.group(0) if redirect else None, line=txt.count('\n',0,r['start'])+1))
# fix numbering: sort by line
routes.sort(key=lambda x:x['line'])
# enrich chunk availability
bybase={}
for m in man:
    b=os.path.basename(m['file'])
    bybase.setdefault(b,[]).append(m)
for r in routes:
    avail=[]
    for c in ([r['component']] if r['component'] else [])+r['chunks']:
        base=c.split('/')[-1]
        found=any(base in x['file'] for x in man)
        avail.append((c, found))
    r['chunk_availability']=avail
json.dump(routes,open(os.path.join(OUT,'routes.json'),'w'),ensure_ascii=False,indent=1)
print('routes',len(routes))
print('with meta',sum(1 for r in routes if r['meta']))
for r in routes:
    print(r['line'],r['path'],'|',r['name'],'| parent',r['parent'],'|',r['component'],'|',r['meta'] if r['meta'] else '')
