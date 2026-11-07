import os,re,json
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
main=[m for m in json.load(open(os.path.join(OUT,'manifest.json'))) if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
print('main pretty lines',txt.count(chr(10))+1,'chars',len(txt))
for pat in ['cef.message','sendMessage','setMessageCallback','createGuid','actionKey','createRouter','createWebHistory','createWebHashHistory','defineStore','createPinia','baseURL','axios','interceptors','getUserMedia','MediaRecorder','FormData','lame','mp3','wav','.upload','collect-rangers','sentry','reportLog','log_data']:
    print(f'{pat:22s}',txt.count(pat))
