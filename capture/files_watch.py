#!/usr/bin/env python3
"""ETS 练习抓包 · 文件监听

监听运行期间目标程序新增/修改的文件（录音、临时音频、题库包、评测 xml 等），
复制到 files/fs/ 并记录 md5，便于还原录音与评测输入。
"""
import hashlib
import json
import os
import shutil
import signal
import sys
import time
from datetime import datetime

ETS_DIR = os.environ.get("ETS_DIR", str(Path(__file__).resolve().parent.parent / "ETS"))
ROOT_DIRS = [
    os.path.join(ETS_DIR, "temp"),
    os.path.join(ETS_DIR, "data"),
    os.path.join(ETS_DIR, "logs"),
    os.path.join(os.environ.get("APPDATA", ""), "ETS"),
]
EXTS = {".spx", ".mp3", ".wav", ".pcm", ".ogg", ".xml", ".json", ".zip", ".7z", ".txt", ".log", ".ini"}
MAX_SIZE = 30 * 1024 * 1024
stop = {"v": False}


def handle(signum, frame):
    stop["v"] = True


def md5(p):
    h = hashlib.md5()
    try:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    outdir = os.path.abspath(sys.argv[1])
    dstroot = os.path.join(outdir, "files", "fs")
    os.makedirs(dstroot, exist_ok=True)
    start = time.time()
    seen = {}
    print("[files] 监听:", ", ".join(d for d in ROOT_DIRS if os.path.isdir(d)))
    fd = open(os.path.join(outdir, "files.jsonl"), "a", encoding="utf-8")
    signal.signal(signal.SIGINT, handle)
    count = 0
    try:
        while not stop["v"]:
            for root in ROOT_DIRS:
                if not os.path.isdir(root):
                    continue
                for dirpath, dirnames, filenames in os.walk(root):
                    if dirpath.startswith(dstroot):
                        continue
                    for name in filenames:
                        p = os.path.join(dirpath, name)
                        try:
                            st = os.stat(p)
                        except OSError:
                            continue
                        if st.st_mtime < start - 2 or st.st_size == 0 or st.st_size > MAX_SIZE:
                            continue
                        if os.path.splitext(name)[1].lower() not in EXTS:
                            continue
                        key = p
                        sig = (st.st_size, int(st.st_mtime))
                        if seen.get(key) == sig:
                            continue
                        seen[key] = sig
                        rel = os.path.relpath(p, os.path.dirname(root))
                        dst = os.path.join(dstroot, rel)
                        try:
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.copy2(p, dst)
                        except OSError:
                            continue
                        rec = {"t": datetime.now().isoformat(), "path": p, "rel": rel, "size": st.st_size, "md5": md5(dst), "copied": dst}
                        fd.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fd.flush()
                        count += 1
                        print(f"[FILE] {rel} {st.st_size}B")
            time.sleep(1.0)
    finally:
        fd.close()
        print(f"[files] 已停止，新文件 {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
