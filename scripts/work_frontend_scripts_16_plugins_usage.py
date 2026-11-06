import os,re,json
OUT=r'D:\ets-rea\work\frontend'; PRETTY=os.path.join(OUT,'pretty')
man=json.load(open(os.path.join(OUT,'manifest.json')))
js=[m for m in man if m['type']=='js' and m.get('pretty')]
tok=['new SndHelper','new ShellHelper','new FileHelper','new HttpHelper','new EtsHelper','new SevenZip','new SqlitePln','new AppController','new SysConfig','new ClientDB','SndHelper','combineAndConvertWavToMp3','startAQCWavFile','checkVoice','checkWov','aqcwavfile','convertfile','soundhelper','SoundHelper(']
for m in js:
    txt=open(os.path.join(OUT,m['pretty']),encoding='utf-8',errors='replace').read()
    hits={t:txt.count(t) for t in tok if t in txt}
    if hits: print(m['file'][:60], hits)
