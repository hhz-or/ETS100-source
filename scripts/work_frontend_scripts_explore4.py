import os,struct
base=r'ETS\temp\Cache_ETSShell\Cache'
b=open(os.path.join(base,'data_3'),'rb').read()
print('data_3 8160..8250')
seg=b[8160:8256]
print(seg.hex())
print(''.join(chr(c) if 32<=c<127 else '.' for c in seg))
b1=open(os.path.join(base,'data_1'),'rb').read()
print('data_1 111580..111680 (before http200 @111644)')
seg=b1[111580:111700]
print(seg.hex())
print(''.join(chr(c) if 32<=c<127 else '.' for c in seg))
print()
print('data_1 @11232..11296 (before refreshPage @11264)')
seg=b1[11232:11296]
print(seg.hex())
print(''.join(chr(c) if 32<=c<127 else '.' for c in seg))
print()
print('data_2 @12288..12360 (appcontroller-ish @12325)')
b2=open(os.path.join(base,'data_2'),'rb').read()
seg=b2[12288:12360]
print(seg.hex())
print(''.join(chr(c) if 32<=c<127 else '.' for c in seg))
