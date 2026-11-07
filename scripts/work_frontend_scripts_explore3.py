import os,struct,re
base=r'ETS\temp\Cache_ETSShell\Cache'
d={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3','index']}
for n,b in d.items():
    print(n,len(b),'blocks4096=',len(b)/4096)
# locate known inline contents
pats={
 'refreshPage': b'function refreshPage(){',
 'doctype': b'<!DOCTYPE html',
 'http200': b'HTTP/1.1 200 OK',
 'appcontroller': b'cef.message',
}
for name,p in pats.items():
    for n,b in d.items():
        start=0
        cnt=0
        while True:
            i=b.find(p,start)
            if i<0: break
            print(name,n,i, 'mod4096=',i%4096)
            cnt+=1; start=i+1
            if cnt>6: break
