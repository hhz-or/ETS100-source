import os, collections
d=r"D:\ets-rea\ETS\soundfiles"
spx=[f for f in sorted(os.listdir(d)) if f.endswith(".spx")]
print("count",len(spx))
print("first bytes:",collections.Counter(open(os.path.join(d,f),'rb').read(1).hex() for f in spx))
print("first 2:",collections.Counter(open(os.path.join(d,f),'rb').read(2).hex() for f in spx))
print("last 4:",collections.Counter(open(os.path.join(d,f),'rb').read()[-4:].hex() for f in spx))
for f in spx[:6]:
    b=open(os.path.join(d,f),'rb').read()
    print(f[-20:], len(b), b[:12].hex(), b[-8:].hex())
