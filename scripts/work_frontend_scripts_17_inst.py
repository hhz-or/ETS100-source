import os,re,json
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
lines=txt.split('\n')
def show(tok,maxn=12):
    hits=[i for i,l in enumerate(lines,1) if tok in l]
    print(f'== {tok} -> {hits[:maxn]}')
    for i in hits[:4]:
        print(f'   [{i}] {lines[i-1][:260]}')
for t in ['new SndHelper','new ShellHelper','new FileHelper','new HttpHelper','new EtsHelper','new SevenZip','new SqlitePln','new AppController','new ClientDB']:
    show(t)
