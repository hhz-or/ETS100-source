import os,struct
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
idx=open(os.path.join(base,'index'),'rb').read()
print('index size',len(idx))
print('header u32:',[hex(x) for x in struct.unpack_from('<16I',idx,0)])
b=open(os.path.join(base,'data_1'),'rb').read()
# entry hashes
for off in [8704,8960,10240,10496]:
    h=struct.unpack_from('<I',b,off)[0]
    print('entry off',off,'hash',hex(h))
    pat=struct.pack('<I',h)
    pos=idx.find(pat)
    while pos>=0 and pos<len(idx):
        print('  idx hit at',pos,'ctx',idx[pos:pos+40].hex())
        pos2=idx.find(pat,pos+1)
        if pos2==pos: break
        pos=pos2
        if pos<0: break
