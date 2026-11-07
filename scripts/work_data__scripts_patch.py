p=r"data\_scripts\dump_storage.py"
s=open(p,encoding="utf-8").read()
old='SENSITIVE = re.compile(r"(token|pwd|password|phone|account|secret|key|signature|authorization|cookie|session|credential|eCard|ecard|login)", re.I)'
new='SENSITIVE = re.compile(r"(token|pwd|password|passwd|phone|mobile|account|secret|key|signature|authorization|cookie|session|credential|eCard|ecard|login|real_name|nickname|username|user_name|email|idcard|id_card|serial|mac|^ip$|device_?id|user_?id|student_no|birthday)", re.I)'
assert old in s, "pattern not found"
s=s.replace(old,new)
open(p,"w",encoding="utf-8").write(s)
print("patched")
