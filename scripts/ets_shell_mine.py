import re

p = r"work/ghidra_out(未发布)\ETSShell.exe\decompiled.c"
lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
heads = [(i, l) for i, l in enumerate(lines) if l.startswith("// ====")]
print("lines", len(lines), "functions", len(heads))

def func_of(i):
    cur = None
    for h, l in heads:
        if h <= i:
            cur = (h, l)
        else:
            break
    return cur

keys = ["PlnInitiliaze", "PlnOnProcessMessage", "PlnSetParam", "rpk.iflytek.com",
        "cpk.iflytek.com", "upk.client", "ignore-certificate-errors", "disable-web-security",
        "CefRegisterSchemeHandlerFactory", "GetProcAddress", "LoadLibrary",
        "stic://", "shell.ini", "--shell-app-", "SetRpkPwd", "CreateMutex"]
for k in keys:
    idxs = [i for i, l in enumerate(lines) if k in l and not l.startswith("// ====")]
    fs = []
    for i in idxs:
        h = func_of(i)
        if h and h[1] not in fs:
            fs.append(h[1])
    print(f"{k}: {len(idxs)} refs, funcs: {fs[:8]}")

# dump the plugin loader-ish functions (those referencing PlnInitiliaze / LoadLibrary)
targets = set()
for k in ["PlnInitiliaze", "LoadLibrary", "GetProcAddress"]:
    for i, l in enumerate(lines):
        if k in l and not l.startswith("// ===="):
            h = func_of(i)
            if h:
                targets.add(h[0])
print("\nfunctions to dump:", len(targets))
out = []
for h in sorted(targets)[:8]:
    start = h
    end = start + 1
    while end < len(lines) and not lines[end].startswith("// ===="):
        end += 1
    out.append("\n".join(lines[start:min(end, start + 260)]))
open(r"work/lead(未发布)\ETSShell_loader.txt", "w", encoding="utf-8").write("\n\n".join(out))
print("wrote ETSShell_loader.txt")
