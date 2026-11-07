#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static PE scan for ETS native layer (read-only on target).
Outputs per-binary: meta.json, exports.json, imports.json, strings.txt
"""
import sys, os, re, json, hashlib, math, struct, datetime, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pylib'))
import pefile

OUT_ROOT = r"data/native"

TARGETS = [
    ("ETSShell",            r"ETS\ETSShell.exe"),
    ("Ets",                 r"ETS\Ets.exe"),
    ("EtsUpdate",           r"ETS\EtsUpdate.exe"),
    ("bugreport",           r"ETS\bugreport\bugreport.exe"),
    ("ets_mq_server",       r"ETS\mq_server\ets_mq_server.exe"),
    ("appcontroller",       r"ETS\plugins\appcontroller\appcontroller.pln"),
    ("etshelper",           r"ETS\plugins\etshelper\etshelper.pln"),
    ("filehelper",          r"ETS\plugins\filehelper\filehelper.pln"),
    ("httphelper",          r"ETS\plugins\httphelper\httphelper.pln"),
    ("sevenzip",            r"ETS\plugins\sevenzip\sevenzip.pln"),
    ("shellhelper",         r"ETS\plugins\shellhelper\shellhelper.pln"),
    ("soundhelper",         r"ETS\plugins\soundhelper\soundhelper.pln"),
    ("sqlitepln",           r"ETS\plugins\sqlitepln\sqlitepln.pln"),
    ("window_control",      r"ETS\plugins\window_control\window_control.pln"),
]

MACHINE = {0x14c: "i386 (x86)", 0x8664: "AMD64", 0x1c0: "ARM", 0xaa64: "ARM64",
           0x200: "IA64", 0x1c4: "ARMNT", 0x14d: "i860"}

SUBSystem = {1: "NATIVE", 2: "WINDOWS_GUI", 3: "WINDOWS_CUI", 5: "OS2_CUI",
             7: "POSIX_CUI", 9: "WINDOWS_CE_GUI", 10: "EFI_APPLICATION",
             11: "EFI_BOOT_SERVICE_DRIVER", 12: "EFI_RUNTIME_DRIVER"}

# Rich header prodid -> likely toolchain family (public mapping, inference only)
PRODID = {
    0x00: "Unknown/0", 0x01: "Import0", 0x02: "Linker510", 0x03: "Cvtomf510",
    0x04: "Linker600", 0x05: "Cvtomf600", 0x06: "Cvtres500", 0x07: "Utc11_Basic",
    0x08: "Utc11_C", 0x09: "Utc12_Basic", 0x0A: "Utc12_C", 0x0B: "Utc12_CPP",
    0x0C: "AliasObj60", 0x0D: "VisualBasic60", 0x0E: "Masm613", 0x0F: "Masm710",
    0x10: "Linker511", 0x11: "Cvtomf511", 0x12: "Masm614", 0x13: "Linker512",
    0x14: "Cvtomf512", 0x15: "Utc12_C_Std", 0x16: "Utc12_CPP_Std",
    0x17: "Utc12_C_Book", 0x18: "Utc12_CPP_Book", 0x19: "Implib700",
    0x1A: "Cvtomf700", 0x1B: "Utc13_Basic", 0x1C: "Utc13_C", 0x1D: "Utc13_CPP",
    0x1E: "Linker610", 0x1F: "Cvtomf610", 0x20: "Linker601", 0x21: "Cvtomf601",
    0x22: "Utc12_1_Basic", 0x23: "Utc12_1_C", 0x24: "Utc12_1_CPP",
    0x25: "Linker620", 0x26: "Cvtomf620", 0x27: "AliasObj70", 0x28: "Linker621",
    0x29: "Cvtomf621", 0x2A: "Masm615", 0x2B: "Utc13_LTCG_C", 0x2C: "Utc13_LTCG_CPP",
    0x2D: "Masm620", 0x2E: "ILAsm100", 0x2F: "Utc12_2_Basic", 0x30: "Utc12_2_C",
    0x31: "Utc12_2_CPP", 0x32: "Utc12_2_C_Std", 0x33: "Utc12_2_CPP_Std",
    0x34: "Utc12_2_C_Book", 0x35: "Utc12_2_CPP_Book", 0x36: "Implib622",
    0x37: "Cvtomf622", 0x38: "Cvtres501", 0x39: "Utc13_C_Std", 0x3A: "Utc13_CPP_Std",
    0x3B: "Cvtpgd1300", 0x3C: "Linker622", 0x3D: "Linker700", 0x3E: "Export622",
    0x3F: "Export700", 0x40: "Masm700", 0x41: "Utc13_POGO_I_C", 0x42: "Utc13_POGO_I_CPP",
    0x43: "Utc13_POGO_O_C", 0x44: "Utc13_POGO_O_CPP", 0x45: "Cvtres700",
    0x46: "Cvtres710p", 0x47: "Linker710p", 0x48: "Cvtomf710p", 0x49: "Export710p",
    0x4A: "Implib710p", 0x4B: "Masm710p", 0x4C: "Utc1310p_C", 0x4D: "Utc1310p_CPP",
    0x4E: "Utc1310p_C_Std", 0x4F: "Utc1310p_CPP_Std", 0x50: "Utc1310p_LTCG_C",
    0x51: "Utc1310p_LTCG_CPP", 0x52: "Utc1310p_POGO_I_C", 0x53: "Utc1310p_POGO_I_CPP",
    0x54: "Utc1310p_POGO_O_C", 0x55: "Utc1310p_POGO_O_CPP", 0x56: "Linker624",
    0x57: "Cvtomf624", 0x58: "Export624", 0x59: "Implib624", 0x5A: "Linker710",
    0x5B: "Cvtomf710", 0x5C: "Export710", 0x5D: "Implib710", 0x5E: "Cvtres710",
    0x5F: "Utc1310_C", 0x60: "Utc1310_CPP", 0x61: "Utc1310_C_Std", 0x62: "Utc1310_CPP_Std",
    0x63: "Utc1310_LTCG_C", 0x64: "Utc1310_LTCG_CPP", 0x65: "Utc1310_POGO_I_C",
    0x66: "Utc1310_POGO_I_CPP", 0x67: "Utc1310_POGO_O_C", 0x68: "Utc1310_POGO_O_CPP",
    0x69: "AliasObj710", 0x6A: "AliasObj710p", 0x6B: "Cvtpgd1310",
    0x6C: "Cvtpgd1310p", 0x6D: "Utc1400_C", 0x6E: "Utc1400_CPP", 0x6F: "Utc1400_C_Std",
    0x70: "Utc1400_CPP_Std", 0x71: "Utc1400_LTCG_C", 0x72: "Utc1400_LTCG_CPP",
    0x73: "Utc1400_POGO_I_C", 0x74: "Utc1400_POGO_I_CPP", 0x75: "Utc1400_POGO_O_C",
    0x76: "Utc1400_POGO_O_CPP", 0x77: "Cvtpgd1400", 0x78: "Linker800",
    0x79: "Cvtomf800", 0x7A: "Export800", 0x7B: "Implib800", 0x7C: "Cvtres800",
    0x7D: "Masm800", 0x7E: "AliasObj800", 0x7F: "PhoenixPrerelease",
    0x80: "Utc1400_CVTCIL_C", 0x81: "Utc1400_CVTCIL_CPP", 0x82: "Utc1400_LTCG_MSIL",
    0x83: "Utc1500_C", 0x84: "Utc1500_CPP", 0x85: "Utc1500_C_Std", 0x86: "Utc1500_CPP_Std",
    0x87: "Utc1500_CVTCIL_C", 0x88: "Utc1500_CVTCIL_CPP", 0x89: "Utc1500_LTCG_C",
    0x8A: "Utc1500_LTCG_CPP", 0x8B: "Utc1500_LTCG_MSIL", 0x8C: "Utc1500_POGO_I_C",
    0x8D: "Utc1500_POGO_I_CPP", 0x8E: "Utc1500_POGO_O_C", 0x8F: "Utc1500_POGO_O_CPP",
    0x90: "Cvtpgd1500", 0x91: "Linker900", 0x92: "Export900", 0x93: "Implib900",
    0x94: "Cvtres900", 0x95: "Masm900", 0x96: "AliasObj900", 0x97: "Resource900",
    0x98: "AliasObj1000", 0x9A: "Cvtres1000", 0x9B: "Export1000", 0x9C: "Implib1000",
    0x9D: "Linker1000", 0x9E: "Masm1000", 0x9F: "Utc1600_C", 0xA0: "Utc1600_CPP",
    0xA1: "Utc1600_CVTCIL_C", 0xA2: "Utc1600_CVTCIL_CPP", 0xA3: "Utc1600_LTCG_C",
    0xA4: "Utc1600_LTCG_CPP", 0xA5: "Utc1600_LTCG_MSIL", 0xA6: "Utc1600_POGO_I_C",
    0xA7: "Utc1600_POGO_I_CPP", 0xA8: "Utc1600_POGO_O_C", 0xA9: "Utc1600_POGO_O_CPP",
    0xAA: "Utc1700_C", 0xAB: "Utc1700_CPP", 0xAC: "Utc1700_CVTCIL_C",
    0xAD: "Utc1700_CVTCIL_CPP", 0xAE: "Utc1700_LTCG_C", 0xAF: "Utc1700_LTCG_CPP",
    0xB0: "Utc1700_LTCG_MSIL", 0xB1: "Utc1700_POGO_I_C", 0xB2: "Utc1700_POGO_I_CPP",
    0xB3: "Utc1700_POGO_O_C", 0xB4: "Utc1700_POGO_O_CPP", 0xB5: "AliasObj1010",
    0xB6: "Cvtres1010", 0xB7: "Export1010", 0xB8: "Implib1010", 0xB9: "Linker1010",
    0xBA: "Masm1010", 0xBB: "Utc1800_C", 0xBC: "Utc1800_CPP", 0xBD: "Utc1800_CVTCIL_C",
    0xBE: "Utc1800_CVTCIL_CPP", 0xBF: "Utc1800_LTCG_C", 0xC0: "Utc1800_LTCG_CPP",
    0xC1: "Utc1800_LTCG_MSIL", 0xC2: "Utc1800_POGO_I_C", 0xC3: "Utc1800_POGO_I_CPP",
    0xC4: "Utc1800_POGO_O_C", 0xC5: "Utc1800_POGO_O_CPP", 0xC6: "AliasObj1100",
    0xC7: "Cvtres1100", 0xC8: "Export1100", 0xC9: "Implib1100", 0xCA: "Linker1100",
    0xCB: "Masm1100", 0xCC: "Utc1900_C", 0xCD: "Utc1900_CPP", 0xCE: "Utc1900_CVTCIL_C",
    0xCF: "Utc1900_CVTCIL_CPP", 0xD0: "Utc1900_LTCG_C", 0xD1: "Utc1900_LTCG_CPP",
    0xD2: "Utc1900_LTCG_MSIL", 0xD3: "Utc1900_POGO_I_C", 0xD4: "Utc1900_POGO_I_CPP",
    0xD5: "Utc1900_POGO_O_C", 0xD6: "Utc1900_POGO_O_CPP",
}

def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return round(-sum((v / n) * math.log2(v / n) for v in c.values()), 4)

def rva2off(pe, rva):
    try:
        return pe.get_offset_from_rva(rva)
    except Exception:
        return None

def parse_rich(data):
    """Parse Rich header manually; return entries and key."""
    if len(data) < 0x80:
        return None
    m = re.search(rb"Rich", data[:0x400])
    if not m:
        return None
    rich_off = m.start()
    # key is the 4 bytes right after 'Rich'
    key = struct.unpack_from("<I", data, rich_off + 4)[0]
    # find 'DanS' marker: DanS ^ key
    dans = struct.pack("<I", 0x536E6144 ^ key)
    start = data.find(dans, 0, rich_off)
    if start < 0:
        return None
    entries = []
    p = start + 16  # skip DanS + 3 padding dwords
    while p + 8 <= rich_off:
        compid, count = struct.unpack_from("<II", data, p)
        # every dword in the record is XOR-obfuscated with the key
        compid ^= key
        count ^= key
        if compid == 0 and count == 0:
            p += 8
            continue
        prodid = (compid >> 16) & 0xFFFF
        build = compid & 0xFFFF
        entries.append({
            "prodid": prodid,
            "prodid_name": PRODID.get(prodid, "Unknown/0x%X" % prodid),
            "build": build,
            "count": count,
        })
        p += 8
    return {"key": "0x%08X" % key, "entries": entries,
            "offset": rich_off, "dans_offset": start}

STR_ASCII = re.compile(rb"[\x20-\x7e]{6,}")
STR_UTF16 = re.compile(rb"(?:[\x20-\x7e]\x00){6,}")

NOISE = {
    "0123456789", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz",
    "0123456789ABCDEF", "0123456789abcdef",
}

def extract_strings(data):
    out = {}
    for m in STR_ASCII.finditer(data):
        s = m.group().decode("latin-1")
        if s not in out:
            out[s] = (m.start(), "A")
    for m in STR_UTF16.finditer(data):
        s = m.group().decode("utf-16le", "ignore")
        if s not in out:
            out[s] = (m.start(), "W")
    return out

RE_ACTION = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
RE_HEX = re.compile(r"^[0-9a-fA-F]+$")
RE_PATH = re.compile(r"[A-Za-z]:\\|\\\\[A-Za-z0-9._-]+\\|(?:^|[\\/])(?:[\w.-]+[\\/]){2,}")
RE_URL = re.compile(r"(?:https?|ftp|ws|wss)://|www\.[A-Za-z0-9.-]+", re.I)
RE_DLL = re.compile(r"^[\w.+-]+\.(dll|exe|pln|pyd|ocx|sys|node|pak|dat|bin|ini|json|xml|db|sqlite|log|txt)$", re.I)
CRYPTO_KW = ["md5", "sha1", "sha256", "sha512", "hmac", "base64", "rsa", "aes",
             "des", "rc4", "crc32", "secret", "privatekey", "publickey", "sign",
             "signature", "encrypt", "decrypt", "cipher", "nonce", "salt",
             "password", "passwd", "token", "appkey", "app_key", "apikey", "api_key",
             "checksum", "digest", "x509", "certificate", "pkcs"]
CEF_KW = ["cef", "libcef", "chromium", "CefBrowser", "CefFrame", "CefString",
          "cefclient", "cef_settings", "CefApp", "CefClient", "on_console_message",
          "OnBeforeCommandLineProcessing"]
STIC_KW = ["STIC", "stic", "PlnInit", "PlnOn", "PlnGet", "PlnRelease", "plugin"]

def classify(s):
    tags = []
    low = s.lower()
    if RE_URL.search(s):
        tags.append("url")
    if RE_PATH.search(s):
        tags.append("path")
    if RE_ACTION.match(s):
        tags.append("action")
    if RE_DLL.match(s):
        tags.append("module")
    if any(k in low for k in CRYPTO_KW):
        tags.append("crypto")
    if any(k.lower() in low for k in CEF_KW):
        tags.append("cef")
    if "stic" in low or low.startswith("pln"):
        tags.append("stic")
    if s.startswith(".?A"):
        tags.append("rtti")
    return tags

def score(s, tags):
    sc = 0
    if "url" in tags: sc += 6
    if "action" in tags: sc += 6
    if "crypto" in tags: sc += 5
    if "rtti" in tags: sc += 4
    if "path" in tags: sc += 3
    if "module" in tags: sc += 2
    if "cef" in tags: sc += 2
    if 8 <= len(s) <= 160: sc += 1
    if RE_HEX.match(s) and len(s) >= 32: sc += 2
    if len(s) > 400: sc -= 3
    return sc

def demangle_rtti(s):
    m = re.match(r"^\.\?A([VUW])(.+?)(?:@@|@)$", s)
    if not m:
        return None
    body = m.group(2)
    parts = [p for p in body.split("@") if p]
    return "::".join(reversed(parts))

def get_version_info(pe):
    info = {}
    if not hasattr(pe, "FileInfo"):
        return info
    try:
        for f in pe.FileInfo:
            for ff in f:
                if getattr(ff, "Key", b"") == b"StringFileInfo":
                    for st in ff.StringTable:
                        for k, v in st.entries.items():
                            try:
                                kk = k.decode("utf-8", "ignore") if isinstance(k, bytes) else str(k)
                                vv = v.decode("utf-8", "ignore") if isinstance(v, bytes) else str(v)
                            except Exception:
                                continue
                            info[kk] = vv
    except Exception as e:
        info["_error"] = str(e)
    return info

def get_res_types(pe):
    out = []
    if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
        return out
    for e in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        name = e.name.decode("utf-8", "ignore") if e.name is not None else None
        rid = e.id
        n = 0
        try:
            for x in e.directory.entries:
                n += 1
        except Exception:
            pass
        out.append({"id": rid, "name": name, "children": n})
    return out

def main():
    os.makedirs(OUT_ROOT, exist_ok=True)
    summary = []
    for name, path in TARGETS:
        if not os.path.isfile(path):
            print("MISSING", path)
            continue
        data = open(path, "rb").read()
        sha = hashlib.sha256(data).hexdigest()
        pe = pefile.PE(data=data, fast_load=False)
        od = {}
        outdir = os.path.join(OUT_ROOT, name)
        os.makedirs(outdir, exist_ok=True)

        fh = pe.FILE_HEADER
        oh = pe.OPTIONAL_HEADER
        ts = fh.TimeDateStamp
        try:
            ts_utc = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            ts_utc = "?"
        dllchars = oh.DllCharacteristics
        secs = []
        for s in pe.sections:
            raw = s.get_data()
            secs.append({
                "name": s.Name.rstrip(b"\x00").decode("latin-1"),
                "va": "0x%08X" % s.VirtualAddress,
                "vsize": s.Misc_VirtualSize,
                "raw_ptr": "0x%08X" % s.PointerToRawData,
                "raw_size": s.SizeOfRawData,
                "chars": "0x%08X" % s.Characteristics,
                "entropy": entropy(raw),
            })

        # exports
        exports = []
        export_dir = None
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            ed = pe.DIRECTORY_ENTRY_EXPORT.struct
            export_dir = {"name": getattr(pe.DIRECTORY_ENTRY_EXPORT, "name", None),
                          "dll_name_raw": getattr(ed, "Name", None)}
            if isinstance(export_dir["name"], bytes):
                export_dir["name"] = export_dir["name"].decode("utf-8", "ignore")
            for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                nm = sym.name.decode("utf-8", "ignore") if sym.name else None
                exports.append({
                    "ordinal": sym.ordinal,
                    "name": nm,
                    "rva": "0x%08X" % sym.address,
                    "va": "0x%08X" % (oh.ImageBase + sym.address) if sym.address else None,
                    "forwarder": sym.forwarder.decode("utf-8", "ignore") if sym.forwarder else None,
                })

        # imports
        imports = []
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) or []:
            fns = []
            for imp in entry.imports:
                fns.append({
                    "name": imp.name.decode("utf-8", "ignore") if imp.name else None,
                    "ordinal": imp.ordinal if imp.name is None else None,
                    "iat_rva": "0x%08X" % imp.address,
                })
            imports.append({"dll": entry.dll.decode("utf-8", "ignore"), "functions": fns})
        delay = []
        for entry in getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", []) or []:
            fns = []
            for imp in entry.imports:
                fns.append({
                    "name": imp.name.decode("utf-8", "ignore") if imp.name else None,
                    "ordinal": imp.ordinal if imp.name is None else None,
                })
            delay.append({"dll": entry.dll.decode("utf-8", "ignore"), "functions": fns})

        # debug / pdb
        debug = []
        for d in getattr(pe, "DIRECTORY_ENTRY_DEBUG", []) or []:
            rec = {"type": d.struct.Type, "size": d.struct.SizeOfData,
                   "addr_rva": "0x%08X" % d.struct.AddressOfRawData,
                   "raw_ptr": "0x%08X" % d.struct.PointerToRawData}
            if d.struct.Type == 2 and hasattr(d, "entry"):
                e = d.entry
                pdb = getattr(e, "PdbFileName", None)
                if isinstance(pdb, bytes):
                    pdb = pdb.rstrip(b"\x00").decode("latin-1", "ignore")
                rec["pdb"] = pdb
                rec["pdb_age"] = getattr(e, "PdbAge", None)
                sig = getattr(e, "PdbSignature", None)
                if isinstance(sig, bytes):
                    rec["pdb_guid"] = sig.hex()
                rec["timestamp"] = getattr(e, "PdbRaw_FeatureSig", None)
            debug.append(rec)

        rich = parse_rich(data)
        vinfo = get_version_info(pe)
        restypes = get_res_types(pe)
        sec_dir = [{"idx": i, "rva": "0x%08X" % dd.VirtualAddress, "size": dd.Size}
                   for i, dd in enumerate(oh.DATA_DIRECTORY) if dd.Size]

        raw_strings = extract_strings(data)
        items = []
        for s, (off, enc) in raw_strings.items():
            tags = classify(s)
            items.append((score(s, tags), off, s, enc, tags))
        items.sort(key=lambda x: (-x[0], x[1]))
        kept = items[:3000]
        kept.sort(key=lambda x: x[1])

        actions = sorted({s for s, (o, e) in raw_strings.items() if RE_ACTION.match(s)})
        urls = sorted({s for s, (o, e) in raw_strings.items() if RE_URL.search(s)})
        rtti = []
        for s in raw_strings:
            if s.startswith(".?A"):
                rtti.append({"mangled": s, "demangled": demangle_rtti(s)})
        rtti.sort(key=lambda r: r["mangled"])
        crypto_strs = sorted({s for s in raw_strings if any(k in s.lower() for k in CRYPTO_KW)})
        pdb_strs = sorted({s for s in raw_strings if ".pdb" in s.lower()})
        cef_strs = sorted({s for s in raw_strings if any(k.lower() in s.lower() for k in CEF_KW)})

        meta = {
            "file": path,
            "name": name,
            "size": len(data),
            "sha256": sha,
            "machine": MACHINE.get(fh.Machine, "0x%X" % fh.Machine),
            "machine_raw": "0x%04X" % fh.Machine,
            "timestamp": ts,
            "timestamp_utc": ts_utc,
            "characteristics": "0x%04X" % fh.Characteristics,
            "is_dll": bool(fh.Characteristics & 0x2000),
            "is_exe": not bool(fh.Characteristics & 0x2000),
            "image_base": "0x%08X" % oh.ImageBase,
            "entry_point_rva": "0x%08X" % oh.AddressOfEntryPoint,
            "size_of_image": oh.SizeOfImage,
            "size_of_headers": oh.SizeOfHeaders,
            "checksum": "0x%08X" % oh.CheckSum,
            "subsystem": SUBSystem.get(oh.Subsystem, str(oh.Subsystem)),
            "subsystem_raw": oh.Subsystem,
            "os_version": "%d.%d" % (oh.MajorOperatingSystemVersion, oh.MinorOperatingSystemVersion),
            "image_version": "%d.%d" % (oh.MajorImageVersion, oh.MinorImageVersion),
            "subsystem_version": "%d.%d" % (oh.MajorSubsystemVersion, oh.MinorSubsystemVersion),
            "linker": "%d.%d" % (oh.MajorLinkerVersion, oh.MinorLinkerVersion),
            "dll_characteristics": "0x%04X" % dllchars,
            "security": {
                "aslr": bool(dllchars & 0x40),
                "dep_nx": bool(dllchars & 0x100),
                "no_seh": bool(dllchars & 0x400),
                "cfg_guard": bool(dllchars & 0x4000),
                "high_entropy_va": bool(dllchars & 0x20),
                "dynamic_base": bool(dllchars & 0x40),
                "terminal_server_aware": bool(dllchars & 0x8000),
            },
            "authenticode": None,
            "sections": secs,
            "file_entropy": entropy(data),
            "data_directories": sec_dir,
            "export_dir": export_dir,
            "exports_count": len(exports),
            "exports": exports,
            "imports": imports,
            "imports_count": sum(len(i["functions"]) for i in imports),
            "delay_imports": delay,
            "debug": debug,
            "rich": rich,
            "version_info": vinfo,
            "resources": restypes,
            "rtti_classes": rtti,
            "action_candidates": actions,
            "urls": urls,
            "crypto_strings": crypto_strs,
            "pdb_strings": pdb_strs,
            "cef_strings": cef_strs[:200],
            "string_stats": {"total": len(raw_strings), "kept": len(kept)},
        }
        # authenticode presence
        try:
            secidx = pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]
            dd = oh.DATA_DIRECTORY[secidx]
            meta["authenticode"] = {"rva": "0x%08X" % dd.VirtualAddress, "size": dd.Size}
        except Exception:
            pass

        json.dump(meta, open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        json.dump({"file": path, "sha256": sha, "image_base": meta["image_base"],
                   "export_dir": export_dir, "exports": exports},
                  open(os.path.join(outdir, "exports.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        json.dump({"file": path, "sha256": sha, "imports": imports,
                   "delay_imports": delay},
                  open(os.path.join(outdir, "imports.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

        with open(os.path.join(outdir, "strings.txt"), "w", encoding="utf-8") as f:
            f.write("# %s  sha256=%s\n# %d unique strings found; %d kept (len>=6, ranked)\n"
                    % (name, sha, len(raw_strings), len(kept)))
            cur = None
            for sc, off, s, enc, tags in kept:
                if enc != cur:
                    f.write("\n=== encoding: %s ===\n" % ("ASCII" if enc == "A" else "UTF-16LE"))
                    cur = enc
                t = (" [" + ",".join(tags) + "]") if tags else ""
                f.write("0x%08X\t%s%s\n" % (off, s, t))

        summary.append({
            "name": name, "file": path, "size": len(data),
            "machine": meta["machine"], "is_dll": meta["is_dll"],
            "timestamp_utc": ts_utc, "linker": meta["linker"],
            "file_entropy": meta["file_entropy"],
            "exports": len(exports), "imports": meta["imports_count"],
            "import_dlls": [i["dll"] for i in imports],
            "pdb": (debug[0].get("pdb") if debug and debug[0].get("type") == 2 else None),
            "rtti": len(rtti), "actions": len(actions),
            "strings_total": len(raw_strings),
            "authenticode": bool(meta.get("authenticode") and meta["authenticode"]["size"]),
        })
        print("OK", name, "exports=%d imports=%d actions=%d rtti=%d" %
              (len(exports), meta["imports_count"], len(actions), len(rtti)))

    json.dump(summary, open(os.path.join(OUT_ROOT, "_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("summary written")

if __name__ == "__main__":
    main()
