import sqlite3, json, os
p = r"ETS\localdata\ETS.db"
con = sqlite3.connect("file:" + p.replace("\\","/") + "?mode=ro", uri=True)
cur = con.cursor()
cur.execute("select Section,Entry,Value,UpdateTime,Common,typeof(Value),typeof(Common),hex(cast(Common as blob)),hex(cast(Value as blob)) from Config")
rows=[]
for r in cur.fetchall():
    sec,ent,val,ut,com,tv,tc,hc,hv = r
    def dec(h):
        b=bytes.fromhex(h)
        try:
            return ("utf8", b.decode("utf-8"))
        except Exception:
            try: return ("gbk", b.decode("gbk"))
            except Exception: return ("raw", repr(b))
    rows.append({"Section":sec,"Entry":ent,"Value":val,"Value_hex":hv,"UpdateTime":ut,
                 "Common_decoded":dec(hc),"Common_hex":hc,"value_type":tv,"common_type":tc})
print(json.dumps(rows,ensure_ascii=False,indent=1))
json.dump(rows,open(r"data\db\ETS_db_Config_rows.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
