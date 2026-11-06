import os,re,json
OUT=r'D:\ets-rea\work\frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
lines=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read().split('\n')
def hits(tok):
    return [i for i,l in enumerate(lines,1) if tok in l]
for t in ['useRecordInit','new WebSocket','onmessage','ENGINE_SDK','ENGINE_CODE','exam_preparation_ise','ISE_WSS','ise_wss','sendArrayBuffer','sender','pcm','16k','sample_rate','audio/L16']:
    h=hits(t)
    print(f'{t:22s} {len(h):4d} {h[:8]}')
