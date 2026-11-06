import os,json
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
lines=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read().split('\n')
out=os.path.join(OUT,'excerpts'); os.makedirs(out,exist_ok=True)
def dump(name,a,b):
    with open(os.path.join(out,name),'w',encoding='utf-8',newline='\n') as f:
        for i in range(a-1,min(b,len(lines))): f.write('%6d: %s\n'%(i+1,lines[i]))
    print(name,min(b,len(lines))-a+1)
dump('snd1.txt',54780,54920)
dump('snd2.txt',55070,55200)
dump('snd3.txt',55230,55360)
dump('oss1.txt',51430,51560)
dump('oss2.txt',51650,51780)
dump('aqc.txt',52190,52260)
dump('up1.txt',53830,53890)
dump('up2.txt',55450,55520)
