import sys,json,re,hashlib
sys.path.insert(0,r"data\_scripts")
import leveldb_reader as L
db=r"ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb"
m=L.read_db(db)
JWT=re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")
ACCT=re.compile(r"SHM\d+")
for k,(seq,typ,v,src) in m.items():
    if k.startswith(b"\x00\x01\x02"):
        t=L.summarize(v,2000)
        t=JWT.sub("eyJ***REDACTED",t); t=ACCT.sub("SHM*******",t)
        print(k.hex(), "| vlen",len(v), "| klass", ("delete" if typ==0 else "value"))
        print("  ",t[:600])
        print()
