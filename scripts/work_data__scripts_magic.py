import os,binascii
d=r"ETS\soundfiles"
for f in sorted(os.listdir(d))[:9]:
    p=os.path.join(d,f)
    b=open(p,'rb').read(40)
    print(f, len(open(p,'rb').read()), b[:16].hex(), repr(b[:16]))
