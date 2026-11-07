import sys, os, json, binascii
sys.path.insert(0,r"data\_scripts")
import leveldb_reader as L
db=r"ETS\temp\Cache_ETSShell\Local Storage\leveldb"
m=L.read_db(db)
print("entries:",len(m))
rows=[]
for k,(seq,typ,val,src) in sorted(m.items(), key=lambda x:-x[1][0]):
    rows.append({"key_hex":k.hex(),"key_text":L.extract_strings(k)[:3],
                 "val_hex_head":val[:80].hex(),"val_len":len(val),
                 "val_text":L.summarize(val), "src":src,"seq":seq,"typ":typ})
open(r"data\_scripts\_ls_dump.json","w",encoding="utf-8").write(json.dumps(rows,ensure_ascii=False,indent=1))
for r in rows[:60]:
    print(r["key_text"], "|", r["val_len"], "|", r["val_text"][:180])
