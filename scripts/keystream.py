import struct, hashlib

PATH = r"D:\ets-rea\ETS\plugins\etshelper\etshelper.pln"
b = open(PATH, "rb").read()

# --- parse PE ---
e_lfanew = struct.unpack_from("<I", b, 0x3C)[0]
assert b[e_lfanew:e_lfanew + 4] == b"PE\0\0"
nsec = struct.unpack_from("<H", b, e_lfanew + 6)[0]
opt = e_lfanew + 24
magic = struct.unpack_from("<H", b, opt)[0]
image_base = struct.unpack_from("<I", b, opt + 28)[0]
size_opt = struct.unpack_from("<H", b, e_lfanew + 20)[0]
sec = opt + size_opt
sections = []
for i in range(nsec):
    o = sec + i * 40
    name = b[o:o + 8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", b, o + 8)
    sections.append((name, vaddr, vsize, rawptr, rawsize))
print("image_base", hex(image_base))
for s in sections:
    print(s)
print()


def va2off(va):
    rva = va - image_base
    for name, vaddr, vsize, rawptr, rawsize in sections:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    raise ValueError(hex(va))


def read(va, n):
    o = va2off(va)
    return b[o:o + n]


def keystream(data_va, idx_va, count, length):
    data = read(data_va, length * 4)
    idx = read(idx_va, count * 2)
    out = bytearray()
    fnv = 0x811C9DC5
    for i in range(count):
        u16 = struct.unpack_from("<H", idx, i * 2)[0]
        if u16 >= length:
            raise ValueError("index out of range")
        b0 = data[u16 * 4]
        b1 = data[u16 * 4 + 1]
        b2 = data[u16 * 4 + 2]
        b3 = data[u16 * 4 + 3]
        r = b3 & 7
        if r:
            b0 = ((b0 >> r) | ((b0 << (8 - r)) & 0xFF)) & 0xFF
        v = ((b0 - b2) & 0xFF) ^ b1
        out.append(v)
        fnv = ((v ^ fnv) * 0x1000193) & 0xFFFFFFFF
    return bytes(out), fnv


print("=== selector 0 (v1) ===")
try:
    ks0, fnv0 = keystream(0x10069208, 0x100691C8, 0x20, 0x32)
    print("keystream0:", ks0.hex())
    print("fnv0:", hex(fnv0), "expected 0x32a7b273", "MATCH" if fnv0 == 0x32A7B273 else "MISMATCH")
except Exception as e:
    print("err0", e)

print("=== selector 1 (v2) ===")
try:
    ks1, fnv1 = keystream(0x10069310, 0x100692D0, 0x20, 0x3D)
    print("keystream1:", ks1.hex())
    print("fnv1:", hex(fnv1), "expected 0xb9ef3cd1", "MATCH" if fnv1 == 0xB9EF3CD1 else "MISMATCH")
except Exception as e:
    print("err1", e)

# dump raw bytes for reference
for va, n, label in [(0x10069208, 0xC8, "sel0_data"), (0x100691C8, 0x40, "sel0_idx"),
                     (0x10069310, 0xF4, "sel1_data"), (0x100692D0, 0x40, "sel1_idx")]:
    try:
        print(label, read(va, n).hex())
    except Exception as e:
        print(label, "err", e)

# Also: what strings live near these tables?
print("\n=== raw bytes around 0x100691C8..0x100693F8 ===")
raw = read(0x100691C8, 0x230)
print(raw.hex())
print(repr(raw))
