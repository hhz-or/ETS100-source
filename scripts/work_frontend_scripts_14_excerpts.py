import os,json
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
p=os.path.join(OUT,main['pretty'])
lines=open(p,encoding='utf-8',errors='replace').read().split('\n')
def dump(name,a,b):
    out=os.path.join(OUT,'excerpts'); os.makedirs(out,exist_ok=True)
    with open(os.path.join(out,name),'w',encoding='utf-8',newline='\n') as f:
        for i in range(a-1,min(b,len(lines))):
            f.write('%6d: %s\n'%(i+1,lines[i]))
    print(name,a,b,'lines',min(b,len(lines))-a+1)
dump('routenames.txt',16600,16660)
dump('logger.txt',50950,51540)
dump('uploadlogs.txt',53400,53560)
dump('uploadlogs2.txt',55760,55840)
dump('record.txt',54400,55160)
dump('ise.txt',40950,41160)
dump('sigreq.txt',56630,56720)
dump('netcap1.txt',50740,50820)
