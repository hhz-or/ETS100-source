import os,re,json
OUT=r'data/frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
lines=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read().split('\n')
for t in ['DefaultRecordFile','wav_url','ugc','sync-v2','report-score','get-score','audio-task-submit','uploadRecord']:
    h=[i for i,l in enumerate(lines,1) if t in l]
    print(f'== {t} {len(h)} {h[:10]}')
    for i in h[:3]:
        print(f'   [{i}] {lines[i-1][:300]}')
