import os,struct,gzip,collections
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
files={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3']}
b=files['data_1']
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]
    if not((0<kl<3000) and (1.0e16<ct<2.0e16)): continue
    recs.append(dict(off=off,ds=struct.unpack_from('<4i',rec,40),da=struct.unpack_from('<4I',rec,56),key=rec[96:96+min(kl,160)].decode('latin1')))
c=collections.Counter(); oob=[]
for r in recs:
    for si in (1,2,3):
        da=r['da'][si]; ds=r['ds'][si]
        if not ds or da>>28==8: continue
        fnum=(da>>16)&0xFF; lo=da&0xFFFF; hi=(da>>24)&0xFF
        fb=files.get('data_%d'%fnum)
        if fb is None: c['nofile']+=1; continue
        off=(lo+2)*4096
        if off+ds>len(fb): c['oob']+=1; oob.append((r['key'][:70],ds,hex(da))); continue
        seg=fb[off:off+16]
        kind='other'
        if seg[:2]==b'\x1f\x8b': kind='gzip'
        elif seg[:8]==b'\x89PNG\r\n\x1a\n': kind='png'
        elif seg[:3]==b'\xff\xd8\xff': kind='jpeg'
        elif seg[:3]==b'GIF': kind='gif'
        elif all(32<=x<127 or x in (9,10,13) for x in seg): kind='text'
        elif seg[:2]==b'PK': kind='zip'
        ext=r['key'].rsplit('?')[0].rsplit('.',1)[-1].lower()
        exp='text' if ext in ('js','css','json','html','htm') else ext
        c[str((exp,kind))]+=1
for k,v in sorted(c.items()): print(k,v)
print('oob',len(oob), oob[:6])
