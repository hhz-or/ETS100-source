import os, collections
d=r"D:\ets-rea\ETS\soundfiles"
rows=[]
for f in sorted(os.listdir(d)):
    if f.endswith(".mp3"):
        p=os.path.join(d,f); sp=p+".spx"; xp=os.path.splitext(p)[0]+".xml"
        mp3=os.path.getsize(p); spx=os.path.getsize(sp) if os.path.exists(sp) else 0
        rows.append((f.split("_")[1][:8], len(open(p,'rb').read()), mp3, spx, os.path.getsize(xp) if os.path.exists(xp) else 0))
print("mp3 sizes:",sorted(collections.Counter(r[2] for r in rows).items()))
print("spx sizes:",sorted(collections.Counter(r[3] for r in rows).items()))
for r in rows: print(r)
