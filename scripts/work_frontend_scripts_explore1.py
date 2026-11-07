import os,struct
base=r'ETS\temp\Cache_ETSShell\Cache'
b=open(os.path.join(base,'data_1'),'rb').read()
rec=b[8704:8704+256]
u32=struct.unpack_from('<64I',rec,0)
for i in range(0,64,4):
    print(i, [hex(x) for x in u32[i:i+4]])
print('u64@24', struct.unpack_from('<Q',rec,24)[0])
print('key_len@32', struct.unpack_from('<i',rec,32)[0])
print('bytes 88..100:', rec[88:100].hex(), repr(rec[88:100]))
print('key at 92:', rec[92:92+80])
print('key at 95:', rec[95:95+80])
