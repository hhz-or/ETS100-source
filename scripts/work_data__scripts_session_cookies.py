import sys, json, collections
sys.path.insert(0,r"data\_scripts")
import leveldb_reader as L
db=r"ETS\temp\Cache_ETSShell\Session Storage"
m=L.read_db(db)
print("session entries:",len(m))
for k,(seq,typ,v,src) in list(m.items())[:20]:
    print("KEY",k.hex()[:100],"|",L.extract_strings(k)[:3],"| vlen",len(v),"|",L.summarize(v,160))
print()
# cookies schema
import sqlite3
p=r"ETS\temp\Cache_ETSShell\Cookies"
con=sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro",uri=True)
cur=con.cursor()
print("COOKIES schema:")
for r in cur.execute("select type,name,sql from sqlite_master order by type,name"):
    print(r)
print("meta:",list(cur.execute("select * from meta"))[:10])
print("cookie count:",cur.execute("select count(*) from cookies").fetchone())
