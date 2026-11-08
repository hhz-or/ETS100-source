#!/usr/bin/env python3
"""ETS 练习抓包 · 汇总

输入：capture/runs/<ts>/ 下的
  - native_http.jsonl : 插件调用/结果（HttpHelper 请求明文）+ WinHTTP 兜底 + WS
  - ws.jsonl          : CDP 抓到的 WebSocket 帧（ISE 评测等）
  - renderer_http.jsonl: 渲染进程请求
  - logs.jsonl        : 客户端日志新增行
  - files.jsonl       : 新增文件清单
输出：REPORT.md / api_calls.json / plugin_calls.json / ws_samples.json / files_index.json（已脱敏）

用法: python summarize.py <抓包目录>
"""
import base64
import json
import os
import re
import sys
from collections import Counter, defaultdict


JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
SECRET_KEYS = {"token", "password", "passwd", "phone", "raw_phone", "bind_mobile", "mobile", "secret", "authorization"}


def mask_str(s):
    if not isinstance(s, str):
        return s
    s = JWT.sub("***JWT***", s)
    s = PHONE.sub("1**********", s)
    s = s.replace("陈一天", "***")
    return s


def mask_obj(o, depth=0):
    if depth > 8:
        return "…"
    if isinstance(o, dict):
        return {k: ("***" if str(k).lower() in SECRET_KEYS and isinstance(v, (str, int)) else mask_obj(v, depth + 1)) for k, v in o.items()}
    if isinstance(o, list):
        return [mask_obj(x, depth + 1) for x in o[:20]]
    if isinstance(o, str):
        return mask_str(o)[:2000]
    return o


def b64d(s):
    try:
        return base64.b64decode(s or "", validate=False)
    except Exception:
        return b""


def try_json(b):
    try:
        return json.loads(b.decode("utf-8", "replace"))
    except Exception:
        return None


def short(o, n=1200):
    s = o if isinstance(o, str) else json.dumps(o, ensure_ascii=False)
    return s[:n] + ("…" if len(s) > n else "")


def read_jsonl(p):
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def decode_envelope(body_bytes):
    j = try_json(body_bytes)
    if isinstance(j, dict) and isinstance(j.get("body"), str):
        return {"head": mask_obj(j.get("head") or {}), "items": mask_obj(try_json(b64d(j["body"])))}
    return {"raw": mask_str(body_bytes[:1500].decode("utf-8", "replace"))}


