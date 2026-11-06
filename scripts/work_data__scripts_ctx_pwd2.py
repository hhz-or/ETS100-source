import os
hits=[
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000014", b"Pwd", 4),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000012", b"pwd", 4),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\data_3", b"Pwd", 3),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000002", b"Pwd", 3),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\Cache\f_000002", b"pwd", 3),
 (r"D:\ets-rea\ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb\000090.log", b"pwd", 5),
]
o=open(r"D:\ets-rea\work\data\_scripts\_ctx_pwd_out.txt","w",encoding="utf-8")
for p,t,n in hits:
    d=open(p,'rb').read()
    print("="*30, os.path.basename(p), t, file=o)
    idx=0; cnt=0
    while cnt<n:
        i=d.find(t,idx)
        if i<0: break
        print("@"+hex(i), repr(d[max(0,i-500):i+500])[:2000], file=o)
        idx=i+1; cnt+=1
o.close()
