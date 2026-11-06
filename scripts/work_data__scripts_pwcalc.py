import hashlib, os, subprocess, json
p=r"D:\ets-rea\ETS\temp\resources\747716\content_811841.zip"
d=open(p,'rb').read()
t=d[-336:]
def s(b): return b.decode('utf-8','replace').replace('\u0000','').strip()
pwd_field=t[16:144]
pwd_text=s(pwd_field)
cands={}
for label,pw in [("ascii_field",pwd_text),("raw_bytes",pwd_field.decode('utf-8','replace')),("strip_null",pwd_field.replace(b'\x00',b'').decode('utf-8','replace'))]:
    m=hashlib.md5(pw.encode()).hexdigest().upper()
    cands[label+"_A"]=m
    cands[label+"_B"]=m+hashlib.md5(m.encode()).hexdigest().upper()
    cands[label+"_C"]=m+hashlib.md5(pw.encode()).hexdigest().upper()
open(r"D:\ets-rea\work\data\_scripts\_pw_cands.json","w",encoding="utf-8").write(json.dumps(cands,indent=1))
print(json.dumps({k:v for k,v in cands.items()},indent=1))
