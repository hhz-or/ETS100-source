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
modranges=[]
for m in re.finditer(r'([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\[\s*\{',txt):
    st=m.start(0)+m.group(0).rfind('[')
    end=A.get(st)
    if end: modranges.append((st,end,m.group(1)))
print('module ranges',[(n,s,e) for s,e,n in modranges])
# RouteNames
rn={}
m=re.search(r'RouteNames\s*=\s*\{',txt)
if m:
    s=m.end()-1; e=B.get(s)
    seg=txt[s:e+1]
    for mm in re.finditer(r'([A-Za-z0-9_$]+):"([^"]*)"',seg): rn[mm.group(1)]=mm.group(2)
print('RouteNames',rn)
route_objs=[]
for m in re.finditer(r'\bpath:"',txt):
    p=m.start()
    if p<18000: continue
    j=txt.rfind('{',max(0,p-200),p)
    if j<0: continue
    end=B.get(j)
    if end is None: continue
    obj=txt[j:end+1]
    if '__vitePreload' not in obj and 'redirect:{name:' not in obj.replace('\n','').replace(' ',''):
        if 'redirect:' not in obj: continue
    route_objs.append(dict(start=j,end=end,obj=obj))
def meta_of(obj):
    mo=re.search(r'meta:\{',obj)
    if not mo: return {}
    s=mo.end()-1; e=brackets(obj,'{','}').get(s)
    if e is None: return {}
    t=obj[s:e+1]; d={}
    for k in ['keepAlive','showMax','showFont','back','show','handleZoom','title','hideHeader','needLogin','noAuth','footer','showUser','hideBack']:
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
        if o['start']<r['start'] and o['end']>r['end'] and 'children:[' in txt[o['start']:r['start']]:
            if best is None or o['start']>best['start']: best=o
    return best
def mod_of(pos):
    for st,end,name in modranges:
        if st<=pos<=end: return name
    return 'root'
# chunk availability
basenames=set()
for m in man:
    b=os.path.basename(m['file'])
    basenames.add(b)
routes=[]
for r in route_objs:
    obj=r['obj']
    path=re.search(r'path:"([^"]*)"',obj).group(1)
    par=parent_of(r)
    nm=re.search(r'name:([A-Za-z0-9_$.]+|"[^"]*")',obj)
    rawname=nm.group(1) if nm else None
    name=rawname.strip('"') if rawname else None
    if name and name in rn: name=rn[name]
    imports=re.findall(r'import\("\./([^"]+)"\)',obj)
    preload=list(dict.fromkeys(re.findall(r'"\./([^"]+\.(?:js|css))"',obj)))
    redirect=re.search(r'redirect:\{([^}]*)\}',obj)
    comp=imports[0] if imports else None
    if not comp:
        cm=re.search(r'component:\s*([A-Za-z_$][A-Za-z0-9_$]*)',obj)
        if cm and cm.group(1)!='async': comp=cm.group(1)
    chunks=[]
    for c in ([comp] if comp and comp.endswith('.js') else [])+preload:
        base=c.split('/')[-1]
        chunks.append(dict(file=c,present=base in basenames))
    routes.append(dict(path=path,parent_path=(par and re.search(r'path:"([^"]*)"',par['obj']).group(1)),
        full_path=None,name=name,name_raw=rawname,component=comp,chunks=chunks,meta=meta_of(obj),
        redirect=(redirect.group(1) if redirect else None),
        module=mod_of(r['start']),line=txt.count('\n',0,r['start'])+1))
for r in routes:
    if r['parent_path'] and not r['parent_path'].startswith('/'): pass
    r['full_path']=('/'+r['path']) if r['path'].startswith('/') else ((r['parent_path'] or '')+'/'+r['path'])
routes.sort(key=lambda x:x['line'])
json.dump(routes,open(os.path.join(OUT,'routes.json'),'w'),ensure_ascii=False,indent=1)
print('routes',len(routes))
import collections
print(collections.Counter(r['module'] for r in routes))
miss=[c['file'] for r in routes for c in r['chunks'] if not c['present']]
print('chunks referenced',sum(len(r['chunks']) for r in routes),'missing from cache',len(set(miss)))
for r in routes: print(r['line'],r['full_path'],'|',r['name'],'|',r['module'],'|',r['component'],'|',r['meta'])
