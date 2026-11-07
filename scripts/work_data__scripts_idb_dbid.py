import sys, json, collections
sys.path.insert(0,r"data\_scripts")
import leveldb_reader as L
db=r"ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb"
m=L.read_db(db)
bydb=collections.Counter(); sample={}
classes=collections.Counter()
for k,(seq,typ,v,src) in m.items():
    if not k.startswith(b'\x00\x01') or len(k)<3: continue
    dbid=k[2]
    bydb[dbid]+=1
    bydb[(dbid,'osid',k[3])]+=1
    t=L.summarize(v,200)
    if 'AudioUrl_EN' in t or 'Spell_EN' in t: c='wordDict'
    elif 'upload_file_url' in t: c='mockExam/eval'
    elif 'SHM' in t or 'rememberMe' in t: c='login'
    elif not t: c='binary'
    else: c='other'
    classes[(dbid,c)]+=1
    sample.setdefault((dbid,c),(k.hex()[:60],t[:200]))
print("count by dbid:",{hex(k) if isinstance(k,int) else k:v for k,v in bydb.items() if isinstance(k,int)})
print("count by (dbid,class):")
for (dbid,c),n in sorted(classes.items(), key=lambda x:(-x[1])): print("  ",hex(dbid),c,n)
for (dbid,c),(k,t) in sample.items(): print("SAMPLE",hex(dbid),c,k,"|",t[:160])
