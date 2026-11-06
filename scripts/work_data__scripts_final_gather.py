import os,json,sqlite3,collections,re
# BuryPoint.db
p=r"D:\ets-rea\ETS\bugreport\localdata\BuryPoint.db"
con=sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro",uri=True)
c=con.cursor()
out={"file":p,"size":os.path.getsize(p),"tables":{}}
for (t,) in c.execute("select name from sqlite_master where type='table'"):
    cols=[x[1] for x in c.execute(f'PRAGMA table_info("{t}")')]
    rows=[dict(zip(cols,r)) for r in c.execute(f'select * from "{t}"')]
    out["tables"][t]={"columns":cols,"rowcount":len(rows),"rows":rows[:50]}
open(r"D:\ets-rea\work\data\db\BuryPoint_db_dump.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=1))
print("BuryPoint tables:",{k:(v['rowcount'],v['columns']) for k,v in out['tables'].items()})

# common.zip structure
e=r"D:\ets-rea\work\data\extracted\common"
ext=collections.Counter(); dirs=collections.Counter(); files=[]
for dp,dn,fn in os.walk(e):
    for f in fn:
        fp=os.path.join(dp,f); rel=os.path.relpath(fp,e)
        files.append((rel,os.path.getsize(fp)))
        ext[os.path.splitext(f)[1].lower()]+=1
        dirs[os.path.dirname(rel) or "."]+=1
print("common: files",len(files),"dirs",dict(dirs),"ext",dict(ext))
print("largest 8:",sorted(files,key=lambda x:-x[1])[:8])
# list all filenames for doc artifact
json.dump({"files":[{"path":a,"size":b} for a,b in sorted(files)],"ext":dict(ext),"dirs":dict(dirs)},
          open(r"D:\ets-rea\work\data\resources_common_index.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)

# pc_xst_dict structure
d=json.load(open(r"D:\ets-rea\work\data\extracted\pc_xst_dict\pc_xst_dict.json",encoding="utf-8"))
print("pc_xst_dict type:",type(d).__name__)
if isinstance(d,dict):
    ks=list(d.keys()); print("keys:",len(ks),ks[:12])
    k0=ks[0]; v=d[k0]; print("sample",k0,"->",json.dumps(v,ensure_ascii=False)[:400] if not isinstance(v,(int,float)) else v)
    if isinstance(v,dict): print("entry keys:",list(v.keys()))
if isinstance(d,list):
    print("len",len(d),"sample",json.dumps(d[0],ensure_ascii=False)[:500])
json.dump(d if isinstance(d,list) else {k:d[k] for k in list(d)[:5]}, open(r"D:\ets-rea\work\data\resources_dict_sample.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)

# search Ets.exe / ETSShell for CREATE TABLE
for f in [r"D:\ets-rea\ETS\Ets.exe",r"D:\ets-rea\ETS\ETSShell.exe",r"D:\ets-rea\ETS\EtsUpdate.exe"]:
    b=open(f,'rb').read()
    for tok in [b"CREATE TABLE",b"ETS.db.sql",b"CREATE  TABLE",b"INSERT INTO"]:
        i=b.find(tok)
        print(os.path.basename(f),tok,i)
