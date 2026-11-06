import json,os
OUT=r'D:\ets-rea\work\frontend'
m=json.load(open(os.path.join(OUT,'manifest.json')))
m.sort(key=lambda x:-x.get('size',0))
for x in m[:12]: print(x['size'],x['type'],x['file'],x['url'][:100])
print('---html---')
for x in m:
    if x['type']=='html': print(x['size'],x['file'][:70],x['url'][:90])
