import re
p=r"ETS\EtsUpdate.exe"
b=open(p,'rb').read()
# find UTF-8/GBK strings containing CREATE TABLE
css=[m.start() for m in re.finditer(rb"CREATE TABLE", b)]
print("CREATE TABLE offsets:",css[:20])
for off in css[:6]:
    chunk=b[max(0,off-200):off+1600]
    s=chunk.decode('gb18030','replace')
    print("="*20,hex(off))
    print(s[:1400])
