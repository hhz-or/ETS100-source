#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Function-level annotated disassembly for ETS PE32 files (capstone).

Seeds recursive descent from exports and from code immediates that point into
.text (handler tables registered by address in PlnInitiliaze), so internal
functions are reachable. IAT slots are annotated with DLL!Function.

Usage:
  python func_dump.py <name> <path> [--str SUBSTR ...] [--out FILE] [--list]
"""
import sys, os, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "pylib"))
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_OP_IMM, CS_OP_MEM, CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True

RE_ASCII = re.compile(rb"[\x20-\x7e]{4,}")
RE_UTF16 = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


class Img:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        self.pe = pefile.PE(data=self.data, fast_load=False)
        self.ib = self.pe.OPTIONAL_HEADER.ImageBase
        self.secs = []
        for s in self.pe.sections:
            self.secs.append({"name": s.Name.rstrip(b"\x00").decode("latin-1"),
                              "va": self.ib + s.VirtualAddress, "raw": s.get_data(),
                              "chars": s.Characteristics})
        self.text = max((s for s in self.secs if s["chars"] & 0x20000000), key=lambda s: len(s["raw"]))
        self.text_lo = self.text["va"]
        self.text_hi = self.text_va_end = self.text["va"] + len(self.text["raw"])
        self.strings = {}
        for s in self.secs:
            for m in RE_ASCII.finditer(s["raw"]):
                self.strings[s["va"] + m.start()] = m.group().decode("latin-1")
            for m in RE_UTF16.finditer(s["raw"]):
                self.strings[s["va"] + m.start()] = m.group().decode("utf-16le", "ignore")
        self.str_to_addr = collections.defaultdict(list)
        for a, s in self.strings.items():
            self.str_to_addr[s].append(a)
        self.iat = {}
        for ent in getattr(self.pe, "DIRECTORY_ENTRY_IMPORT", []) or []:
            dll = ent.dll.decode("latin-1")
            for imp in ent.imports:
                nm = imp.name.decode("latin-1") if imp.name else ("ord_%d" % imp.ordinal)
                va = imp.address if imp.address >= self.ib else self.ib + imp.address
                self.iat[va] = "%s!%s" % (dll, nm)
        self.exp = {}
        if hasattr(self.pe, "DIRECTORY_ENTRY_EXPORT"):
            for sym in self.pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if sym.name:
                    self.exp[sym.name.decode("latin-1")] = self.ib + sym.address

    def off(self, va):
        try:
            return self.pe.get_offset_from_rva(va - self.ib)
        except Exception:
            return None

    def read(self, va, n):
        o = self.off(va)
        return self.data[o:o + n] if o is not None else None

    def in_text(self, va):
        return self.text["va"] <= va < self.text_va_end


def analyze(img, max_funcs=20000):
    funcs = {}                     # start -> list of (va,size,text,cmt)
    insn_func = {}                 # insn va -> func start
    str_refs = collections.defaultdict(set)   # str va -> {(func, insn)}
    work = list(img.exp.values())
    seen_seed = set(work)
    # prologue scan for additional seeds (validated by decode)
    raw, base = img.text["raw"], img.text["va"]
    for m in re.finditer(rb"\x55\x8b\xec", raw):
        a = base + m.start()
        if a not in seen_seed:
            seen_seed.add(a)
            work.append(a)
    while work and len(funcs) < max_funcs:
        st = work.pop()
        if st in funcs or not img.in_text(st):
            continue
        body = []
        visited = set()
        stack = [st]
        while stack:
            va = stack.pop()
            while True:
                if va in visited or not img.in_text(va):
                    break
                visited.add(va)
                code = img.read(va, 16)
                if not code:
                    break
                try:
                    ins = next(md.disasm(code, va, 1))
                except StopIteration:
                    break
                cmt = []
                imm_text = []
                for op in ins.operands:
                    if op.type == CS_OP_IMM:
                        v = op.imm & 0xFFFFFFFF
                        imm_text.append(v)
                    elif op.type == CS_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                        v = op.mem.disp & 0xFFFFFFFF
                        if v in img.iat:
                            cmt.append(img.iat[v])
                        else:
                            imm_text.append(v)
                for v in imm_text:
                    if v in img.strings:
                        s = img.strings[v]
                        cmt.append('"%s"' % s.replace('"', "'")[:120])
                        str_refs[v].add((st, va))
                    elif img.in_text(v):
                        # possible function pointer (handler table registration)
                        if v not in seen_seed and v not in funcs:
                            seen_seed.add(v)
                            work.append(v)
                body.append((va, ins.size, "%s %s" % (ins.mnemonic, ins.op_str), cmt))
                insn_func[va] = st
                nxt = va + ins.size
                is_ret = ins.group(CS_GRP_RET) != 0
                is_jmp = ins.group(CS_GRP_JUMP) != 0
                is_call = ins.group(CS_GRP_CALL) != 0
                if is_ret:
                    break
                if ins.mnemonic.startswith("jmp"):
                    if ins.operands and ins.operands[0].type == CS_OP_IMM:
                        t = ins.operands[0].imm & 0xFFFFFFFF
                        if img.in_text(t):
                            if t > va:
                                if t not in visited:
                                    stack.append(t)
                            else:
                                stack.append(t)
                    break
                if ins.mnemonic.startswith("j") and ins.operands and ins.operands[0].type == CS_OP_IMM:
                    t = ins.operands[0].imm & 0xFFFFFFFF
                    if img.in_text(t) and t not in visited:
                        stack.append(t)
                    va = nxt
                    continue
                if ins.mnemonic in ("int3", "hlt", "ud2", "int 3"):
                    break
                va = nxt
        if body:
            funcs[st] = body
    return funcs, insn_func, str_refs


def func_at(funcs, insn_func, va):
    return insn_func.get(va)


def dump_func(img, body, title):
    lines = ["# %s" % title, ""]
    for (va, size, text, cmt) in body:
        c = ("   ; " + " | ".join(cmt)) if cmt else ""
        lines.append("0x%08X  %-56s%s" % (va, text, c))
    return "\n".join(lines)


def main():
    name, path = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    sub_str = []
    out = None
    listmode = False
    i = 0
    while i < len(args):
        if args[i] == "--str":
            sub_str.append(args[i + 1]); i += 2
        elif args[i] == "--out":
            out = args[i + 1]; i += 2
        elif args[i] == "--list":
            listmode = True; i += 1
        else:
            i += 1
    img = Img(path)
    funcs, insn_func, str_refs = analyze(img)
    print("functions=%d" % len(funcs))
    if listmode:
        rows = []
        for st in sorted(funcs):
            body = funcs[st]
            strs = []
            seen = set()
            for (va, size, text, cmt) in body:
                for c in cmt:
                    if c.startswith('"') and c not in seen:
                        seen.add(c); strs.append(c)
            rows.append({"start": "0x%08X" % st, "n": len(body), "strings": strs[:12],
                         "export": [k for k, v in img.exp.items() if v == st]})
        json.dump({"file": path, "functions": rows}, open(out or (os.path.splitext(path)[0] + "_funcs.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("listed %d functions -> %s" % (len(rows), out or "?"))
        return
    # locate functions containing target substrings
    targets = []
    for st in sorted(funcs):
        body = funcs[st]
        texts = [c for (va, size, t, cmt) in body for c in cmt]
        hit = [s for s in sub_str if any(s in c for c in texts)]
        if hit:
            targets.append((st, hit))
    print("targets:", [(("0x%08X" % st), h) for st, h in targets])
    chunks = []
    for st, hit in targets:
        exp = [k for k, v in img.exp.items() if v == st]
        title = "%s @0x%08X%s  matched=%s" % (name, st, ("  [export:%s]" % ",".join(exp)) if exp else "", hit)
        chunks.append(dump_func(img, funcs[st], title))
    text = "\n\n".join(chunks)
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(text + "\n")
        print("wrote", out, len(text), "bytes")


if __name__ == "__main__":
    main()
