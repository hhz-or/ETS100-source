import sys, json, collections
sys.path.insert(0,r"D:\ets-rea\work\data\_scripts")
import leveldb_reader as L
db=r"D:\ets-rea\ETS\temp\Cache_ETSShell\IndexedDB\https_statics.ets100.com_0.indexeddb.leveldb"
m=L.read_db(db)
# find schema record
for k,(seq,typ,v,src) in m.items():
    if b'currentSchema' in k:
        print("SCHEMA KEY:",k.hex())
        print(L.summarize(v,4000))
        print()
# find login-ish records
hits=[]
for k,(seq,typ,v,src) in m.items():
    txt=L.summarize(v,2000)
    if ('"token"' in txt) or ('"pwd"' in txt) or ('"account"' in txt and 'login' in txt.lower()):
        hits.append((k,v))
print("login-like records:",len(hits))
for k,v in hits[:6]:
    print("KEY",k.hex()[:80],"vlen",len(v))
    print(L.summarize(v,1200)[:1200])
    print()
# classify all values
cls=collections.Counter(); samples={}
for k,(seq,typ,v,src) in m.items():
    if k.startswith(b'\x00\x00'): c='meta_empty'
    else:
        t=L.summarize(v,120)
        if 'AudioUrl_EN' in t: c='dict_word'
        elif 'upload_file_url' in t: c='evaluate_upload_record'
        elif 'currentSchema' in t: c='schema_config'
        elif '"token"' in t or '"pwd"' in t: c='login_session'
        elif not t: c='binary_or_empty'
        else: c='other'
    cls[c]+=1
    if c not in samples and v: samples[c]=(k.hex()[:80], L.summarize(v,300))
print("classes:",dict(cls))
for c,(k,t) in samples.items(): print("SAMPLE",c,k,"|",t[:220])
