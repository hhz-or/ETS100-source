import os, re
root = r"D:\ets-rea\ETS"
needles = [b"RpkPwd", b"CpkPwd", b"rpkPwd", b"cpkPwd", b"RpkPwd".replace(b"R",b"r")]
hits=[]
for dp,dn,fn in os.walk(root):
    for f in fn:
        p=os.path.join(dp,f)
        try:
            sz=os.path.getsize(p)
        except OSError: continue
        if sz>60_000_000: continue
        try: data=open(p,'rb').read()
        except OSError: continue
        for n in [b"RpkPwd", b"pkPwd", b"rpk", b"cpk"]:
            idx=0
            c=0
            while True:
                i=data.find(n, idx)
                if i<0 or c>=5: break
                ctx=data[max(0,i-120):i+160]
                hits.append((p, n.decode(), i, ctx))
                idx=i+1; c+=1
for p,n,i,ctx in hits:
    print("="*20, os.path.relpath(p,root), n, hex(i))
    try: print(ctx.decode('utf-8','replace'))
    except: print(repr(ctx))
