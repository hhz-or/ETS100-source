import re,os
paths=[r"ETS\temp\Cache_ETSShell\Cache\data_3",
       r"ETS\temp\Cache_ETSShell\Cache\f_000002",
       r"ETS\temp\Cache_ETSShell\Cache\f_000001",
       r"ETS\temp\Cache_ETSShell\Cache\f_000028"]
for p in paths:
    if not os.path.exists(p): continue
    d=open(p,'rb').read()
    print("="*20, os.path.basename(p), len(d))
    for tok in [b"setRpkPwd", b"setRpkInfo", b"rpkPwd", b"rpkpwd", b"rpksalt", b"RpkPwd"]:
        i=d.find(tok)
        if i>=0:
            print("---", tok.decode(), hex(i))
            print(d[max(0,i-500):i+700].decode('utf-8','replace'))
            break
