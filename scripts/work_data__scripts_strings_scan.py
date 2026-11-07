import re, sys, os
def strings(path, minlen=4):
    data = open(path,'rb').read()
    out=[]
    # ascii
    for m in re.finditer(rb"[\x20-\x7e]{%d,}"%minlen, data):
        out.append((m.start(), 'a', m.group().decode('latin1')))
    # utf16le
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}"%minlen, data):
        out.append((m.start(), 'w', m.group().decode('utf-16le','replace')))
    out.sort(key=lambda x:x[0])
    return out
pats = re.compile(r"(?i)password|pwd|7z|zip|extract|unzip|resources|content_|template_|passwd|解压|密码|资源")
for f in [r"ETS\ETSShell.exe", r"ETS\Ets.exe", r"ETS\EtsUpdate.exe"]:
    print("="*30, os.path.basename(f))
    items = strings(f,4)
    print("total strings:", len(items))
    for off,kind,s in items:
        if pats.search(s) and len(s)<200:
            print(f"{off:#08x} {kind} {s}")
