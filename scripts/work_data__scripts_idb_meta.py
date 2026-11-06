import sys, json
sys.path.insert(0,r"D:\ets-rea\work\data\_scripts")
import leveldb_reader as L
db=r"D:\ets-rea\ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb"
m=L.read_db(db)
meta=[(k,v) for k,(seq,typ,v,src) in m.items() if k.startswith(b'\x00\x00')]
print("meta entries:",len(meta))
for k,v in meta[:40]:
    print(k.hex()[:100], "|", len(v), "|", L.summarize(v,160))
