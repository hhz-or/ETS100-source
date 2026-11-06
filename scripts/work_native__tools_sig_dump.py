#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate functions containing given strings (via .text xrefs) and dump
annotated capstone disassembly of them + their direct callees.

Handles MSVC x86-32 layout where functions are separated by 0xCC padding or
16-aligned prologues: candidate function starts are taken from the nearest
preceding int3-padding gap and validated by re-decoding to the xref address.

Usage:
  python sig_dump.py <name> <path> --str SUBSTR [--str ...] [--out FILE]
                     [--depth N] [--maxfuncs N] [--json FILE]
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
        self.raw = self.text["raw"]
        self.base = self.text["va"]
        self.end = self.base + len(self.raw)
        self.strings = {}
        for s in self.secs:
            for m in RE_ASCII.finditer(s["raw"]):
                self.strings[s["va"] + m.start()] = m.group().decode("latin-1")
            for m in RE_UTF16.finditer(s["raw"]):
                self.strings[s["va"] + m.start()] = m.group().decode("utf-16le", "ignore")
        self.iat = {}
        for ent in getattr(self.pe, "DIRECTORY_ENTRY_IMPORT", []) or []:
            dll = ent.dll.decode("latin-1")
            for imp in ent.imports:
                nm = imp.name.decode("latin-1") if imp.name else ("ord_%d" % imp.ordinal)
                # pefile reports PE32 import addresses as VA-like values (image_base + RVA)
                va = imp.address if imp.address >= self.ib else self.ib + imp.address
                self.iat[va] = "%s!%s" % (dll, nm)
        self.exp = {}
        if hasattr(self.pe, "DIRECTORY_ENTRY_EXPORT"):
            for sym in self.pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if sym.name:
                    self.exp[self.ib + sym.address] = sym.name.decode("latin-1")
        # index of string start -> sorted list of xref instruction addresses in .text
        self.str_addrs = sorted(set(self.strings))
        self.strset = set(self.str_addrs)

    def in_text(self, va):
        return self.base <= va < self.end

    def read(self, va, n):
        o = va - self.base
        if 0 <= o < len(self.raw):
            return self.raw[o:o + n]
        try:
            off = self.pe.get_offset_from_rva(va - self.ib)
            return self.data[off:off + n]
        except Exception:
            return None

    def find_xrefs(self, sva):
        """addresses in .text whose 4-byte immediate equals sva"""
        pat = sva.to_bytes(4, "little")
        out = []
        start = 0
        while True:
            i = self.raw.find(pat, start)
            if i < 0:
                break
            out.append(self.base + i)
            start = i + 1
        return out

    def function_start_for(self, insn_va, max_back=0x4000):
        """MSVC x86: functions are 16-byte aligned and preceded by int3 padding
        (or the previous function ends exactly at the boundary).
        Try up to 16 preceding aligned candidates, validated by exact re-decode."""
        cands = []
        # exports at/just above the xref are always valid starts
        for va in self.exp:
            if self.base <= va <= insn_va:
                cands.append(va)
        a = insn_va & ~0xF
        lo = max(self.base, insn_va - max_back)
        while a >= lo:
            o = a - self.base
            if 0 <= o:
                b = self.raw[o] if o < len(self.raw) else 0xCC
                prev = self.raw[o - 1] if o - 1 >= 0 else 0xCC
                if b != 0xCC and (prev == 0xCC or prev in (0xC3, 0xC2, 0x90)):
                    cands.append(a)
            a -= 16
        cands = sorted(set(cands), reverse=True)
        for c in cands[:24]:
            if self.decodes_to(c, insn_va):
                return c
        return None

    def decodes_to(self, start, target, limit=30000):
        va = start
        n = 0
        while va < target and n < limit:
            code = self.read(va, 16)
            if not code:
                return False
            try:
                ins = next(md.disasm(code, va, 1))
            except StopIteration:
                return False
            nva = va + ins.size
            if nva == target:
                return True
            if nva > target:
                return False
            va = nva
            n += 1
        return False


def dis_func(img, start, max_insns=6000):
    """recursive-descent function body -> (insns, callees, strrefs)"""
    body = []
    callees = []
    strrefs = []
    visited = set()
    stack = [start]
    while stack:
        va = stack.pop()
        while True:
            if va in visited or not img.in_text(va) or len(body) > max_insns:
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
            for op in ins.operands:
                vals = []
                if op.type == CS_OP_IMM:
                    vals.append(op.imm & 0xFFFFFFFF)
                elif op.type == CS_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                    vals.append(op.mem.disp & 0xFFFFFFFF)
                for v in vals:
                    if v in img.iat:
                        cmt.append("IAT " + img.iat[v])
                    elif v in img.strset:
                        s = img.strings[v]
                        cmt.append('"%s"' % s.replace('"', "'")[:120])
                        strrefs.append((v, s))
            body.append((va, ins.size, "%s %s" % (ins.mnemonic, ins.op_str), cmt))
            nxt = va + ins.size
            if ins.group(CS_GRP_RET):
                break
            if ins.mnemonic.startswith("jmp"):
                if ins.operands and ins.operands[0].type == CS_OP_IMM:
                    t = ins.operands[0].imm & 0xFFFFFFFF
                    if img.in_text(t):
                        # tail call to another function: treat as callee
                        callees.append(t)
                break
            if ins.mnemonic.startswith("j") and ins.operands and ins.operands[0].type == CS_OP_IMM:
                t = ins.operands[0].imm & 0xFFFFFFFF
                if img.in_text(t) and t not in visited:
                    stack.append(t)
                va = nxt
                continue
            if ins.mnemonic in ("int3", "hlt", "ud2", "int 3"):
                break
            if ins.group(CS_GRP_CALL) and ins.operands and ins.operands[0].type == CS_OP_IMM:
                t = ins.operands[0].imm & 0xFFFFFFFF
                if img.in_text(t):
                    callees.append(t)
            va = nxt
    body.sort()
    seen = set()
    callees2 = []
    for c in callees:
        if c not in seen:
            seen.add(c)
            callees2.append(c)
    return body, callees2, strrefs


