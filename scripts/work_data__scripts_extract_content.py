import hashlib, os, subprocess, json, glob, sys
seven=r"C:\Users\***\scoop\shims\7z.exe"
root=r"D:\ets-rea\ETS\temp\resources"
out=r"D:\ets-rea\work\data\extracted\content"
os.makedirs(out, exist_ok=True)
def s(b): return b.decode('utf-8','replace').replace('\u0000','').strip()
results={}
for zp in sorted(glob.glob(os.path.join(root,"*","content_*.zip"))):
    d=open(zp,'rb').read()
    t=d[-336:]
    company=s(t[0:8]); product=s(t[144:176])
    pwd_text=s(t[16:144])
    ok = company=="MSTCHINA" and product=="EPLAT"
    m=hashlib.md5(pwd_text.encode()).hexdigest().upper()
    pw=m+hashlib.md5(m.encode()).hexdigest().upper()
    name=os.path.splitext(os.path.basename(zp))[0]
    dst=os.path.join(out,name)
    os.makedirs(dst, exist_ok=True)
    cp=subprocess.run([seven,"x",zp,"-o"+dst,"-y","-p"+pw],capture_output=True)
    okx = cp.returncode==0
    results[name]={"zip":zp,"tail_company":company,"tail_product":product,"tail_ok":ok,
                   "pwd_md5_1":m,"pwd":pw,"extract_rc":cp.returncode,"extract_ok":okx,
                   "size":len(d),"tail_len":len(t)}
open(r"D:\ets-rea\work\data\_scripts\_content_extract.json","w",encoding="utf-8").write(json.dumps(results,indent=1,ensure_ascii=False))
bad=[k for k,v in results.items() if not (v["tail_ok"] and v["extract_ok"])]
print("total",len(results),"bad",bad)
