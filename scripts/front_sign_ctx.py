import re, os

out = r"work/lead(未发布)"
p = os.path.join(out, "cache_f_000002.txt")
b = open(p, "rb").read()
print("size", len(b))

def ctxs(pat, width=700, maxn=6):
    print("\n########", pat)
    n = 0
    for m in re.finditer(pat, b):
        s = max(0, m.start() - width // 2)
        e = min(len(b), m.end() + width // 2)
        txt = b[s:e].decode("utf-8", "replace").replace("\n", " ")
        print(f"--- off {m.start()} ---")
        print(txt)
        n += 1
        if n >= maxn:
            break
    if n == 0:
        print("(no match)")

ctxs(rb"sign_protocol_selected", 900, 2)
ctxs(rb"encode_api_body", 1200, 5)
ctxs(rb"encode_api_resp", 1200, 2)
ctxs(rb"getmd5", 600, 3)
ctxs(rb"API_ETS", 400, 4)
