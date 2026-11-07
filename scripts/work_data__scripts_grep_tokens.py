import os,re
root=r"ETS"
toks=[b"setRpkPwd",b"setRpkInfo",b"downloadresource",b"rpkPwd",b"rpkpwd",b"pwd",b"Pwd",b"811841",b"template_686",b"747716"]
skip_ext={'.dll','.exe','.dat','.pak','.bin','.wav','.mp3','.png','.jpg','.db','.zip','.7z','.spx','.pln','.log'}  # logs handled separately
out=open(r"data\logs\grep_pwd_hits.txt","w",encoding="utf-8")
for dp,dn,fn in os.walk(root):
    for f in fn:
        p=os.path.join(dp,f)
        ext=os.path.splitext(f)[1].lower()
        if ext in skip_ext and ext!='.log': continue
        try:
            if os.path.getsize(p)>60_000_000: continue
            d=open(p,'rb').read()
        except OSError: continue
        for t in toks:
            i=d.find(t)
            if i>=0:
                out.write(f"==== {os.path.relpath(p,root)} :: {t.decode()} @ {i:#x}\n")
                out.write(d[max(0,i-300):i+400].decode('utf-8','replace').replace('\r',' ')+"\n\n")
out.close()
print("done")
