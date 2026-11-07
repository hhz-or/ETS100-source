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
# locate pickle sizes in data_1 for entries with fnum=1 headers
print('entries with da0 fnum=1:')
rows=[]
for r in recs:
    da=r['da'][0]; ds=r['ds'][0]
    if not ds or da>>28==8: continue
    fnum=(da>>16)&0xFF
    if fnum!=1: continue
    lo=da&0xFFFF; hi=(da>>24)&0xFF
    pat=struct.pack('<I',ds-4)
    locs=[i for i in range(len(b)) if b.startswith(pat,i)]
    rows.append((r['off'],lo,hi,ds,hex(da),locs[:4],r['key'][:50]))
for x in rows: print(x)