def decode_api_response(body_bytes):
    j = try_json(body_bytes)
    if isinstance(j, list) and j and isinstance(j[0], dict):
        item = j[0]
        return {"code": item.get("code"), "msg": mask_str(str(item.get("msg") or "")),
                "bodyKeys": list((item.get("body") or {}).keys())[:40], "bodySample": mask_obj(item.get("body"))}
    if j is not None:
        return {"json": mask_obj(j)}
    return {"raw": mask_str(body_bytes[:1500].decode("utf-8", "replace"))}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    root = os.path.abspath(sys.argv[1])
    native = read_jsonl(os.path.join(root, "native_http.jsonl"))
    cdp_ws = read_jsonl(os.path.join(root, "ws.jsonl"))
    cdp_http = read_jsonl(os.path.join(root, "renderer_http.jsonl"))
    logs = read_jsonl(os.path.join(root, "logs.jsonl"))
    files = read_jsonl(os.path.join(root, "files.jsonl"))

    calls = {}      # uid -> call
    api = []        # HttpHelper.request 明细
    other = []      # 其它插件调用
    action_counts = Counter()
    for ev in native:
        t = ev.get("type")
        if t == "plugin" and ev.get("phase") == "call":
            uid = ev.get("uid")
            calls[uid] = ev
            action_counts[f"{ev.get('plugin')}.{ev.get('action')}"] += 1
        elif t == "plugin" and ev.get("phase") == "result":
            uid = ev.get("uid")
            call = calls.pop(uid, None)
            if not call:
                continue
            plugin, action = call.get("plugin"), call.get("action")
            try:
                args = json.loads(call.get("args") or "{}")
            except Exception:
                args = {"_raw": call.get("args")}
            try:
                result = json.loads(ev.get("data") or "{}")
            except Exception:
                result = {"_raw": ev.get("data")}
            if plugin == "HttpHelper" and action == "request":
                url = str(args.get("url") or "")
                method = str(args.get("method") or "GET").upper()
                body = args.get("body") or ""
                m = re.match(r"https?://([^/]+)(/.*)?$", url)
                host = m.group(1) if m else ""
                path = (m.group(2) if m else url)
                rec = {
                    "method": method, "host": host, "path": path,
                    "status": result.get("status"),
                    "request": decode_envelope(body.encode("utf-8", "replace")) if body else {},
                    "response": decode_api_response((result.get("body") or "").encode("utf-8", "replace")) if result.get("body") is not None else mask_obj(result),
                    "truncated": ev.get("data", "") and "<truncated>" in (ev.get("data") or ""),
                }
                api.append(rec)
            else:
                other.append({"plugin": plugin, "action": action, "args": mask_obj(args), "result": mask_obj(result)})
        elif t == "http":
            api.append({
                "method": ev.get("verb"), "host": ev.get("host"), "path": ev.get("path"),
                "status": ev.get("status"), "request": decode_envelope(b64d(ev.get("reqB64"))),
                "response": decode_api_response(b64d(ev.get("respB64"))), "source": "winhttp"
            })
        elif t == "ws":
            pass

    # 没有配对到结果的调用：请求参数仍然有效（响应可从 logs.jsonl 的 API_ETS 行获取）
    for uid, call in list(calls.items()):
        plugin, action = call.get("plugin"), call.get("action")
        try:
            args = json.loads(call.get("args") or "{}")
        except Exception:
            args = {"_raw": call.get("args")}
        if plugin == "HttpHelper" and action == "request":
            url = str(args.get("url") or "")
            method = str(args.get("method") or "GET").upper()
            body = args.get("body") or ""
            m = re.match(r"https?://([^/]+)(/.*)?$", url)
            api.append({
                "method": method,
                "host": m.group(1) if m else "",
                "path": (m.group(2) if m else url),
                "status": None,
                "request": decode_envelope(body.encode("utf-8", "replace")) if body else {},
                "response": {"note": "响应未捕获；见 logs.jsonl 中 API_ETS response 行"},
                "source": "plugin-call"
            })
        else:
            other.append({"plugin": plugin, "action": action, "args": mask_obj(args), "result": {"note": "result 未捕获；见 logs.jsonl"}})

    # WS 汇总（CDP 文本帧 + 原生二进制帧）
    ws_events = []
    for ev in cdp_ws:
        if ev.get("kind") in ("send", "recv"):
            ws_events.append({"dir": ev.get("kind"), "opcode": ev.get("opcode"), "text": ev.get("text"), "url": ev.get("id"), "source": "cdp"})
    for ev in native:
        if ev.get("type") == "ws":
            ws_events.append({"dir": ev.get("dir"), "opcode": ev.get("opcode"), "dataB64": ev.get("dataB64"), "source": "native"})
    ws_sessions = [e for e in cdp_ws if e.get("kind") in ("created", "handshake", "closed")]
    ws_samples = []
    for ev in ws_events[:300]:
        if ev.get("text"):
            ws_samples.append({"source": ev.get("source"), "dir": ev.get("dir"), "opcode": ev.get("opcode"), "text": mask_str(ev["text"][:1500])})
        else:
            b = b64d(ev.get("dataB64"))
            ws_samples.append({"source": ev.get("source"), "dir": ev.get("dir"), "opcode": ev.get("opcode"), "bytes": len(b), "preview": mask_str(b[:800].decode("utf-8", "replace"))})

    # 渲染进程 / 日志 / 文件
    host_counts = Counter()
    for e in cdp_http:
        if e.get("kind") == "request":
            m = re.match(r"https?://([^/]+)", e.get("url") or "")
            if m:
                host_counts[m.group(1)] += 1
    interesting = []
    pat = re.compile(r"API_ETS|ets request|ets response|submit|checkstart|audio|eval|评分|评测|上传|oss|ISE|record|spx|sync|start|finish", re.I)
    for e in logs:
        line = e.get("line") or ""
        if pat.search(line):
            interesting.append({"file": e.get("file"), "line": mask_str(line)[:800]})
    file_index = [{"rel": f.get("rel"), "size": f.get("size"), "md5": f.get("md5")} for f in files]
    ext_counts = Counter(os.path.splitext(f.get("rel") or "")[1].lower() for f in files)

    with open(os.path.join(root, "api_calls.json"), "w", encoding="utf-8") as f:
        json.dump(api, f, ensure_ascii=False, indent=1)
    with open(os.path.join(root, "plugin_calls.json"), "w", encoding="utf-8") as f:
        json.dump({"actions": dict(action_counts), "calls": other[:500]}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(root, "ws_samples.json"), "w", encoding="utf-8") as f:
        json.dump({"sessions": ws_sessions, "events": ws_samples}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(root, "files_index.json"), "w", encoding="utf-8") as f:
        json.dump({"files": file_index, "ext": dict(ext_counts)}, f, ensure_ascii=False, indent=1)

    lines = ["# ETS 练习抓包 · 汇总\n",
             f"- 目录：`{root}`",
             f"- 插件调用：{sum(action_counts.values())} 次（{len(action_counts)} 种 action）",
             f"- API 请求（HttpHelper 明文）：{len(api)} 条",
             f"- WebSocket：{len(ws_events)} 帧 / 会话事件 {len(ws_sessions)}",
             f"- 渲染进程请求：{sum(host_counts.values())} 条；日志新行 {len(logs)}；新文件 {len(files)} {dict(ext_counts)}",
             "", "## 一、插件 action 统计\n", "| action | 次数 |", "|---|---|"]
    for k, v in action_counts.most_common():
        lines.append(f"| `{k}` | {v} |")
    lines += ["", "## 二、HTTP API（明文，脱敏）\n", "| 方法 | 主机 | 路径 | 状态 |", "|---|---|---|---|"]
    for r in api[:200]:
        lines.append(f"| {r['method']} | {r['host']} | {r['path']} | {r.get('status')} |")
    lines += ["", "### 请求/响应样例\n"]
    for r in api[:80]:
        lines += [f"#### {r['method']} {r['host']}{r['path']} · status={r.get('status')}",
                  "请求：```json\n" + short(r.get("request")) + "\n```",
                  "响应：```json\n" + short(r.get("response")) + "\n```", ""]
    lines += ["## 三、其它插件调用（录音/上传/解压等）\n"]
    for o in other[:80]:
        lines.append(f"### {o['plugin']}.{o['action']}")
        lines.append("args：```json\n" + short(o.get("args")) + "\n```")
        lines.append("result：```json\n" + short(o.get("result")) + "\n```")
        lines.append("")
    lines += ["## 四、WebSocket（ISE 评测等）\n"]
    for s in ws_sessions[:30]:
        lines.append(f"- {s}")
    for s in ws_samples[:120]:
        lines.append("- " + short(s, 800))
    lines += ["", "## 五、渲染进程域名\n"]
    for h, c in host_counts.most_common(30):
        lines.append(f"- {h}: {c}")
    lines += ["", "## 六、客户端日志线索（脱敏）\n"]
    for s in interesting[:150]:
        lines.append(f"- [{s['file']}] {s['line']}")
    lines += ["", "## 七、新增文件\n"]
    for f in file_index[:120]:
        lines.append(f"- `{f['rel']}` · {f['size']}B · md5={f['md5']}")
    lines.append("")
    with open(os.path.join(root, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("已生成:", os.path.join(root, "REPORT.md"))
    print("  api_calls.json / plugin_calls.json / ws_samples.json / files_index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
