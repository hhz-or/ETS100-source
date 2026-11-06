import os, hashlib, json, collections

root = r"D:\ets-rea\ETS"
KEY = [
    "ETSShell.exe", "Ets.exe", "EtsUpdate.exe", "Uninstall.exe", "libcef.dll",
    "chrome_100_percent.pak", "chrome_200_percent.pak", "chrome_elf.dll",
    "d3dcompiler_47.dll", "resources.pak", "icudtl.dat", "snapshot_blob.bin",
    "v8_context_snapshot.bin", "sqlite3.dll", "7z.dll", "lame.exe", "shell.ini",
    "plugins/appcontroller/appcontroller.pln", "plugins/etshelper/etshelper.pln",
    "plugins/filehelper/filehelper.pln", "plugins/httphelper/httphelper.pln",
    "plugins/sevenzip/sevenzip.pln", "plugins/shellhelper/shellhelper.pln",
    "plugins/soundhelper/soundhelper.pln", "plugins/sqlitepln/sqlitepln.pln",
    "plugins/window_control/window_control.pln",
    "bugreport/bugreport.exe", "mq_server/ets_mq_server.exe",
    "localdata/ETS.db", "temp/Cache_ETSShell/Cookies",
    "temp/Cache_ETSShell/databases/Databases.db",
]

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

res = {}
for k in KEY:
    p = os.path.join(root, k.replace("/", os.sep))
    if os.path.isfile(p):
        res[k] = {"size": os.path.getsize(p), "sha256": sha(p)}
json.dump(res, open(r"D:\ets-rea\work\inventory_hashes.json", "w", encoding="utf-8"), indent=1)
for k, v in res.items():
    print(f"{k}\t{v['size']}\t{v['sha256']}")

# extension stats
ext = collections.Counter()
extsz = collections.Counter()
for dp, dn, fn in os.walk(root):
    for f in fn:
        p = os.path.join(dp, f)
        e = os.path.splitext(f)[1].lower() or "(none)"
        ext[e] += 1
        extsz[e] += os.path.getsize(p)
print("\n--- extension stats ---")
for e, c in ext.most_common(30):
    print(f"{e:14s} {c:5d} {extsz[e]/1048576:9.2f}MB")
