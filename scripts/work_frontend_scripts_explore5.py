import os,struct,json,re
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
b=open(os.path.join(base,'data_1'),'rb').read()
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]; lk=struct.unpack_from('<I',rec,36)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]; h=struct.unpack_from('<I',rec,0)[0]
    if not((0<kl<3000) and (1.0e16<ct<2.0e16) and h not in (0,0xffffffff)): continue
    ds=struct.unpack_from('<4i',rec,40); da=struct.unpack_from('<4I',rec,56)
    recs.append((off,kl,lk,ds,da,rec[96:96+min(kl,160)]))
print('n',len(recs))
for off,kl,lk,ds,da,key in recs[:40]:
    print(off,kl,'ds',ds,'da',[hex(x) for x in da],key[:60])
