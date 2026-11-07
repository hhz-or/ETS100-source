import os,struct,collections
base=r'ETS\temp\Cache_ETSShell\Cache'
files={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3']}
b=files['data_1']
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]
    if not((0<kl<3000) and (1.0e16<ct<2.0e16)): continue
    recs.append(dict(off=off,ds=struct.unpack_from('<4i',rec,40),da=struct.unpack_from('<4I',rec,56),key=rec[96:96+min(kl,160)].decode('latin1')))
fails=[]
for r in recs:
    da=r['da'][0]; ds=r['ds'][0]
    if not ds or da>>28==8: continue
    fnum=(da>>16)&0xFF; lo=da&0xFFFF; hi=(da>>24)&0xFF
    fb=files.get('data_%d'%fnum)
    if fb is None: continue
    off=(lo+2)*4096
    v=struct.unpack_from('<I',fb,off)[0] if off+4<=len(fb) else -1
    if v!=ds-4:
        fails.append((r['off'],fnum,lo,hi,ds,v,r['key'][:60]))
print('fails',len(fails))
c=collections.Counter((f[1],f[2]==0) for f in fails)
print(c)
for f in fails[:12]: print(f)
# look for the value ds-4 near computed offset
for f in fails[:5]:
    eoff,fnum,lo,hi,ds,v,key=f
    fb=files['data_%d'%fnum]
    pat=struct.pack('<I',ds-4)
    locs=[]
    p=0
    while True:
        i=fb.find(pat,p)
        if i<0: break
        locs.append(i); p=i+1
    print('entry',eoff,'ds',ds,'want block',lo+2,'found pickle-size at',locs[:6],'key',key[:50])
