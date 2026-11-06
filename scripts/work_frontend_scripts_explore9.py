import os,re
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
for n in ['data_0','data_1','data_2','data_3']:
    b=open(os.path.join(base,n),'rb').read()
    for pat in [b'<!DOCTYPE', b'<!doctype', b'<html']:
        pos=0
        while True:
            i=b.lower().find(pat.lower(),pos)
            if i<0: break
            print(n,pat,i, b[i:i+80])
            pos=i+1
