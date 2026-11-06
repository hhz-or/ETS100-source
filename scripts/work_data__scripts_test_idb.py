import sys, json, collections
sys.path.insert(0,r"D:\ets-rea\work\data\_scripts")
import leveldb_reader as L
db=r"D:\ets-rea\ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb"
m=L.read_db(db)
print("IDB entries:",len(m))
pref=collections.Counter()
keys=sorted(m.items(), key=lambda x:-len(x[1][2]))
for k,(seq,typ,val,src) in m.items():
    pref[k[:2].hex()]+=1
print("prefix 2 bytes:",dict(pref))
# print 30 longest-value records
for k,(seq,typ,val,src) in keys[:12]:
    print("="*20,"keyhex",k[:48].hex(),"len",len(k),"vlen",len(val))
    print("  keytext:",L.extract_strings(k)[:5])
    print("  valtext:",L.summarize(val,300))
