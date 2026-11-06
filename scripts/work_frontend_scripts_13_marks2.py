import os,re,json
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
p=os.path.join(OUT,main['pretty'])
txt=open(p,encoding='utf-8',errors='replace').read()
lines=txt.split('\n')
marks=['RouteNames=','RouteNames =','Object.freeze({Error','RouteNames={','logRequest','logResponse','log_collector','useUploadLogs','SoundHelper','FileHelper','EtsHelper','sndhelper','record','getUserMedia','aqcwavfile','combineandconvert','MediaRecorder','createScriptProcessor','AudioContext','wss://','exam_preparation_ise','dual_channel','evaluate','ise_cfg','signBody(','putObject','oss','aliyun','uploadLogs','report','Tracker','dcp','gdpr','sentry']
for mk in marks:
    hits=[i for i,l in enumerate(lines,1) if mk in l]
    print(f'{mk:24s} n={len(hits):4d} {hits[:10]}')
