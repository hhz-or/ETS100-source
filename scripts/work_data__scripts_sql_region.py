p=r"D:\ets-rea\ETS\EtsUpdate.exe"
b=open(p,'rb').read()
chunk=b[1583500:1588600]
s=chunk.decode('gb18030','replace')
print(s)
