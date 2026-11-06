"""Parse ETS soundfiles: evaluation XML results + mp3/spx pair analysis."""
import os, json, re, hashlib, zlib, gzip, bz2, lzma, collections
import xml.etree.ElementTree as ET

D = r"D:\ets-rea\ETS\soundfiles"
OUT = r"D:\ets-rea\work\data\soundfiles"
os.makedirs(OUT, exist_ok=True)


def fmt(xml_bytes):
    s = xml_bytes.decode("utf-8", "replace")
    # pretty print lightly
    return s


def walk(elem, depth=0):
    return {
        "tag": elem.tag,
        "attrib": dict(elem.attrib),
        "children": [walk(c, depth + 1) for c in list(elem)[:40]],
        "child_count": len(list(elem)),
    }


files = sorted(f for f in os.listdir(D) if f.endswith(".xml"))
rows = []
schema_stats = collections.Counter()
eval_types = collections.Counter()
versions = collections.Counter()
regions = collections.Counter()
type_attr = collections.Counter()
scores = collections.defaultdict(list)
reject = collections.Counter()
attr_names = collections.defaultdict(collections.Counter)
for f in files:
    p = os.path.join(D, f)
    raw = open(p, "rb").read()
    try:
        root = ET.fromstring(raw)
    except Exception as e:
        rows.append({"file": f, "error": str(e)})
        continue
    base = f[:-4]
    mp3 = base + ".mp3"
    spx = mp3 + ".spx"
    # root child = evaluation element
    ev = list(root)
    ev = ev[0] if ev else None
    rec = {
        "file": f, "size": len(raw),
        "root_tag": root.tag,
        "eval_tag": ev.tag if ev is not None else None,
        "eval_attrib": dict(ev.attrib) if ev is not None else {},
        "paired_files": {
            "mp3": {"exists": os.path.exists(os.path.join(D, mp3)),
                    "size": os.path.getsize(os.path.join(D, mp3)) if os.path.exists(os.path.join(D, mp3)) else 0},
            "spx": {"exists": os.path.exists(os.path.join(D, spx)),
                    "size": os.path.getsize(os.path.join(D, spx)) if os.path.exists(os.path.join(D, spx)) else 0},
        },
        "top_tags": [c.tag for c in (ev if ev is not None else [])][:10],
    }
    if ev is not None:
        eval_types[ev.tag] += 1
        for a in ("lan", "region", "region_version", "type", "version"):
            if a in ev.attrib:
                {"lan": regions, "region": regions, "region_version": regions,
                 "type": type_attr, "version": versions}[a][ev.attrib[a]] += 1
        # score fields on read_chapter / rec_paper
        for node in ev.iter():
            for k, v in node.attrib.items():
                attr_names[node.tag][k] += 1
            if node.tag in ("read_chapter", "rec_paper", "sentence", "word", "syll", "phone"):
                for sc in ("total_score", "accuracy_score", "fluency_score", "integrity_score",
                           "standard_score", "phone_total_score", "syll_score"):
                    if sc in node.attrib:
                        try:
                            scores[sc].append(float(node.attrib[sc]))
                        except Exception:
                            pass
            if node.tag in ("read_chapter", "rec_paper") and "is_rejected" in node.attrib:
                reject[node.attrib.get("is_rejected")] += 1
        # structure summary: tag hierarchy of first path
        def path(e):
            return "/".join([e.tag] + [path(c) for c in list(e)[:1]])
        rec["structure_path"] = path(ev)
        rec["text_content_sample"] = []
        for node in ev.iter():
            c = node.attrib.get("content")
            if c and len(c) > 1:
                rec["text_content_sample"].append(c.strip())
        rec["text_content_sample"] = rec["text_content_sample"][:40]
    rows.append(rec)

stats = {
    "file_count": len(files),
    "eval_tags": dict(eval_types),
    "eval_type_attr": dict(type_attr),
    "regions": dict(regions),
    "engine_versions": dict(versions),
    "reject_counts": dict(reject),
    "score_ranges": {k: {"count": len(v), "min": min(v), "max": max(v),
                         "mean": round(sum(v) / len(v), 4) if v else None}
                     for k, v in scores.items()},
    "attr_frequency_top": {t: dict(c.most_common(14)) for t, c in attr_names.items()},
}
json.dump({"stats": stats, "files": rows}, open(os.path.join(OUT, "xml_parse.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ------- spx/mp3 binary analysis -------
bin_rows = []
pairs = [f for f in os.listdir(D) if f.endswith(".mp3")]
for mp in sorted(pairs):
    p = os.path.join(D, mp)
    s = p + ".spx"
    mb = open(p, "rb").read()
    sb = open(s, "rb").read() if os.path.exists(s) else b""
    rec = {"mp3": mp, "mp3_size": len(mb), "spx_size": len(sb),
           "mp3_head_hex": mb[:16].hex(), "spx_head_hex": sb[:16].hex(),
           "ratio": round(len(sb) / len(mb), 4) if mb else None}
    if sb:
        # entropy of first block
        import math
        def ent(b):
            if not b:
                return 0
            c = collections.Counter(b)
            n = len(b)
            return round(-sum((v / n) * math.log2(v / n) for v in c.values()), 3)
        rec["spx_entropy_first1k"] = ent(sb[:1000])
        rec["spx_entropy_all"] = ent(sb)
        rec["spx_has_speex_string"] = b"Speex" in sb
        rec["spx_has_ogg"] = b"OggS" in sb[:8]
        rec["spx_ascii_strings"] = [x.decode("latin1") for x in re.findall(rb"[\x20-\x7e]{5,}", sb)[:10]]
        # try common decompressors on whole and offset 1..8
        dec = []
        for off in (0, 1, 2, 4, 8):
            frag = sb[off:]
            for name, fn in (("zlib", lambda b: zlib.decompress(b)),
                             ("gzip", lambda b: gzip.decompress(b)),
                             ("bz2", lambda b: bz2.decompress(b)),
                             ("lzma", lambda b: lzma.decompress(b))):
                try:
                    fn(frag)
                    dec.append(f"{name}@{off}")
                except Exception:
                    pass
        rec["decompress_tried_ok"] = dec
    bin_rows.append(rec)
json.dump(bin_rows, open(os.path.join(OUT, "audio_pair_analysis.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps(stats, ensure_ascii=False, indent=1)[:4000])
print("spx sample:", json.dumps(bin_rows[0], ensure_ascii=False, indent=1))
print("all spx first bytes:", collections.Counter(r["spx_head_hex"][:2] for r in bin_rows))
print("ratios:", collections.Counter(r["ratio"] for r in bin_rows))
