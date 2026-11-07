import os,struct,json
base=r'ETS\temp\Cache_ETSShell\Cache'
files={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3']}
b=files['data_1']
recs=[]
for off in range(0,len(b)-256,256):
    rec=b[off:off+256]
    kl=struct.unpack_from('<i',rec,32)[0]; lk=struct.unpack_from('<I',rec,36)[0]
    ct=struct.unpack_from('<Q',rec,24)[0]
    if not((0<kl<3000) and (1.0e16<ct<2.0e16)): continue
    recs.append(dict(off=off,kl=kl,lk=lk,ds=struct.unpack_from('<4i',rec,40),da=struct.unpack_from('<4I',rec,56),key=rec[96:96+min(kl,160)].decode('latin1')))
size2idx={}
for r in recs:
    for i,s in enumerate(r['ds']):
        if s: size2idx.setdefault(s,[]).append((r['off'],i))
found={}
for fname,fb in files.items():
    for o in range(0,len(fb)-64,4):
        sz=struct.unpack_from('<I',fb,o)[0]
        if sz not in size2idx: continue
        seg=fb[o+28:o+40]
        if seg.startswith(b'HTTP/1.1') or seg.startswith(b'HTTP/1.0'):
            idxs=size2idx[sz]
            found.setdefault(fname,[]).append((o,sz,idxs))
for fname,lst in found.items():
    print('==',fname,len(lst))
    for o,sz,idxs in lst[:15]:
        print('  loc',o,'size',sz,'entries',[(x[0],x[1]) for x in idxs], files[fname][o+28:o+60])
print()
print('total entries',len(recs))
# cross ref: for each entry with found location, print da
locmap={}
for fname,lst in found.items():
    for o,sz,idxs in lst:
        for (eoff,si) in idxs: locmap[(eoff,si)]=(fname,o)
n=0
for r in recs:
    for si in range(4):
        k=(r['off'],si)
        if k in locmap and r['ds'][si]:
            print('entry',r['off'],'stream',si,'da',hex(r['da'][si]),'ds',r['ds'][si],'->',locmap[k])
            n+=1
            if n>25: raise SystemExit
