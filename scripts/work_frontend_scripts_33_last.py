import os,re,json
OUT=r'data/frontend'
man=json.load(open(os.path.join(OUT,'manifest.json')))
main=[m for m in man if 'index-dc0257dd' in m['file'] and m['type']=='js'][0]
lines=open(os.path.join(OUT,main['pretty']),encoding='utf-8',errors='replace').read().split('\n')
for t in ['class EtsSeverUtils','static sendMessage','AI2_dualChannelManager','function permissionInterceptor','function keepAliveInterceptor','function pageInterceptor','function resetStoreAfterRouteInterceptor','function getGeneralSlsParams','getAppConfig','class DoubleChannel','class DualChannel','sendIoFrame','audio_chunk_send_interval','pc_web_aicloud_chunk_size','connectTimeout','WS_TIMEOUT']:
    h=[i for i,l in enumerate(lines,1) if t in l]
    print(f'{t:40s} {len(h):4d} {h[:6]}')
    for i in h[:2]:
        print('    ',i,lines[i-1][:240])
