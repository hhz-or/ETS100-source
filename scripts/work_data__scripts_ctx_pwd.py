import os
hits=[
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000014", b"Pwd"),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000012", b"pwd"),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\data_3", b"Pwd"),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000002", b"Pwd"),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000002", b"pwd"),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb\000090.log", b"pwd"),
]
for p,t in hits:
    d=open(p,'rb').read()
    print("="*30, os.path.basename(p), t)
    idx=0
    cnt=0
    while cnt<3:
        i=d.find(t,idx)
        if i<0: break
        print("@"+hex(i), d[max(0,i-500):i+500].decode('utf-8','replace').replace('\x00','.'))
        idx=i+1; cnt+=1