def dump(img, name, start, body, callee_names):
    nm = img.exp.get(start)
    title = "%s  %s  n_insns=%d" % (name, ("export:" + nm) if nm else "sub_%08X" % start, len(body))
    lines = ["", "=" * 100, "# " + title, "=" * 100]
    for (va, size, text, cmt) in body:
        anno = ""
        if cmt:
            anno = "   ; " + " | ".join(cmt)
        lines.append("0x%08X  %-54s%s" % (va, text, anno))
    return "\n".join(lines)


def main():
    name, path = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    subs, out, jsonout, depth, maxfuncs, rvas = [], None, None, 2, 60, []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--str":
            subs.append(args[i + 1]); i += 2
        elif a == "--out":
            out = args[i + 1]; i += 2
        elif a == "--json":
            jsonout = args[i + 1]; i += 2
        elif a == "--depth":
            depth = int(args[i + 1]); i += 2
        elif a == "--maxfuncs":
            maxfuncs = int(args[i + 1]); i += 2
        elif a == "--rva":
            rvas.append(int(args[i + 1], 0)); i += 2
        else:
            i += 1

    img = Img(path)
    if rvas:
        funcs = [img.ib + r for r in rvas]
        entries = []
        print("explicit funcs:", ["0x%08X" % f for f in funcs])
    else:
        # 1) locate string VAs whose text matches any substring
        hit_addrs = []
        for sva in img.str_addrs:
            s = img.strings[sva]
            if any(sub in s for sub in subs):
                hit_addrs.append(sva)
        print("string hits:", len(hit_addrs))

        # 2) xref instructions -> enclosing function starts
        entries = []
        for sva in hit_addrs:
            for x in img.find_xrefs(sva):
                fs = img.function_start_for(x)
                if fs is None:
                    fs = x
                entries.append({"str_va": sva, "string": img.strings[sva], "xref": x, "func": fs})
        funcs = sorted({e["func"] for e in entries})
        print("functions:", ["0x%08X" % f for f in funcs])

    # 3) disassemble functions, then callees to depth
    order = []
    got = {}
    queue = [(f, 0) for f in funcs]
    while queue and len(got) < maxfuncs:
        f, d = queue.pop(0)
        if f in got:
            continue
        body, callees, strrefs = dis_func(img, f)
        got[f] = {"body": body, "callees": callees, "strrefs": strrefs, "depth": d}
        order.append(f)
        if d < depth:
            for c in callees:
                if c not in got and c not in [q[0] for q in queue]:
                    queue.append((c, d + 1))

    chunks = []
    meta = {"file": path, "functions": []}
    for f in order:
        g = got[f]
        chunks.append(dump(img, name, f, g["body"], {}))
        meta["functions"].append({
            "start": "0x%08X" % f,
            "name": img.exp.get(f),
            "depth": g["depth"],
            "n_insns": len(g["body"]),
            "strings": sorted({s for (a, s) in g["strrefs"]}),
            "iat_calls": sorted({x[4:] for (va, sz, t, c) in g["body"] for x in c if x.startswith("IAT ")}),
            "callees": ["0x%08X" % c for c in g["callees"]],
        })
    header = "# %s | %s | string-substrings=%s | funcs=%d" % (name, path, subs, len(order))
    text = header + "\n" + "\n".join(chunks)
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(text + "\n")
        print("wrote", out, len(text), "bytes /", len(order), "funcs")
    if jsonout:
        json.dump(meta, open(jsonout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # console summary: function -> strings + IAT calls
    iat_union = set()
    for f in order:
        g = got[f]
        iats = sorted({x for (va, sz, t, c) in g["body"] for x in c if x.startswith("IAT ")})
        iat_union.update(iats)
        print("  func 0x%08X depth=%d insns=%d iats=%d strings=%d" %
              (f, g["depth"], len(g["body"]), len(iats), len(g["strrefs"])))
        for x in iats[:14]:
            print("      ", x)
        for (a, s) in g["strrefs"][:8]:
            print("       str:", s[:110])


if __name__ == "__main__":
    main()
