import os,json
OUT=r'data/frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
lines=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read().split('\n')
def dump(name,a,b):
    out=os.path.join(OUT,'excerpts')
    with open(os.path.join(out,name),'w',encoding='utf-8',newline='\n') as f:
        for i in range(a-1,min(b,len(lines))): f.write('%6d: %s\n'%(i+1,lines[i]))
dump('etssever.txt',50740,50920)
dump('guards.txt',56440,56470)
