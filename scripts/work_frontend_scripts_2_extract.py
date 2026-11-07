import os,struct,hashlib,gzip,json,re
base=r'ETS\temp\Cache_ETSShell\Cache'
OUT=r'data/frontend'; BUND=os.path.join(OUT,'bundles'); os.makedirs(BUND,exist_ok=True)
files={i:open(os.path.join(base,'data_%d'%i),'rb').read() for i in range(4)}
BS={i:struct.unpack_from('<I',files[i],12)[0] for i in files}
b=files[1]
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]; ct=struct.unpack_from('<Q',rec,24)[0]; h=struct.unpack_from('<I',rec,0)[0]
    if not((0<kl<4000) and (1.0e16<ct<2.0e16) and h not in (0,0xffffffff)): continue
    recs.append(dict(off=off,hash=h,ct=ct,kl=kl,lk=struct.unpack_from('<I',rec,36)[0],
        ds=list(struct.unpack_from('<4i',rec,40)),da=list(struct.unpack_from('<4I',rec,56)),
        key=rec[96:96+min(kl,160)].decode('utf-8','replace')))
def rd(da,ds):
    if ds<=0: return b''
    if (da>>28)==8:
        n=da&0xFFFFFF; p=os.path.join(base,'f_%06x'%n)
        return open(p,'rb').read()[:ds] if os.path.exists(p) else None
    fnum=(da>>16)&0xFF; lo=da&0xFFFF; fb=files.get(fnum)
    if fb is None: return None
    off=8192+lo*BS[fnum]
    return fb[off:off+ds]
def parse_resp(p):
    if len(p)<28: return {}
    hlen=struct.unpack_from('<I',p,24)[0]
    txt=p[28:28+hlen].decode('latin1') if 0<hlen<=len(p)-28 else ''
    hs={}
    for line in txt.split('\x00'):
        if ':' in line:
            k,v=line.split(':',1); hs.setdefault(k.strip().lower(),v.strip())
    hs['_status']=txt.split('\x00')[0][:40]
    return hs
# resolve long keys
def longkey(lk):
    if lk>>28==8:
        n=lk&0xFFFFFF; p=os.path.join(base,'f_%06x'%n)
        return open(p,'rb').read() if os.path.exists(p) else None
    fnum=(lk>>16)&0xFF; lo=lk&0xFFFF; fb=files.get(fnum)
    if fb is None: return None
    return fb[8192+lo*BS[fnum]:]
def safe_name(url):
    u=re.sub(r'^https?://','',url)
    u=u.split('?')[0].split('#')[0]
    u=u.replace('/','__')
    u=re.sub(r'[^A-Za-z0-9_.\-]','_',u)
    return u[:150]
manifest=[]; urls=[]
for i,r in enumerate(recs):
    key=r['key']
    if r['lk'] or r['kl']>160:
        lkd=longkey(r['lk'])
        if lkd:
            s=lkd[:r['kl']].split(b'\x00')[0].decode('utf-8','replace')
            if s.startswith('http'): key=s
    hdr=rd(r['da'][0],r['ds'][0]) or b''
    resp=parse_resp(hdr)
    ctype=resp.get('content-type','')
    body=rd(r['da'][1],r['ds'][1]) if r['ds'][1]>0 else b''
    if body is None:
        manifest.append(dict(url=key,error='body_unreadable',ds=r['ds'],da=[hex(x) for x in r['da']],content_type=ctype)); continue
    enc=resp.get('content-encoding','')
    decoded=body; decompressed=False
    if body[:2]==b'\x1f\x8b':
        try:
            decoded=gzip.decompress(body); decompressed=True
        except Exception:
            try:
                decoded=gzip.GzipFile(fileobj=__import__('io').BytesIO(body)).read(); decompressed=True
            except Exception: pass
    ext='bin'
    ct=ctype.lower()
    if 'javascript' in ct: ext='js'
    elif 'css' in ct: ext='css'
    elif 'json' in ct: ext='json'
    elif 'html' in ct: ext='html'
    elif 'svg' in ct: ext='svg'
    elif ct.startswith('image/png'): ext='png'
    elif ct.startswith('image/jpeg'): ext='jpg'
    elif ct.startswith('image/gif'): ext='gif'
    elif ct.startswith('image/webp'): ext='webp'
    elif ct.startswith('font') or 'woff' in ct or 'ttf' in ct: ext='font'
    else:
        u=key.split('?')[0]; m=re.search(r'\.([a-z0-9]{2,4})$',u,re.I)
        ext=m.group(1).lower() if m else 'bin'
    name=safe_name(key)
    if not name.lower().endswith('.'+ext): name=name+'.'+ext
    outname='%03d_%s'%(i,name)
    p=os.path.join(BUND,outname)
    open(p,'wb').write(decoded)
    manifest.append(dict(index=i,url=key,file=outname,cache_file=('f_%06x'%(r['da'][1]&0xFFFFFF)) if (r['da'][1]>>28)==8 else ('data_%d@%d'%((r['da'][1]>>16)&0xFF,8192+(r['da'][1]&0xFFFF)*BS[(r['da'][1]>>16)&0xFF])),
        stored_size=len(body),size=len(decoded),gzip=decompressed,sha256=hashlib.sha256(decoded).hexdigest(),type=ext,content_type=ctype,
        status=resp.get('_status',''),headers={k:v for k,v in resp.items() if k!='_status'}))
json.dump(manifest,open(os.path.join(OUT,'manifest.json'),'w'),ensure_ascii=False,indent=1)
import collections
c=collections.Counter(m['type'] for m in manifest)
print('files',len(manifest),c)
tot=sum(m['size'] for m in manifest if 'size' in m)
print('total decoded bytes',tot)
print('errors',sum(1 for m in manifest if 'error' in m))
for m in manifest:
    if m['type'] in ('js','html','json') : print(m['type'],m['size'],m['url'][:110])
