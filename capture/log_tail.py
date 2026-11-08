#!/usr/bin/env python3
"""ETS 练习抓包 · 日志跟随（官方客户端 logs/*.log）

客户端前端会把 API 请求/响应、页面事件写入 logs/ets_*.log（经 mq_server 落盘）；
这里把运行期间新增的行实时写入 logs.jsonl，作为 HTTP 抓包的交叉证据。
"""
import glob
import json
import os
import signal
import sys
import time
from datetime import datetime

ETS_DIR = os.environ.get("ETS_DIR", r"D:\ets-rea\ETS")
LOG_DIR = os.path.join(ETS_DIR, "logs")
stop = {"v": False}


def handle(signum, frame):
    stop["v"] = True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    outdir = os.path.abspath(sys.argv[1])
    os.makedirs(outdir, exist_ok=True)
    if not os.path.isdir(LOG_DIR):
        print("[logs] 日志目录不存在:", LOG_DIR)
        return 2

    files = {}
    for pattern in ("ets_*.log", "shell_*.log", "cef_*.log"):
        for p in glob.glob(os.path.join(LOG_DIR, pattern)):
            try:
                files[p] = os.path.getsize(p)
            except OSError:
                pass
    print(f"[logs] 跟随 {len(files)} 个日志文件（仅新行）")

    fd = open(os.path.join(outdir, "logs.jsonl"), "a", encoding="utf-8")
    signal.signal(signal.SIGINT, handle)
    total = 0
    try:
        while not stop["v"]:
            for p in list(files):
                try:
                    size = os.path.getsize(p)
                    if size < files[p]:
                        files[p] = 0  # 日志轮转
                    if size > files[p]:
                        with open(p, "rb") as f:
                            f.seek(files[p])
                            chunk = f.read(size - files[p])
                            files[p] = f.tell()
                        for raw in chunk.decode("utf-8", "replace").splitlines():
                            if not raw.strip():
                                continue
                            fd.write(json.dumps({"t": datetime.now().isoformat(), "file": os.path.basename(p), "line": raw}, ensure_ascii=False) + "\n")
                            total += 1
                        fd.flush()
                except OSError:
                    continue
            time.sleep(0.4)
    finally:
        fd.close()
        print(f"[logs] 已停止，新行 {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
