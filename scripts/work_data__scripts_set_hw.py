import sys,re
sys.path.insert(0,r"data\_scripts")
import leveldb_reader as L
db=r"ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb"
m=L.read_db(db)
pairs=set()
for k,(seq,typ,v,src) in m.items():
    if k.startswith(b"\x00\x01\x0a") or k.startswith(b"\x00\x01\x0d"):
        t=L.summarize(v,800)
        sids=re.findall(r"set_id\"?\s*\|?\s*|7477\d\d",t)  # crude
        s=re.findall(r"747\d{3}",t); hw=re.findall(r"1102\d{5}|1110\d{5}",t)
        if s or hw:
            pairs.add((tuple(sorted(set(s))),tuple(sorted(set(hw))),k[:4].hex()))
for p in sorted(pairs): print(p)
# also scan whole value texts for 7477xx with homework ids
allpairs=set()
for k,(seq,typ,v,src) in m.items():
    if not k.startswith(b"\x00\x01"): continue
    t=L.summarize(v,1000)
    for sid in re.findall(r"\b747\d{3}\b",t):
        for hw in re.findall(r"\b11[01]\d{6}\b",t):
            allpairs.add((sid,hw))
print(sorted(allpairs)[:40])
