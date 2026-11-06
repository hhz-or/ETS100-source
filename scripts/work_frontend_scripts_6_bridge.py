import os,re,json,collections
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
jsfiles=[m for m in man if m['type']=='js' and m.get('pretty')]
# bridge sendMessage patterns
pat=re.compile(r'sendMessage\(\s*([A-Za-z0-9_$.]+)\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"')
pat2=re.compile(r'setMessageCallback\(\s*([A-Za-z0-9_$.]+)\s*,')
rows=[]; actions=collections.Counter()
for m in jsfiles:
    p=os.path.join(OUT,m['pretty'])
    try: lines=open(p,encoding='utf-8',errors='replace').read().split('\n')
    except: continue
    for i,line in enumerate(lines,1):
        for mo in pat.finditer(line):
            rows.append(dict(file=os.path.basename(m['file']),line=i,uid=mo.group(1),plugin=mo.group(2),action=mo.group(3)))
            actions[(mo.group(2),mo.group(3))]+=1
print('sendMessage calls',len(rows),'distinct plugin/action',len(actions))
json.dump(rows,open(os.path.join(OUT,'bridge_calls.json'),'w'),ensure_ascii=False,indent=1)
for (pl,ac),c in sorted(actions.items()):
    print(f'{c:3d}  {pl}.{ac}')
