import sqlite3, json, os, sys
p = r"ETS\localdata\ETS.db"
con = sqlite3.connect("file:" + p.replace("\\","/") + "?mode=ro", uri=True)
con.text_factory = lambda b: b.decode("utf-8", "replace")
cur = con.cursor()
out = {"file": p, "size": os.path.getsize(p), "tables": {}, "sqlite_master": []}
for row in cur.execute("select type,name,tbl_name,rootpage,sql from sqlite_master order by type,name"):
    out["sqlite_master"].append({"type":row[0],"name":row[1],"tbl_name":row[2],"rootpage":row[3],"sql":row[4]})
    if row[0] == "table" and row[4]:
        t = row[1]
        cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{t}")')]
        rows = [dict(zip(cols, r)) for r in cur.execute(f'SELECT * FROM "{t}"')]
        out["tables"][t] = {"columns": cols, "rowcount": len(rows), "rows": rows}
for t, d in out["tables"].items():
    print(f"TABLE {t}: {d['rowcount']} rows, cols={d['columns']}")
json.dump(out, open(r"data\db\ETS_db_dump.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("pragma page_size", cur.execute("pragma page_size").fetchone(), "user_version", cur.execute("pragma user_version").fetchone(), "journal", cur.execute("pragma journal_mode").fetchone())
print("encoding", cur.execute("pragma encoding").fetchone())
