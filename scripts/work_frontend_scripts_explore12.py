import os,struct,gzip,zlib
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
files={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3']}
b=files['data_1']
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]
    if not((0<kl<3000) and (1.0e16<ct<2.0e16)): continue
    recs.append(dict(off=off,kl=kl,ds=struct.unpack_from('<4i',rec,40),da=struct.unpack_from('<4I',rec,56),key=rec[96:96+min(kl,160)].decode('latin1')))
print('entries',len(recs))
ok=0; bad=0; ext=0
for r in recs:
    for si in range(4):
        da=r['da'][si]; ds=r['ds'][si]
        if not ds: continue
        if da>>28==8:
            ext+=1; continue
        lo=da&0xFFFF; fnum=(da>>16)&0xFF; hi=(da>>24)&0xFF
        blk=lo+2
        fname='data_%d'%fnum
        if fname not in files: bad+=1; continue
        fb=files[fname]
        off=blk*4096
        if off+8>len(fb): bad+=1; continue
        if si==0:
            v=struct.unpack_from('<I',fb,off)[0]
            if v==ds-4: ok+=1
            else: bad+=1
print('header stream check: ok',ok,'bad',bad,'ext',ext)
# now for non-header streams check high byte vs size classes
import collections
pairs=[]
for r in recs:
    for si in range(4):
        da=r['da'][si]; ds=r['ds'][si]
        if not ds or da>>28==8: continue
        fnum=(da>>16)&0xFF; hi=(da>>24)&0xFF; lo=da&0xFFFF
        fb=files.get('data_%d'%fnum)
        if fb is None: continue
        off=(lo+2)*4096
        if off+8>len(fb): continue
        pairs.append((si,ds,da,hi,fnum,lo))
agg=collections.defaultdict(list)
for si,ds,da,hi,fnum,lo in pairs: agg[hi].append(ds)
for hi in sorted(agg):
    v=sorted(agg[hi])
    print('hi=0x%02x n=%d min=%d max=%d'%(hi,len(v),v[0],v[-1]))
