import sys, json, re
sys.path.insert(0,r"data\_scripts")
import leveldb_reader as L
db=r"ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb"
m=L.read_db(db)
schema=None
for k,(seq,typ,v,src) in m.items():
    if 'currentSchema' in L.summarize(v,4000):
        schema=(k,v); break
if schema:
    k,v=schema
    print("SCHEMA KEY:",k.hex())
    txt=L.summarize(v,8000)
    print(txt)
jwt=re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")
hits=[]
for k,(seq,typ,v,src) in m.items():
    s=L.summarize(v,4000)
    if jwt.search(s) or 'rememberMe' in s or 'autoLogin' in s:
        hits.append((k,v,s))
print("\nJWT/login-ish records:",len(hits))
for k,v,s in hits[:8]:
    print("="*10,"KEY",k.hex()[:100],"vlen",len(v))
    print(s[:1000])
