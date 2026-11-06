import os,struct
base=r'D:\ets-rea\ETS\temp\Cache_ETSShell\Cache'
b=open(os.path.join(base,'data_3'),'rb').read()
# block at 8192, payload at 8220, size 5776
print('first',b[8220:8220+60])
# capacity 4068 -> end
print('at 12288-40:',b[12288-40:12288+60])
print('at 12316:',b[12316:12316+60])
# try payload = size? find continuation by matching sequence
first=b[8220:8220+4068]
# find where remaining 1708 bytes start: search for last 40 bytes of first
tail=first[-40:]
i=b.find(tail)
print('tail found at',i)
if i>=0: print('cont:',b[i+40:i+140])
