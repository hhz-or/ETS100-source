import os,re,glob,collections
base=r'D:\ets-rea\ETS\logs'
p=os.path.join(base,'ets_2026-11-4.log')
txt=open(p,'rb').read().decode('utf-8','replace')
lines=txt.split('\n')
print('total lines',len(lines))
tags=collections.Counter(re.findall(r'\[(API_ETS|PLG_STIC|ENG_SCORE|MISC|ENGINE|UPGRADE|SYS)\]',txt))
print('tags',dict(tags))
n=0
for l in lines:
    if 'key_id' in l or 'ets_sign' in l:
        print('SIGN:',l.strip()[:400]); n+=1
        if n>=6: break
print()
n=0
for l in lines:
    if 'PLG_STIC' in l and ('record' in l):
        print('REC:',l.strip()[:300]); n+=1
        if n>=8: break
print()
n=0
for l in lines:
    if 'ENG_SCORE' in l and ('最终选择SDK' in l or '评测' in l):
        print('ENG:',l.strip()[:300]); n+=1
        if n>=6: break
print()
n=0
for l in lines:
    if 'API_ETS' in l and 'request' in l:
        print('API:',l.strip()[:300]); n+=1
        if n>=6: break
