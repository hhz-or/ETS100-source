import os,re,glob,collections
base=r'D:\ets-rea\ETS\logs'
pat=re.compile(r'(actionKey|sendMessage|soundhelper|etshelper|shellhelper|filehelper|encode_api_body|sign_version|key_id|评测|record)')
for p in sorted(glob.glob(os.path.join(base,'ets_*.log'))):
    txt=open(p,'rb').read().decode('utf-8','replace')
    print('==',os.path.basename(p),len(txt))
    cnt=collections.Counter()
    for m in pat.finditer(txt):
        cnt[m.group(1)]+=1
    print(dict(cnt))
    # sample lines with actionKey or sendMessage
    n=0
    for line in txt.split('\n'):
        if 'actionKey' in line or 'sendMessage' in line:
            print('  ',line.strip()[:220]); n+=1
            if n>=6: break
