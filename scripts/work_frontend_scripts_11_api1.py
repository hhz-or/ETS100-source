import os,re,json
OUT=r'data/frontend'; PRETTY=os.path.join(OUT,'pretty')
main=[m for m in json.load(open(os.path.join(OUT,'manifest.json'))) if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
lines=txt.split('\n')
def find(pat):
    return [i for i,l in enumerate(lines,1) if pat in l]
for pat in ['class HYRequest','const HYRequest','HYRequest=','BASE_URL=','const BASE_URL','TIME_OUT','LoggerUtils=','const LoggerUtils','useUploadLogs=','function useUploadLogs','defineStore("','signBody(','signResponse(','etsSignatureAdapter','showLoginAuthFiledDialog','useUserInfoStore$1=','const useUserInfoStore']:
    hits=find(pat)
    print(f'{pat:26s} lines {hits[:8]} count {len(hits)}')
