import re
p=r"D:\ets-rea\ETS\EtsUpdate.exe"
b=open(p,'rb').read()
i=b.find(b"ETS.db.sql")
print("ctx",repr(b[i-120:i+160]))
for tok in [b"UpdateLoginInfo", b"UpdatePop", b"C_Version", b"EnvType", b"TestVersion"]:
    offs=[m.start() for m in re.finditer(tok,b)]
    print(tok,offs[:10])
# search gbk-encoded chinese '客户端版本号'
for tok in ['客户端版本号'.encode('gbk'), '是否跳过更新提示'.encode('gbk')]:
    offs=[m.start() for m in re.finditer(re.escape(tok),b)]
    print(tok,offs[:5])
