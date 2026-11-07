import os,struct
base=r'ETS\temp\Cache_ETSShell\Cache'
files={n:open(os.path.join(base,n),'rb').read() for n in ['data_0','data_1','data_2','data_3']}
targets=[b'Content-Length: 3481698',b'Content-Length: 375097',b'Content-Length: 48929',b'Content-Length: 86879']
for t in targets:
    print('==',t)
    for n,b in files.items():
        pos=0
        while True:
            i=b.find(t,pos)
            if i<0: break
            print('  ',n,i,'blk',i//4096,'off_in_blk',i%4096)
            pos=i+1
