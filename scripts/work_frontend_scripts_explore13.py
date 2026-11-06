import os,struct,gzip,zlib
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
files={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3']}
for fn,off in [('data_1',57344),('data_1',4096*2),('data_2',4096*2),('data_1',8192*2)]:
    fb=files[fn]
    print('==',fn,off)
    seg=fb[off:off+120]
    print(seg.hex()[:200])
    print(''.join(chr(c) if 32<=c<127 else '.' for c in seg))
