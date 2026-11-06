import os,re,json
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
def brackets(s,op,cl):
    m={}; st=[]
    for i,c in enumerate(s):
        if c==op: st.append(i)
        elif c==cl and st: m[st.pop()]=i
    return m
B=brackets(txt,'{','}'); A=brackets(txt,'[',']')
# module route arrays
modranges=[]
for m in re.finditer(r'([A-Za-z_$][A-Za-z0-9_$]*)=\[\{path:"',txt):
    st=m.start(0)+len(m.group(1))+1
    end=A.get(st)
    if end: modranges.append((st,end,m.group(1)))
route_objs=[]
for m in re.finditer(r'\bpath:"',txt):
    p=m.start(); j=txt.rfind('{',max(0,p-200),p)
    if j<0: continue
    end=B.get(j)
    if end is None: continue
    obj=txt[j:end+1]
    route_objs.append(dict(start=j,end=end,obj=obj))
def meta_of(obj):
    mo=re.search(r'meta:\{',obj)
    if not mo: return {}
    s=mo.end()-1
    mb=brackets(obj,'{','}')
    e=mb.get(s)
    if e is None: return {}
    t=obj[s:e+1]; d={}
    for k in ['keepAlive','showMax','showFont','back','show','handleZoom','title','hideHeader','needLogin','noAuth','footer','showUser']:
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
        if o is r or o['start']==r['start']: continue
        if o['start']<r['start'] and o['end']>r['end'] and 'children:[' in txt[o['start']:r['start']]:
            if best is None or o['start']>best['start']: best=o
    return best
def mod_of(pos):
    for st,end,name in modranges:
        if st<=pos<=end: return name
    return None
routes=[]
for r in route_objs:
    obj=r['obj']
    pm=re.search(r'path:"([^"]*)"',obj)
    if not pm: continue
    path=pm.group(1)
    par=parent_of(r)
    nm=re.search(r'name:([A-Za-z0-9_$.]+|"[^"]*")',obj)
    name=nm.group(1).strip('"') if nm else None
    imports=re.findall(r'import\("\./([^"]+)"\)',obj)
    preload=list(dict.fromkeys(re.findall(r'"\./([^"]+\.(?:js|css))"',obj)))
    redirect=re.search(r'redirect:\{[^}]*\}',obj)
    # component can be direct component var or async import
    comp=imports[0] if imports else None
    if not comp:
        cm=re.search(r'component:([A-Za-z_$][A-Za-z0-9_$]*)',obj)
        if cm and cm.group(1) not in ('async',): comp=cm.group(1)
    routes.append(dict(path=path,name=name,parent=(par and re.search(r'path:"([^"]*)"',par['obj']).group(1)),
        component=comp,chunks=preload,meta=meta_of(obj),
        redirect=redirect.group(0) if redirect else None,
        module=mod_of(r['start']),line=txt.count('\n',0,r['start'])+1))
routes.sort(key=lambda x:x['line'])
for r in routes:
    r['chunk_present']=None
json.dump(routes,open(os.path.join(OUT,'routes.json'),'w'),ensure_ascii=False,indent=1)
print('routes',len(routes))
c=0
for r in routes:
    if r['meta']: c+=1
print('with meta',c)
print('modules',sorted(set(str(r['module']) for r in routes)))
for r in routes[:6]+routes[-6:]: print(r['line'],r['path'],r['name'],r['component'],r['meta'],r['module'])
