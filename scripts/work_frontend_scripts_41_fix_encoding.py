import os,json,glob
OUT=r'D:\ets-rea\work\frontend'
for p in glob.glob(os.path.join(OUT,'*.json')):
    raw=open(p,'rb').read()
    try:
        txt=raw.decode('utf-8'); enc='utf-8'
    except UnicodeDecodeError:
        txt=raw.decode('gbk',errors='replace'); enc='gbk'
    try:
        obj=json.loads(txt)
    except Exception as e:
        print('skip',p,e); continue
    with open(p,'w',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=1)
    print('fixed',os.path.basename(p),enc,len(raw))
