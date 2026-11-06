import sys, json
sys.path.insert(0,r"D:\ets-rea\work\data\_scripts")
import leveldb_reader as L
db=r"D:\ets-rea\ETS\temp\Cache_ETSShell\Local Storage\leveldb"
m=L.read_db(db)
for k,(seq,typ,val,src) in m.items():
    print("KEYHEX",k.hex()[:120])
    print("  VALHEAD",val[:24].hex(), repr(val[:60]))
