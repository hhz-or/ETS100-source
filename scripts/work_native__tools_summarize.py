#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a compact overview of all scanned binaries for report writing."""
import os, json, re, collections

ROOT = r"D:\ets-rea\work\native"
BINS = ["ETSShell", "Ets", "EtsUpdate", "bugreport", "ets_mq_server",
        "appcontroller", "etshelper", "filehelper", "httphelper", "sevenzip",
        "shellhelper", "soundhelper", "sqlitepln", "window_control"]

SEC_API = ["IsDebuggerPresent", "CheckRemoteDebuggerPresent", "NtQueryInformationProcess",
           "OutputDebugStringA", "OutputDebugStringW", "VirtualProtect", "VirtualAlloc",
           "CreateToolhelp32Snapshot", "Process32First", "Process32Next", "TerminateProcess",
           "CryptAcquireContext", "CryptHashData", "CryptEncrypt", "CryptDecrypt",
           "BCrypt", "WinHttpOpen", "InternetOpen", "URLDownloadToFile", "HttpSendRequest",
           "CreateProcess", "ShellExecuteEx", "WinExec", "RegSetValue", "RegOpenKey",
           "OpenProcess", "ReadProcessMemory", "WriteProcessMemory", "SetWindowsHookEx",
           "GetAsyncKeyState", "CreateFileMapping", "MapViewOfFile", "OpenFileMapping",
           "LoadLibraryA", "LoadLibraryW", "LoadLibraryExW", "GetProcAddress", "GetModuleFileName"]

lines = ["# ETS native layer overview (generated)", ""]
for name in BINS:
    d = os.path.join(ROOT, name)
    mp = os.path.join(d, "meta.json")
    if not os.path.exists(mp):
        continue
    m = json.load(open(mp, encoding="utf-8"))
    lines.append("## %s" % name)
    lines.append("- file: `%s`" % m["file"])
    lines.append("- size: %d  sha256: %s" % (m["size"], m["sha256"]))
    lines.append("- machine: %s  dll=%s  subsystem=%s  linker=%s  ts=%s" %
                 (m["machine"], m["is_dll"], m["subsystem"], m["linker"], m["timestamp_utc"]))
    lines.append("- image_base: %s  entry: %s  file_entropy: %s  checksum: %s" %
                 (m["image_base"], m["entry_point_rva"], m["file_entropy"], m["checksum"]))
    lines.append("- security: " + json.dumps(m["security"]))
    lines.append("- authenticode dir: " + json.dumps(m.get("authenticode")))
    vs = m.get("version_info") or {}
    keep = ["FileVersion", "ProductVersion", "ProductName", "FileDescription", "CompanyName",
            "OriginalFilename", "InternalName", "LegalCopyright", "Comments", "FileVersion"]
    lines.append("- version_info: " + json.dumps({k: vs.get(k) for k in keep if k in vs}, ensure_ascii=False))
    lines.append("- sections: " + ", ".join("%s(va=%s sz=%d ent=%s)" %
                 (s["name"], s["va"], s["raw_size"], s["entropy"]) for s in m["sections"]))
    rich = m.get("rich") or {}
    if rich:
        ents = ["%s(build %d x%d)" % (e["prodid_name"], e["build"], e["count"]) for e in rich["entries"]]
        lines.append("- rich: key=%s entries=%s" % (rich["key"], ", ".join(ents)))
    dbg = m.get("debug") or []
    if dbg:
        lines.append("- debug: " + json.dumps(dbg, ensure_ascii=False))
    lines.append("- exports(%d): %s" % (m["exports_count"],
                 ", ".join("%s@%s(ord %s)" % (e["name"], e["rva"], e["ordinal"]) for e in m["exports"][:40])
                 if m["exports_count"] <= 40 else
                 ", ".join("%s@%s" % (e["name"], e["rva"]) for e in m["exports"][:40]) + " ..."))
    if m["exports_count"] > 40:
        names = [e["name"] for e in m["exports"] if e["name"]]
        json.dump({"name": name, "exports": m["exports"]},
                  open(os.path.join(d, "exports.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    # imports
    imp_summary = []
    flagged = []
    for i in m["imports"]:
        imp_summary.append("%s(%d)" % (i["dll"], len(i["functions"])))
        for f in i["functions"]:
            fn = f["name"] or ("ord_%s" % f["ordinal"])
            for api in SEC_API:
                if fn == api or fn.startswith(api):
                    flagged.append("%s!%s" % (i["dll"], fn))
    lines.append("- imports: " + ", ".join(imp_summary))
    if flagged:
        lines.append("- security/API imports: " + ", ".join(sorted(set(flagged))))
    if m.get("delay_imports"):
        lines.append("- delay imports: " + ", ".join("%s(%d)" % (d2["dll"], len(d2["functions"]))
                                                    for d2 in m["delay_imports"]))
    # rtti
    rtti = [r["demangled"] or r["mangled"] for r in m.get("rtti_classes", [])]
    if rtti:
        interesting = [r for r in rtti if re.search(r"Sti|Plugin|Pln|Cef|Json|Sqlite|Http|Sound|Audio|Window|Pln", r, re.I)]
        lines.append("- rtti(%d, interesting %d): %s" % (len(rtti), len(interesting),
                     "; ".join(sorted(set(interesting))[:60])))
        json.dump({"name": name, "rtti": rtti},
                  open(os.path.join(d, "rtti_classes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    # log handlers from dispatch.json
    dp = os.path.join(d, "dispatch.json")
    if os.path.exists(dp):
        r = json.load(open(dp, encoding="utf-8"))
        methods = set()
        classes = set()
        for f in r["functions"]:
            for l in f.get("log_handlers", []):
                classes.add(l["class"]); methods.add(l["method"])
        lines.append("- log classes: " + ", ".join(sorted(classes)))
        lines.append("- log methods(%d): %s" % (len(methods), ", ".join(sorted(methods))))
        p = r.get("plnonprocess")
        if p:
            lines.append("- dispatcher @%s insns=%d" % (p["rva"], p["insn_count"]))
            lines.append("- action keys: " + ", ".join(p["action_candidates"]))
    lines.append("")
lines.append("## cross-binary interesting strings")
urls = set()
for name in BINS:
    m = json.load(open(os.path.join(ROOT, name, "meta.json"), encoding="utf-8"))
    urls.update(m.get("urls") or [])
lines.append("URLS: " + ", ".join(sorted(urls)[:80]))

open(os.path.join(ROOT, "_overview.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("wrote", os.path.join(ROOT, "_overview.md"), len(lines), "lines")
