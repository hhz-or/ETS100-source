import os, re, gzip

base = r"ETS\temp\Cache_ETSShell\Cache"
out = r"work/lead(未发布)"
os.makedirs(out, exist_ok=True)
kws = [b"sign_protocol_selected", b"encode_api_body", b"encode_api_resp", b"head.sign", b"ETS-SIGN",
       b"sign_protocol", b"getmd5", b"md5(", b"ets_sign", b"api_body", b"parse_api_body",
       b"checkToken", b"global_client_version", b"API_ETS"]

files = []
for f in sorted(os.listdir(base)):
    p = os.path.join(base, f)
    if not os.path.isfile(p):
        continue
    b = open(p, "rb").read()
    if b[:2] == b"\x1f\x8b":
        try:
            b = gzip.decompress(b)
        except Exception:
            continue
    files.append((f, b))

print("files loaded:", len(files), "total MB", round(sum(len(b) for _, b in files) / 1048576, 1))
for f, b in files:
    hits = {k.decode(): b.count(k) for k in kws if b.count(k)}
    if hits:
        print(f, len(b), hits)

# dump decompressed text resources for later
for f, b in files:
    if f in ("f_000002", "f_000003", "f_00000b", "f_00000e", "f_00000f", "f_000012", "f_000014",
             "f_000016", "f_000017", "f_000018", "f_000019", "f_00001b", "f_00001a", "f_00001c",
             "f_00001d", "f_000029", "f_000001"):
        open(os.path.join(out, "cache_" + f + ".txt"), "wb").write(b)
print("dumped selected resources to", out)
