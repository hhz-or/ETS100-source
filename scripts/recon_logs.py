import os,re,json,glob,collections
root=r"ETS"
for f in glob.glob(os.path.join(root,"logs","*")):
    sz=os.path.getsize(f)
    raw=open(f,"rb").read(400000)
    # detect encoding
    enc=None
    for e in ("utf-8","gbk"):
        try: raw.decode(e); enc=e; break
        except: pass
    print(os.path.basename(f), sz, enc)
log=os.path.join(root,"logs","ets_2026-11-4.log")
data=open(log,"rb").read()
print("ets log bytes",len(data))
text=data.decode("utf-8","replace")
lines=text.split("\n")
print("lines",len(lines))
# classify prefixes
pat=collections.Counter()
for l in lines[:200000]:
    m=re.match(r"\[(\d{4}-\d\d-\d\d [\d:.]+)\] \[(\w+)\] ([\w_-]+) - ([^:]{0,40})",l)
    if m: pat[(m.group(2),m.group(3),m.group(4)[:30])]+=1
for k,v in pat.most_common(30): print(v,k)
