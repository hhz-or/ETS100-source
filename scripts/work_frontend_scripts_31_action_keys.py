import os,re,json,collections
OUT=r'data/frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
files=[m['file'] for m in man]
d=json.load(open(os.path.join(OUT,'routes.json')))
present=0
for c,v in d['chunks'].items():
    base=os.path.basename(c)
    hit=any(base in f for f in files)
    v['present']=hit
    present+=1 if hit else 0
d['summary']['chunks_present_in_cache']=present
d['summary']['chunks_missing']=len(d['chunks'])-present
json.dump(d,open(os.path.join(OUT,'routes.json'),'w'),ensure_ascii=False,indent=1)
print('chunks',len(d['chunks']),'present',present)
# ---- action keys ----
bridges=json.load(open(os.path.join(OUT,'bridge_calls.json')))
# enrich with method name & channel uid suffix
PRETTY=os.path.join(OUT,'pretty')
byfile=collections.defaultdict(list)
for b in bridges: byfile[b['file']].append(b)
out=[]
for f,lst in byfile.items():
    p=os.path.join(PRETTY,f)
    if not os.path.exists(p):
        # find matching pretty file
        cand=[x for x in os.listdir(PRETTY) if x==f]
        if cand: p=os.path.join(PRETTY,cand[0])
    lines=open(p,encoding='utf-8',errors='replace').read().split('\n') if os.path.exists(p) else []
    for b in lst:
        ln=b['line']
        method=None; cls=None
        for i in range(ln-1,max(0,ln-60),-1):
            if i>=len(lines): continue
            l=lines[i]
            mm=re.search(r'prototype\.([A-Za-z0-9_$]+)\s*=\s*function',l)
            if mm and not method: method=mm.group(1)
            cm=re.search(r'\bclass\s+([A-Za-z0-9_$]+)',l)
            if cm and not cls: cls=cm.group(1)
            if method and cls: break
        # params: look back for JSON.stringify(var) and var={...}
        params=None
        line_txt=lines[ln-1] if ln-1<len(lines) else ''
        pm=re.search(r'sendMessage\([^,]+,\s*"[^"]+",\s*"[^"]+",\s*(.+)\)\s*$',line_txt)
        if pm:
            arg=pm.group(1)
            sm=re.search(r'JSON\.stringify\(\s*([A-Za-z0-9_$]+)\s*\)',arg)
            if sm:
                var=sm.group(1)
                ctx='\n'.join(lines[max(0,ln-25):ln])
                mm2=re.search(r'\b'+re.escape(var)+r'\s*=\s*\{',ctx)
                if mm2:
                    s=ctx.find('{',mm2.start())
                    seg=ctx[s:s+400]
                    params=seg.split(';')[0][:300]
            if params is None: params=arg[:200]
        out.append(dict(plugin=b['plugin'],action=b['action'],method=method or None,
            cls=cls, uid_suffix=None, params=params, file=f, line=ln))
# uid suffix from createGuid()+"@..."
for o in out:
    o['action_key']=o['plugin']+'.'+o['action']
out.sort(key=lambda x:(x['plugin'],x['action']))
res=dict(summary=dict(total_actions=len(out),plugins=sorted(set(o['plugin'] for o in out)),
    actions_per_plugin=dict(collections.Counter(o['plugin'] for o in out))),
    actions=out)
json.dump(res,open(os.path.join(OUT,'action_keys.json'),'w'),ensure_ascii=False,indent=1)
print(json.dumps(res['summary'],ensure_ascii=False))
for o in out[:6]: print(o)
