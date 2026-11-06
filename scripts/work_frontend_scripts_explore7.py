import os,struct,collections
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
files={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3']}
b=files['data_1']
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]; lk=struct.unpack_from('<I',rec,36)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]
    if not((0<kl<3000) and (1.0e16<ct<2.0e16)): continue
    recs.append((off,struct.unpack_from('<4i',rec,40),struct.unpack_from('<4I',rec,56),rec[96:96+min(kl,160)]))
sizes=collections.defaultdict(list)
for off,ds,da,key in recs:
    for i,s in enumerate(ds):
        if s: sizes[s].append((off,i))
print('distinct sizes',len(sizes))
# scan block prefixes
for fname,fb in files.items():
    print('==',fname,len(fb))
    for o in range(0,len(fb)-32,4096):
        seg=fb[o:o+32]
        vals=struct.unpack('<8I',seg)
        # heuristics: first u32 in sizes and second looks like addr
        if vals[0] in sizes:
            print(' hit',o,'u32',[hex(v) for v in vals],'size match entry idx',sizes[vals[0]][:2])
