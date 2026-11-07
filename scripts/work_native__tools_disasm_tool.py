#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recursive-descent x86-32 disassembler for ETS plugins (capstone based).

Extracts, per binary:
 - function map (entry RVA from exports + discovered call/jmp targets)
 - absolute address -> string references per function
 - dispatch candidates from PlnOnProcessMessage (action keys)
 - per-function annotated disassembly files

Read-only on target. Everything written under work/native/.
"""
import sys, os, re, json, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "pylib"))
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_IMM, CS_OP_MEM, CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET

OUT_ROOT = r"data/native"
TARGETS = [
    ("ETSShell",       r"ETS\ETSShell.exe"),
    ("Ets",            r"ETS\Ets.exe"),
    ("appcontroller",  r"ETS\plugins\appcontroller\appcontroller.pln"),
    ("etshelper",      r"ETS\plugins\etshelper\etshelper.pln"),
    ("filehelper",     r"ETS\plugins\filehelper\filehelper.pln"),
    ("httphelper",     r"ETS\plugins\httphelper\httphelper.pln"),
    ("sevenzip",       r"ETS\plugins\sevenzip\sevenzip.pln"),
    ("shellhelper",    r"ETS\plugins\shellhelper\shellhelper.pln"),
    ("soundhelper",    r"ETS\plugins\soundhelper\soundhelper.pln"),
    ("sqlitepln",      r"ETS\plugins\sqlitepln\sqlitepln.pln"),
    ("window_control", r"ETS\plugins\window_control\window_control.pln"),
]

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True

RE_ASCII = re.compile(rb"[\x20-\x7e]{4,}")
RE_UTF16 = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


class Image:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        self.pe = pefile.PE(data=self.data, fast_load=False)
        self.oh = self.pe.OPTIONAL_HEADER
        self.image_base = self.oh.ImageBase
        self.sections = []
        for s in self.pe.sections:
            self.sections.append({
                "name": s.Name.rstrip(b"\x00").decode("latin-1"),
                "va": self.image_base + s.VirtualAddress,
                "vsize": s.Misc_VirtualSize,
                "raw": s.get_data(),
                "chars": s.Characteristics,
            })
        self.text = self._pick_code()
        self.strings = self._scan_strings()

    def _pick_code(self):
        best = None
        for s in self.sections:
            if s["chars"] & 0x20000000:  # MEM_EXECUTE
                if best is None or len(s["raw"]) > len(best["raw"]):
                    best = s
        return best

    def _scan_strings(self):
        """addr(VA) -> string, for all non-code sections + code (utf16)."""
        res = {}
        for s in self.sections:
            raw = s["raw"]
            base = s["va"]
            for m in RE_ASCII.finditer(raw):
                res[base + m.start()] = m.group().decode("latin-1")
            for m in RE_UTF16.finditer(raw):
                res[base + m.start()] = m.group().decode("utf-16le", "ignore")
        return res

    def off_to_va(self, off):
        # find section whose raw covers off
        best = None
        for s in self.sections:
            pass
        return None

    def va_to_off(self, va):
        try:
            return self.pe.get_offset_from_rva(va - self.image_base)
        except Exception:
            return None

    def read(self, va, n):
        off = self.va_to_off(va)
        if off is None:
            return None
        return self.data[off:off + n]

    def in_code(self, va):
        t = self.text
        return t["va"] <= va < t["va"] + len(t["raw"])

    def exports(self):
        out = []
        for sym in getattr(self.pe, "DIRECTORY_ENTRY_EXPORT", None).symbols if hasattr(self.pe, "DIRECTORY_ENTRY_EXPORT") else []:
            nm = sym.name.decode("utf-8", "ignore") if sym.name else None
            out.append({"ordinal": sym.ordinal, "name": nm,
                        "va": self.image_base + sym.address,
                        "rva": "0x%08X" % sym.address})
        return out


def annotate_string(img, s):
    """decorate a referenced string with printable content"""
    return s


class Dis:
    def __init__(self, img):
        self.img = img
        self.funcs = {}       # start_va -> {"insns":[(va,size,text,refs)], "code":...}
        self.str_xrefs = collections.defaultdict(set)  # str_va -> {(func_start, insn_va)}
        self.discovered_starts = set()
        self.bad = 0

    def _insn_refs(self, ins):
        """return (abs_addrs, call_target, jmp_target, is_ret)"""
        absaddrs = []
        calls = None
        jmp = None
        for op in ins.operands:
            if op.type == CS_OP_IMM:
                v = op.imm & 0xFFFFFFFF
                absaddrs.append(v)
            elif op.type == CS_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                absaddrs.append(op.mem.disp & 0xFFFFFFFF)
        if ins.group(CS_GRP_CALL) and ins.operands and ins.operands[0].type == CS_OP_IMM:
            calls = ins.operands[0].imm & 0xFFFFFFFF
        if ins.group(CS_GRP_JUMP) and ins.operands and ins.operands[0].type == CS_OP_IMM:
            jmp = ins.operands[0].imm & 0xFFFFFFFF
        return absaddrs, calls, jmp, ins.group(CS_GRP_RET) != 0

    def dis_func(self, start, max_insns=6000):
        """recursive descent within one function; returns list of (va,size,text,refs)."""
        img = self.img
        if start in self.funcs:
            return self.funcs[start]["insns"]
        body = []
        seen = set()
        work = [start]
        order = []
        while work:
            va = work.pop()
            while True:
                if va in seen or len(body) > max_insns:
                    break
                seen.add(va)
                if not img.in_code(va):
                    break
                code = img.read(va, 16)
                if not code:
                    break
                insns = list(md.disasm(code, va, 1))
                if not insns:
                    self.bad += 1
                    break
                ins = insns[0]
                absaddrs, calls, jmp, is_ret = self._insn_refs(ins)
                refs = []
                for a in absaddrs:
                    if a in img.strings:
                        refs.append((a, img.strings[a]))
                        self.str_xrefs[a].add((start, va))
                body.append((va, ins.size, "%s %s" % (ins.mnemonic, ins.op_str), refs))
                order.append(va)
                nxt = va + ins.size
                if is_ret:
                    # stop this path unless next is not padding
                    break
                if ins.mnemonic.startswith("jmp"):
                    if jmp is not None and img.in_code(jmp) and jmp != start:
                        # tail call or loop target
                        if jmp > va + 2:  # forward jmp: likely jump table/tail
                            if jmp not in seen:
                                work.append(jmp)
                        else:
                            work.append(jmp)
                        break
                    break
                if ins.mnemonic.startswith("j") and jmp is not None:
                    if img.in_code(jmp) and jmp not in seen and jmp not in work:
                        work.append(jmp)
                    va = nxt
                    continue
                if ins.mnemonic in ("int3", "int 3", "hlt", "ud2"):
                    break
                if calls is not None and img.in_code(calls):
                    if calls not in self.funcs and calls not in self.discovered_starts:
                        self.discovered_starts.add(calls)
                # fallthrough
                if ins.mnemonic.startswith("call") or ins.mnemonic.startswith("j"):
                    va = nxt
                    continue
                va = nxt
                # heuristic stop: next bytes are int3 padding + this appeared aligned ret? handled by ret
        body.sort()
        self.funcs[start] = {"insns": body}
        return body

    def dis_overlaps(self, start, stop):
        """linear-ish bounded disassembly from start up to stop (for long dispatchers)."""
        img = self.img
        body = []
        va = start
        while va < stop and len(body) < 30000:
            code = img.read(va, 16)
            if not code:
                break
            insns = list(md.disasm(code, va, 1))
            if not insns:
                va += 1
                continue
            ins = insns[0]
            absaddrs, calls, jmp, is_ret = self._insn_refs(ins)
            refs = []
            for a in absaddrs:
                if a in img.strings:
                    refs.append((a, img.strings[a]))
                    self.str_xrefs[a].add((start, va))
            body.append((va, ins.size, "%s %s" % (ins.mnemonic, ins.op_str), refs))
            va += ins.size
        return body


ACTION_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,63}$")
LOG_RE = re.compile(r"\[([A-Za-z_][\w:]*)::(\w+)\]")
SIGN_KW = ["md5", "sha1", "sha256", "hmac", "sign", "secret", "appkey", "app_key",
           "apikey", "api_key", "token", "base64", "encrypt", "decrypt", "cipher",
           "aes", "rsa", "crc32", "timestamp", "nonce", "salt", "key", "digest"]


def is_actionish(s):
    if not ACTION_RE.match(s):
        return False
    if re.search(r"\.(dll|exe|pdb|json|txt|log|ini|dat|bin)$", s, re.I):
        return False
    if s.lower() in ("error", "warning", "debug", "info", "true", "false", "null",
                     "utf-8", "utf8", "ascii", "unicode", "success", "failed"):
        return False
    if re.fullmatch(r"[A-Za-z0-9]+", s) and s.islower() and len(s) > 3:
        return True
    if "_" in s and s.islower():
        return True
    if re.match(r"^[a-z]+[A-Z]", s):  # camelCase
        return True
    return False


def process(name, path):
    img = Image(path)
    outdir = os.path.join(OUT_ROOT, name)
    os.makedirs(outdir, exist_ok=True)
    exp = img.exports()
    d = Dis(img)

    # disassemble exported functions
    for e in exp:
        if img.in_code(e["va"]):
            d.dis_func(e["va"])

    # find dispatch function: PlnOnProcessMessage
    target = None
    for e in exp:
        if e["name"] and e["name"].lower().startswith("plnonprocessmessage"):
            target = e
    res = {"file": path, "functions": [], "action_candidates": [],
           "log_handlers": [], "plnonprocess": None}
    if target:
        # recursive descent from the dispatcher entry (switch tables remain unresolved)
        body = d.dis_func(target["va"], max_insns=12000)
        stop = img.text["va"] + len(img.text["raw"])
        refs = []
        seen = set()
        for (va, size, text, refs_) in body:
            for (a, s) in refs_:
                if a not in seen:
                    seen.add(a)
                    refs.append({"va": "0x%08X" % a, "string": s})
        disp_strings = [r for r in refs]
        cand = sorted({r["string"] for r in disp_strings if is_actionish(r["string"])})
        res["plnonprocess"] = {
            "rva": target["rva"], "insn_count": len(body),
            "extent_stop": "0x%08X" % stop,
            "string_refs": disp_strings[:400],
            "action_candidates": cand,
        }

    # analyze all discovered functions, collect log handlers and per-function strings
    all_starts = sorted(set([e["va"] for e in exp if img.in_code(e["va"])]) | d.discovered_starts)
    funcs_out = []
    for st in all_starts:
        body = d.dis_func(st, max_insns=8000)
        strs = []
        seen = set()
        for (va, size, text, refs_) in body:
            for (a, s) in refs_:
                if a not in seen:
                    seen.add(a)
                    strs.append(s)
        logs = []
        for s in strs:
            m = LOG_RE.search(s)
            if m:
                logs.append({"class": m.group(1), "method": m.group(2), "text": s})
        funcs_out.append({
            "rva": "0x%08X" % (st - img.image_base),
            "va": "0x%08X" % st,
            "insn_count": len(body),
            "strings": strs[:200],
            "log_handlers": logs,
        })
    res["functions"] = funcs_out
    # global action candidate = union of plnonprocess candidates and lower-case refs
    log_actions = sorted({(l["method"]) for f in funcs_out for l in f["log_handlers"]})
    res["log_handlers"] = log_actions
    res["stats"] = {"exports": len(exp), "funcs": len(funcs_out),
                    "discovered": len(d.discovered_starts), "bad_decode": d.bad,
                    "strings_indexed": len(img.strings)}
    json.dump(res, open(os.path.join(outdir, "dispatch.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # save disassembly of the dispatcher (bounded)
    if target:
        lines = ["# %s PlnOnProcessMessage @ RVA %s, %d instructions (capstone recursive/linear)"
                 % (name, target["rva"], len(d.funcs[target["va"]]["insns"])), ""]
        for (va, size, text, refs_) in d.funcs[target["va"]]["insns"]:
            r = ""
            if refs_:
                r = "    ; " + " | ".join('"%s"' % s.replace('"', "'")[:100] for (a, s) in refs_)
            lines.append("0x%08X  %-58s%s" % (va, text, r))
        open(os.path.join(outdir, "disasm_plnonprocessmessage.txt"), "w",
             encoding="utf-8").write("\n".join(lines) + "\n")

    print("OK %-14s funcs=%3d discovered=%4d strings=%5d disp_insns=%s actions=%d"
          % (name, len(funcs_out), len(d.discovered_starts), len(img.strings),
             (len(d.funcs[target["va"]]["insns"]) if target else "-"),
             len(res["plnonprocess"]["action_candidates"]) if target else 0))
    return img, d, exp, res


if __name__ == "__main__":
    for name, path in TARGETS:
        if not os.path.isfile(path):
            print("MISSING", path)
            continue
        process(name, path)
