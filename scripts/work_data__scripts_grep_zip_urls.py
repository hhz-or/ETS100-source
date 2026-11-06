import re,os
LOG=r"D:\ets-rea\ETS\logs"
def dec(b):
    try:
        s=b.decode('utf-8')
        if "\ufffd" not in s: return s
    except: pass
    return b.decode('gb18030','replace')
pat=re.compile(r"(content_\d+\.zip|template_\d+\.zip|common\.zip|pc_xst_dict\.zip|clear_cache\.zip|\.rpk|\.wpk)",re.I)
for name in ["cef_2026-11-4.log","cef_2026-10-28.log","ets_2026-11-4.log","ets_2026-10-28.log"]:
    s=dec(open(os.path.join(LOG,name),'rb').read())
    lines=s.split("\n")
    print("="*20,name,len(lines))
    n=0
    for ln in lines:
        if pat.search(ln) and re.search(r"https?://",ln):
            print(ln.strip()[:400]); n+=1
            if n>=15: break
    if n==0:
        # print any url lines with zip-ish path
        for ln in lines:
            if re.search(r"https?://[^\s]*\.zip",ln):
                print(ln.strip()[:400]); n+=1
                if n>=15: break
    print("found",n)
