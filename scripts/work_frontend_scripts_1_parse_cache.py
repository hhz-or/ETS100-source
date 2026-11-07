import os,struct,hashlib,gzip,json,re,io
base=r'ETS\temp\Cache_ETSShell\Cache'
OUT=r'data/frontend'
BUND=os.path.join(OUT,'bundles')
os.makedirs(BUND,exist_ok=True)
files={}
for i in range(4):
    p=os.path.join(base,'data_%d'%i)
    files[i]=open(p,'rb').read()
def blocksize(i):
    fb=files[i]
    v=struct.unpack_from('<I',fb,12)[0]
    return v if v in (36,256,512,1024,2048,4096,8192) else 4096
BS={i:blocksize(i) for i in files}
print('block sizes',BS,{i:len(files[i]) for i in files})
b=files[1]
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]
    h=struct.unpack_from('<I',rec,0)[0]
    if not((0<kl<3000) and (1.0e16<ct<2.0e16) and h not in (0,0xffffffff)): continue
    d=dict(off=off,hash=h,ct=ct,kl=kl,lk=struct.unpack_from('<I',rec,36)[0],
           ds=list(struct.unpack_from('<4i',rec,40)),da=list(struct.unpack_from('<4I',rec,56)))
    d['key']=rec[96:96+min(kl,160)].decode('utf-8','replace')
    recs.append(d)
print('entries',len(recs))
def ext_num(addr): return addr & 0xFFFFFF
def read_stream(da,ds):
    if ds<=0: return b''
    if (da>>28)==8:
        n=ext_num(da)
        p=os.path.join(base,'f_%06x'%n)
        if not os.path.exists(p): return None
        data=open(p,'rb').read()
        return data[:ds]
    fnum=(da>>16)&0xFF; lo=da&0xFFFF
    fb=files.get(fnum)
    if fb is None: return None
    off=8192+lo*BS[fnum]
    return fb[off:off+ds]
def parse_resp(pickle):
    if len(pickle)<28: return None
    payload=struct.unpack_from('<I',pickle,0)[0]
    flags=struct.unpack_from('<I',pickle,4)[0]
    rt=struct.unpack_from('<Q',pickle,8)[0]; st=struct.unpack_from('<Q',pickle,16)[0]
    hlen=struct.unpack_from('<I',pickle,24)[0]
    hdrs=pickle[28:28+hlen].decode('latin1') if 0<hlen<len(pickle) else ''
    return dict(payload=payload,flags=flags,response_time=st,headers=hdrs)
entries=[]
for r in recs:
    key=r['key']
    hdr=read_stream(r['da'][0],r['ds'][0]) or b''
    resp=parse_resp(hdr)
    entries.append(dict(key=key,off=r['off'],hash=r['hash'],ct=r['ct'],lk=r['lk'],
        ds=r['ds'],da=[hex(x) for x in r['da']],resp=resp))
json.dump(entries,open(os.path.join(OUT,'cache_entries.json'),'w'),ensure_ascii=False,indent=1)
# quick stats
print('with resp',sum(1 for e in entries if e['resp']))
print('sample headers')
print(entries[0]['resp']['headers'][:400])
