import re
p=r"D:\ets-rea\ETS\EtsUpdate.exe"
b=open(p,'rb').read()
i=b.find(b"ETS.db.sql")
print("offset",i)
chunk=b[max(0,i-3000):i+3000]
# try utf8 then gbk
for enc in ('utf-8','gb18030'):
    try:
        s=chunk.decode(enc)
        print("=== decoded",enc,"===")
        print(s)
        break
    except Exception as e:
        print("fail",enc,e)
