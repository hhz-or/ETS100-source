#!/usr/bin/env python3
"""ETS 练习抓包 · Frida 原生采集（WinHTTP 请求/响应 + WebSocket 帧）

用法:
    python native_capture.py <输出目录> [--pid PID]

- 默认自动寻找窗口标题含「E听说」的 ETSShell.exe 进程
- 依赖 frida；如未安装: pip install frida
"""
import ctypes
import json
import os
import signal
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "frida_winhttp.js")


def load_frida():
    try:
        import frida  # noqa
        return frida
    except Exception:
        pass
    for cand in (os.environ.get("ETS_PYLIBS", ""), os.path.join(HERE, "pylibs"), os.path.join(HERE.parent, "work", "pylibs")):
        if os.path.isdir(cand) and cand not in sys.path:
            sys.path.insert(0, cand)
            try:
                import frida  # noqa
                return frida
            except Exception:
                continue
    return None


def find_browser_pid():
    user32 = ctypes.windll.user32
    hits = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if "E听说" in title or "E听说" in title:
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                hits.append((pid.value, title))
        return True

    user32.EnumWindows(cb, 0)
    if hits:
        return hits[0][0], hits[0][1]
    return None, None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    outdir = os.path.abspath(sys.argv[1])
    os.makedirs(outdir, exist_ok=True)
    pid = None
    if "--pid" in sys.argv:
        pid = int(sys.argv[sys.argv.index("--pid") + 1])

    frida = load_frida()
    if frida is None:
        print("[native] 缺少 frida：请先执行  python -m pip install frida")
        return 2

    title = ""
    if not pid:
        pid, title = find_browser_pid()
    if not pid:
        print("[native] 没找到「E听说」窗口进程；请确认官方客户端已启动，或用 --pid 指定 ETSShell.exe 主进程")
        return 3
    print(f"[native] 目标进程 pid={pid} {title}")

    fd = open(os.path.join(outdir, "native_http.jsonl"), "a", encoding="utf-8")
    counts = {"http": 0, "ws": 0, "plugin": 0}
    stop = {"v": False}

    def on_message(message, data):
        if message.get("type") == "send":
            payload = message.get("payload") or {}
            kind = payload.get("type")
            if kind in ("http", "ws", "ws_close", "error", "ready", "plugin", "dbg"):
                payload["t"] = datetime.now().isoformat()
                fd.write(json.dumps(payload, ensure_ascii=False) + "\n")
                fd.flush()
                if kind == "ready":
                    print("[native]", payload.get("msg"), "plugins=", payload.get("plugins"), "ws=", payload.get("ws"))
                elif kind == "http":
                    counts["http"] += 1
                    print(f"[HTTP] {payload.get('verb')} {payload.get('host')}{payload.get('path')} -> {payload.get('status')}")
                elif kind == "ws":
                    counts["ws"] += 1
                    print(f"[WS] {payload.get('dir')} opcode={payload.get('opcode')} bytes={len(payload.get('dataB64') or '')}")
                elif kind == "plugin":
                    counts["plugin"] += 1
                    if payload.get("phase") == "call":
                        print(f"[PLUGIN] {payload.get('plugin')}.{payload.get('action')} args={len(payload.get('args') or '')}B")
                    else:
                        print(f"[RESULT] uid={str(payload.get('uid'))[:18]} data={len(payload.get('data') or '')}B")
                elif kind == "error":
                    print("[native] error:", payload.get("msg"))
        elif message.get("type") == "error":
            print("[native] script error:", message.get("stack") or message.get("description"))

    session = frida.attach(pid)
    script = session.create_script(open(AGENT, encoding="utf-8").read())
    script.on("message", on_message)
    script.load()
    print("[native] 采集已开始（Ctrl+C 停止）")

    def handle(signum, frame):
        stop["v"] = True

    signal.signal(signal.SIGINT, handle)
    try:
        while not stop["v"]:
            time.sleep(0.3)
    finally:
        try:
            session.detach()
        except Exception:
            pass
        fd.close()
        with open(os.path.join(outdir, "native_done.json"), "w", encoding="utf-8") as f:
            json.dump({"counts": counts, "done": datetime.now().isoformat()}, f, ensure_ascii=False)
        print(f"[native] 已停止 http={counts['http']} ws={counts['ws']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
