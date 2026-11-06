import os,json,re
OUT=r'D:\ets-rea\work\frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
lines=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read().split('\n')
for t in ['uploadRecord','/m/file/pre-upload','m/file/pre-upload','ossFormData','new FormData','put(','POST','requestUpload','OssUpload','uploadAudioFile']:
    h=[i for i,l in enumerate(lines,1) if t in l]
    print(f'{t:22s} {len(h):4d} {h[:12]}')
print('--- ETS logs grep ---')
