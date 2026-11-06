import os,re,json,collections
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
def brack(s,op,cl):
    mm={};st=[]
    for i,c in enumerate(s):
        if c==op: st.append(i)
        elif c==cl and st: mm[st.pop()]=i
    return mm
B=brack(txt,'{','}'); A=brack(txt,'[',']')
modranges=[]
for m in re.finditer(r'([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\[\s*\{',txt):
    st=m.start(0)+m.group(0).rfind('['); end=A.get(st)
    if end: modranges.append((st,end,m.group(1)))
def mod_of(pos):
    for st,end,name in modranges:
        if st<=pos<=end: return name
    return 'main-router'
objs=[]
for m in re.finditer(r'\bpath:"',txt):
    p=m.start()
    if p<18000: continue
    j=txt.rfind('{',max(0,p-200),p)
    if j<0: continue
    end=B.get(j)
    if end is None: continue
    obj=txt[j:end+1]
    if '__vitePreload' not in obj and 'redirect:' not in obj: continue
    if 'RouterView' in obj or 'matched:' in obj or 'routeRecord' in obj: continue
    objs.append((j,end,obj))
def meta_of(obj):
    mo=re.search(r'meta:\{',obj)
    if not mo: return {}
    s=mo.end()-1; e=brack(obj,'{','}').get(s)
    if e is None: return {}
    t=obj[s:e+1]; d={}
    for k in ['keepAlive','showMax','showFont','back','show','handleZoom','title','hideHeader','needLogin','noAuth','footer']:
        mm=re.search(k+r':(!0|!1|"[^"]*"|\d+)',t)
        if mm:
            v=mm.group(1)
            d[k]= True if v=='!0' else False if v=='!1' else (v[1:-1] if v.startswith('"') else int(v))
    return d
def par_of(j,end):
    best=None
    for oj,oend,oobj in objs:
        if oj<j and oend>end and 'children:[' in txt[oj:j]:
            if best is None or oj>best[0]: best=(oj,oend,oobj)
    return best
routes=[]
for j,end,obj in objs:
    path=re.search(r'path:"([^"]*)"',obj).group(1)
    par=par_of(j,end)
    parpath=re.search(r'path:"([^"]*)"',par[2]).group(1) if par else None
    nm=re.search(r'name:([A-Za-z0-9_$.]+|"[^"]*")',obj)
    rawname=nm.group(1) if nm else None
    name=rawname.strip('"') if rawname else None
    rn={'RouteNames.Error':'error','RouteNames.AppStart':'appStart','RouteNames.Startup':'startup','RouteNames.SystemMessage':'systemMessage','RouteNames.Login':'login'}
    name=rn.get(name,name)
    imports=re.findall(r'import\("\./([^"]+)"\)',obj)
    chunks=list(dict.fromkeys(re.findall(r'"\./([^"]+\.(?:js|css))"',obj)))
    comp=imports[0] if imports else None
    if not comp:
        cm=re.search(r'component:\s*([A-Za-z_$][A-Za-z0-9_$]*)',obj)
        if cm and cm.group(1)!='async': comp=cm.group(1)
    rdy=re.search(r'redirect:\{([^}]*)\}',obj)
    full = path if path.startswith('/') else ((parpath or '')+'/'+path)
    routes.append(dict(path=path,parent_path=parpath,full_path=full,name=name,name_raw=rawname,
        component=comp,chunks=chunks,meta=meta_of(obj),
        redirect=rdy.group(1).strip() if rdy else None,module=mod_of(j),
        line=txt.count('\n',0,j)+1))
routes.sort(key=lambda x:x['line'])
allchunks=collections.OrderedDict()
for r in routes:
    for c in ([r['component']] if r['component'] and r['component'].endswith('.js') else [])+r['chunks']:
        allchunks.setdefault(c,[]).append(r['path'])
basenames=set(os.path.basename(m['file']) for m in man)
for c in allchunks:
    allchunks[c]=dict(routes=allchunks[c],present=os.path.basename(c) in basenames)
out=dict(summary=dict(total=len(routes),
    module_routes=sum(1 for r in routes if r['module'] not in ('main-router',)),
    router_routes=sum(1 for r in routes if r['module']=='main-router'),
    distinct_chunks=len(allchunks),chunks_present_in_cache=sum(1 for v in allchunks.values() if v['present']),
    chunks_missing=sum(1 for v in allchunks.values() if not v['present'])),
  routes=routes,chunks=allchunks)
json.dump(out,open(os.path.join(OUT,'routes.json'),'w'),ensure_ascii=False,indent=1)
print(json.dumps(out['summary'],ensure_ascii=False))
for r in routes[:3]+routes[-3:]: print(r['line'],r['full_path'],r['name'],r['module'],r['meta'])
