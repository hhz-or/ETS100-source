import os,re,json,collections
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
rows=json.load(open(os.path.join(OUT,'bridge_calls.json')))
c=collections.Counter((r['plugin'],r['action']) for r in rows)
items=sorted(c.items())
for (pl,ac),n in items[80:]: print(f'{n:3d}  {pl}.{ac}')
print('--- files with bridge calls ---')
print(collections.Counter(r['file'] for r in rows))
print()
# search actionKey literal
for m in json.load(open(os.path.join(OUT,'manifest.json'))):
    if m['type']!='js' or not m.get('pretty'): continue
    txt=open(os.path.join(OUT,m['pretty']),encoding='utf-8',errors='replace').read()
    if 'actionKey' in txt:
        print('actionKey in',m['file'],txt.count('actionKey'))
