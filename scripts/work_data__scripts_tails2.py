import hashlib, os, json
def show(p):
    d=open(p,'rb').read()
    tail=d[-336:]; tail40=d[-40:]
    def s(b): return b.decode('utf-8','replace').replace('\x00','').strip()
    return {"file":os.path.basename(p),"size":len(d),
          "tail336":{"company":s(tail[0:8]),"version":s(tail[8:16]),
                     "pwd_hex":tail[16:144].hex(),"pwd_text":s(tail[16:144]),
                     "productid":s(tail[144:176]),
                     "keySerialNum":s(tail[176:304]),"thisAnswer":s(tail[304:336])},
          "tail40_hex":tail40.hex(),"tail40_text":s(tail40)}
files=[r"ETS\temp\resources\747716\content_811841.zip",
       r"ETS\temp\resources\747716\template_686.zip",
       r"ETS\temp\resources\common.zip",
       r"ETS\temp\resources\pc_xst_dict.zip",
       r"ETS\temp\resources\clear_cache.zip"]
res=[show(f) for f in files]
open(r"data\_scripts\_tails.json","w",encoding="utf-8").write(json.dumps(res,ensure_ascii=False,indent=1))
