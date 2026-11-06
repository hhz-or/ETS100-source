"""Pure-python LevelDB reader for Chromium LevelDB dirs (no external deps).
Parses .ldb (SortedStringTable) + .log (write-ahead log) files, merges by sequence number.
"""
import os, struct, json, hashlib

# ---------------- snappy ----------------
def snappy_decompress(data):
    pos = 0
    # uncompressed length varint
    shift = 0; ulen = 0
    while True:
        b = data[pos]; pos += 1
        ulen |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    out = bytearray()
    n = len(data)
    while pos < n:
        tag = data[pos]; pos += 1
        t = tag & 3
        if t == 0:  # literal
            ln = tag >> 2
            if ln < 60:
                ln += 1
            else:
                extra = ln - 59
                ln = int.from_bytes(data[pos:pos+extra], 'little') + 1
                pos += extra
            out += data[pos:pos+ln]; pos += ln
        else:
            if t == 1:
                ln = 4 + ((tag >> 2) & 0x7)
                off = ((tag >> 5) << 8) | data[pos]; pos += 1
            elif t == 2:
                ln = 1 + (tag >> 2)
                off = int.from_bytes(data[pos:pos+2], 'little'); pos += 2
            else:
                ln = 1 + (tag >> 2)
                off = int.from_bytes(data[pos:pos+4], 'little'); pos += 4
            start = len(out) - off
            if start < 0:
                raise ValueError("bad snappy offset")
            for i in range(ln):
                out.append(out[start + i])
    if len(out) != ulen:
        raise ValueError(f"snappy len mismatch {len(out)} != {ulen}")
    return bytes(out)

# ---------------- varint / block ----------------
def read_varint(buf, pos):
    shift = 0; val = 0
    while True:
        b = buf[pos]; pos += 1
        val |= (b & 0x7f) << shift
        if not (b & 0x80):
            return val, pos
        shift += 7

def read_block(data, off, size):
    raw = data[off:off+size]
    ctype = data[off+size]
    if ctype == 0:
        return raw
    if ctype == 1:
        return snappy_decompress(raw)
    if ctype == 2:  # zlib (rare)
        import zlib
        return zlib.decompress(raw)
    raise ValueError("unknown block compression %d" % ctype)

def block_entries(block):
    n = len(block)
    if n < 4:
        return
    num_restarts = struct.unpack('<I', block[-4:])[0]
    end = n - 4 - 4 * num_restarts
    if end < 0:
        end = 0
    pos = 0
    prev = b''
    while pos < end:
        shared, pos = read_varint(block, pos)
        non_shared, pos = read_varint(block, pos)
        vlen, pos = read_varint(block, pos)
        key = prev[:shared] + block[pos:pos+non_shared]
        pos += non_shared
        val = block[pos:pos+vlen]
        pos += vlen
        yield key, val
        prev = key

def read_table(path):
    data = open(path, 'rb').read()
    if len(data) < 48:
        return []
    footer = data[-48:]
    pos = 0
    m_off, pos = read_varint(footer, pos)
    m_size, pos = read_varint(footer, pos)
    i_off, pos = read_varint(footer, pos)
    i_size, pos = read_varint(footer, pos)
    out = []
    try:
        idx = read_block(data, i_off, i_size)
    except Exception as e:
        return out
    for _, handle in block_entries(idx):
        try:
            hpos = 0
            boff, hpos = read_varint(handle, hpos)
            bsize, hpos = read_varint(handle, hpos)
            blk = read_block(data, boff, bsize)
        except Exception:
            continue
        for k, v in block_entries(blk):
            out.append((k, v))
    return out

# ---------------- log ----------------
def read_log(path):
    data = open(path, 'rb').read()
    pos = 0
    n = len(data)
    buf = bytearray()
    out = []
    while pos + 7 <= n:
        block_left = 32768 - (pos % 32768)
        if block_left < 7:
            pos += block_left
            continue
        header = data[pos:pos+7]
        if header == b'\x00' * 7:
            pos += 32768 - (pos % 32768)
            continue
        length = struct.unpack('<H', header[4:6])[0]
        rtype = header[6]
        payload = data[pos+7:pos+7+length]
        pos += 7 + length
        if rtype == 1:
            out.append(bytes(payload)); buf = bytearray()
        elif rtype == 2:
            buf = bytearray(payload)
        elif rtype == 3:
            buf += payload
        elif rtype == 4:
            buf += payload
            out.append(bytes(buf)); buf = bytearray()
    return out

def parse_writebatch(rec):
    """Yield (seq, type, key, value) from a WriteBatch record."""
    if len(rec) < 12:
        return
    seq = struct.unpack('<Q', rec[0:8])[0]
    count = struct.unpack('<I', rec[8:12])[0]
    pos = 12
    for i in range(count):
        if pos >= len(rec):
            break
        tag = rec[pos]; pos += 1
        klen, pos = read_varint(rec, pos)
        key = rec[pos:pos+klen]; pos += klen
        if tag == 1:
            vlen, pos = read_varint(rec, pos)
            val = rec[pos:pos+vlen]; pos += vlen
            yield (seq + i, 'put', key, val)
        else:
            yield (seq + i, 'del', key, b'')

# ---------------- merged db ----------------
def read_db(dbdir):
    """Return dict user_key -> (seq, type, value) with latest version."""
    entries = []
    for f in sorted(os.listdir(dbdir)):
        p = os.path.join(dbdir, f)
        if not os.path.isfile(p):
            continue
        try:
            if f.endswith('.ldb') or f.endswith('.sst'):
                for k, v in read_table(p):
                    if len(k) < 8:
                        continue
                    seq = int.from_bytes(k[-8:], 'little') >> 8
                    typ = 1 if k[-1] == 1 else 0
                    entries.append((k[:-8], seq, typ, v, f))
            elif f.endswith('.log'):
                for rec in read_log(p):
                    for seq, typ, key, val in parse_writebatch(rec):
                        entries.append((key, seq, 1 if typ == 'put' else 0, val, f))
        except Exception as e:
            print("WARN", p, e)
    merged = {}
    for key, seq, typ, val, src in entries:
        cur = merged.get(key)
        if cur is None or seq > cur[0]:
            merged[key] = (seq, typ, val, src)
    return merged

# ---------------- string extraction ----------------
import re
_ascii = re.compile(rb"[\x20-\x7e]{4,}")
_utf16 = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")
_utf16cjk = re.compile(rb"(?:[\x00-\xff][\x30-\x9f]){3,}")

def extract_strings(b, minlen=4):
    out = []
    for m in _ascii.finditer(b):
        out.append(m.group().decode('latin1'))
    for m in _utf16.finditer(b):
        try:
            out.append(m.group().decode('utf-16le'))
        except Exception:
            pass
    for m in _utf16cjk.finditer(b):
        try:
            s = m.group().decode('utf-16le')
            if any('\u4e00' <= c <= '\u9fff' for c in s):
                out.append(s)
        except Exception:
            pass
    # dedupe keeping order
    seen = set(); res = []
    for s in out:
        s = s.strip()
        if len(s) >= minlen and s not in seen:
            seen.add(s); res.append(s)
    return res

def summarize(val, limit=400):
    s = " | ".join(extract_strings(val))
    return s[:limit]
