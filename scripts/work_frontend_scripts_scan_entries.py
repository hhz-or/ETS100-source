import os,struct,re,json
base=r'ETS\temp\Cache_ETSShell\Cache'

def scan(name):
    b=open(os.path.join(base,name),'rb').read()
    hits=[]
    for off in range(0,len(b)-256,256):
        rec=b[off:off+256]
        kl=struct.unpack_from('<i',rec,32)[0]
        if not (1<=kl<=160): continue
        lk=struct.unpack_from('<I',rec,36)[0]
        if lk!=0: 
            continue
        ct=struct.unpack_from('<Q',rec,24)[0]
        if not (1.0e16 < ct < 2.0e16): continue
        h=struct.unpack_from('<I',rec,0)[0]
        if h in (0,0xffffffff): continue
        key=rec[96:96+kl]
        if not all(32<=c<127 for c in key): continue
        # require key look like path/url
        s=key.decode()
        if not (s.startswith('http') or s.startswith('/') or '/' in s): continue
        ds=struct.unpack_from('<4i',rec,40)
        da=struct.unpack_from('<4I',rec,56)
        hits.append(dict(file=name,off=off,hash=h,ct=ct,kl=kl,key=s,ds=list(ds),da=[x for x in da]))
    return hits

allh=[]
for n in ['data_0','data_1','data_2','data_3']:
    h=scan(n); print(n,len(h))
    allh+=h
print('total',len(allh))
for x in allh[:6]:
    print(x['file'],x['off'],x['kl'],x['ds'],[hex(a) for a in x['da']],x['key'][:100])
# find big data sizes
for x in allh:
    for i,v in enumerate(x['ds']):
        if v>16000:
            print('BIG',x['file'],x['off'],'stream',i,'size',v,'addr',hex(x['da'][i]),x['key'][:80])
json.dump(allh,open(r'data/frontend\scripts\entries_raw.json','w'),ensure_ascii=False)
