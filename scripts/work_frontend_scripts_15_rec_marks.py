import os,re,json
OUT=r'data/frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
txt=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read()
lines=txt.split('\n')
marks=['startRecord','stopRecord','recordStart','recordStop','onRecord','Recorder','recorder','SoundHelper','speex','Speex','checkvoice','aqc','loadfile','RecordMedia','mediaRecord','getUserMedia','audio/wav','audio/mp3','wavfile','convertWav','mergeWav','uploadAudio','audio_upload','OSS','oss_config','ossConfig','signature','policy','callback']
for mk in marks:
    hits=[i for i,l in enumerate(lines,1) if mk in l]
    print(f'{mk:14s} n={len(hits):4d} {hits[:8]}')
print()
# sndhelper file
sd=[m for m in man if 'sndhelper' in m['file']]
print('sndhelper manifest',sd[0]['file'] if sd else None)
