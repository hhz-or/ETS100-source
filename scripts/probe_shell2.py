import re
for p in [r'ETS\logs\shell_2026-11-4.log', r'ETS\logs\shell_2026-10-28.log']:
    t=open(p,'rb').read().decode('gbk','replace')
    print('=====',p,len(t))
    for kw in ['mq_server','remote-debugging','10086','--shell-app-','launch','StartProcess','CreateProcess','plugin','.pln','upgrade']:
        ms=[l for l in t.split('\n') if kw.lower() in l.lower()]
        print(f'  {kw}: {len(ms)}')
        for l in ms[:4]: print('     ',l[:240])
