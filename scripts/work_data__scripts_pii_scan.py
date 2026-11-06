import os,re,json
D=r"D:\ets-rea\work\data"
ACCT=re.compile(r"SHM3\d{7,}"); PHONE=re.compile(r"1[3-9]\d{9}"); JWT=re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.")
bad=[]
for dp,dn,fn in os.walk(D):
    for f in fn:
        p=os.path.join(dp,f)
        try: b=open(p,'rb').read()
        except: continue
        hits={}
        for name,rx in (("acct",ACCT),("phone",PHONE),("jwt",JWT)):
            m=rx.findall(b.decode('utf-8','ignore'))
            if m: hits[name]=m[:3]
        if hits: bad.append((os.path.relpath(p,D),hits))
print("files with potential raw PII:",len(bad))
for x in bad[:30]: print(x)
