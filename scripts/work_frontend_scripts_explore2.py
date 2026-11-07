import os,struct,json
base=r'ETS\temp\Cache_ETSShell\Cache'
b=open(os.path.join(base,'data_1'),'rb').read()
print('size',len(b),'slots',len(b)//256)
ok=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]; lk=struct.unpack_from('<I',rec,36)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]; h=struct.unpack_from('<I',rec,0)[0]
    cand = (0<kl<3000) and (1.0e16<ct<2.0e16) and h not in (0,0xffffffff)
    if cand:
        key=rec[96:96+min(kl,160)]
        ok.append((off,kl,lk,key))
print('candidates',len(ok))
bad=[x for x in ok if not all(32<=c<127 for c in x[3])]
print('nonprint',len(bad))
for x in bad[:10]: print(x[0],x[1],hex(x[2]),x[3][:60])
print('long_key entries:',[ (x[0],x[1],hex(x[2])) for x in ok if x[2]!=0][:20])
# print gaps: all offsets
offs=[x[0] for x in ok]
print('first',offs[:10],'last',offs[-5:])
