import os,re,json
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
# bracket matching
match={}
st=[]
for i,c in enumerate(txt):
    if c=='{': st.append(i)
    elif c=='}':
        if st: match[st.pop()]=i
match_arr={}
st=[]
for i,c in enumerate(txt):
    if c=='[': st.append(i)
    elif c==']':
        if st: match_arr[st.pop()]=i
pats=[m.start() for m in re.finditer(r'\bpath:"',txt)]
routes=[]
for p in pats:
    # object start: nearest '{' before p
    j=txt.rfind('{',max(0,p-200),p)
    if j<0: continue
    end=match.get(j)
    if end is None: continue
    obj=txt[j:end+1]
    pm=re.search(r'path:"([^"]*)"',obj)
    if not pm: continue
    nm=re.search(r'name:([A-Za-z0-9_$.]+|"[^"]*")',obj)
    redirect=re.search(r'redirect:\{[^}]*\}',obj)
    imports=re.findall(r'import\("\./([^"]+)"\)',obj)
    preload=re.findall(r'"\./([^"]+\.(?:js|css))"',obj)
    meta=re.search(r'meta:\{',obj)
    routes.append(dict(pos=p,start=j,end=end,path=pm.group(1),
        name=(nm.group(1) if nm else None), redirect=(redirect.group(0) if redirect else None),
        imports=imports, preload=[x for x in dict.fromkeys(preload)], 
        has_meta=bool(meta), obj=obj))
print('total route-ish',len(routes))
# determine parents
def parent_of(r):
    best=None
    for o in routes:
        if o is r: continue
        if o['start']<r['start'] and o['end']>r['end']:
            # candidate container; must contain children:
            seg=txt[o['start']:r['start']]
            if 'children:[' in seg:
                if best is None or o['start']>best['start']: best=o
    return best
out=[]
for r in routes:
    par=parent_of(r)
    meta={}
    mo=re.search(r'meta:\{',r['obj'])
    if mo:
        s=mo.end()-1; e=match.get(s)
        if e: meta_txt=r['obj'][s:e+1]
        else: meta_txt=''
    else: meta_txt=''
    for k in ['keepAlive','showMax','showFont','back','show','handleZoom','title','hideHeader','showHeader']:
        v=re.search(k+r':(!\d|!0|!1|"[^"]*")',meta_txt)
        if v:
            val=v.group(1)
            meta[k]= val in ('!0',) and True or (val in ('!1',) and False) or val.strip('"')
    out.append(dict(path=r['path'],name=r['name'],parent=(par['path'] if par else None),
        component=(r['imports'][0] if r['imports'] else None),chunks=r['preload'],meta=meta,
        redirect=r['redirect'],line=txt.count('\n',0,r['start'])+1))
json.dump(out,open(os.path.join(OUT,'routes.json'),'w'),ensure_ascii=False,indent=1)
print('routes',len(out))
for r in out: print(r['line'],r['path'],'|',r['name'],'| parent=',r['parent'],'|',r['component'],'| meta',r['meta'])
