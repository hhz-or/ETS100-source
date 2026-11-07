import sys, json
sys.path.insert(0,r"data\_scripts")
import leveldb_reader as L
db=r"ETS\temp\Cache_ETSShell\Local Storage\leveldb"
m=L.read_db(db)
for k,(seq,typ,val,src) in m.items():
    print("KEYHEX",k.hex()[:120])
    print("  VALHEAD",val[:24].hex(), repr(val[:60]))
