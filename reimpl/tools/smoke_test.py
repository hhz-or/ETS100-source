#!/usr/bin/env python3
"""参考客户端本地验收脚本（只读，不触发登录）。

用法：
    python reimpl/server.py              # 另开一个终端
    python reimpl/tools/smoke_test.py    # 默认 http://127.0.0.1:8787

检查项：
  1. GET / 返回 HTML
  2. /api/status 已登录（token 可用）
  3. /api/home、/api/homework、/api/homework/<id>、/api/modules、/api/sets、
     /api/courses、/api/mistakes、/api/ecards、/api/config、/api/about 均返回 ok
  4. /api/content 下载并解密一个 content 包，/api/audio 能取回 MP3 字节
  5. 输出实测摘要，失败时退出码非 0

不打印 token、手机号、密码等敏感值。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"
TIMEOUT = 90
results: list[tuple[str, bool, str]] = []


def request(path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, bytes, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read(), {"elapsed": time.time() - started}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {"elapsed": time.time() - started}


def check(name: str, path: str, validate=None, method: str = "GET", payload: dict | None = None):
    try:
        status, raw, meta = request(path, method, payload)
        data = json.loads(raw.decode("utf-8")) if raw[:1] in (b"{", b"[") else raw
        ok = status == 200
        detail = f"HTTP {status} · {meta['elapsed']:.2f}s"
        if ok and isinstance(data, dict) and data.get("ok") is False:
            ok = False
            detail += " · " + str((data.get("error") or {}).get("message"))[:120]
        if ok and validate:
            extra_ok, extra_detail = validate(data if isinstance(data, dict) else {})
            ok = ok and extra_ok
            detail += " · " + extra_detail
        results.append((name, ok, detail))
        return data if ok else None
    except Exception as exc:  # noqa: BLE001
        results.append((name, False, f"{type(exc).__name__}: {exc}"))
        return None


def payload(data: dict) -> dict:
    return (data or {}).get("data") or {}


def main() -> int:
    print(f"== E 听说参考客户端验收：{BASE} ==")
    try:
        status, raw, _ = request("/")
        html = raw.decode("utf-8", "replace")
        ok = status == 200 and "<html" in html.lower() and "app.js" in html
        results.append(("GET / 返回 HTML", ok, f"HTTP {status} · {len(raw)} B"))
    except Exception as exc:  # noqa: BLE001
        results.append(("GET / 返回 HTML", False, str(exc)))
        print("后端未启动，无法继续。")
        return 2

    status = check("GET /api/status", "/api/status", lambda d: (bool(d.get("loggedIn")), "loggedIn=" + str(d.get("loggedIn")) + " · source=" + str(d.get("tokenSource"))))

    home = check("GET /api/home", "/api/home", lambda d: (bool(payload(d).get("homework")), "todo=" + str(((payload(d).get("homework") or {}).get("counts") or {}).get("todo"))))
    check("GET /api/homework?tab=todo", "/api/homework?tab=todo", lambda d: (bool(payload(d).get("items") is not None), "total=" + str(payload(d).get("total"))))
    check("GET /api/homework?tab=done", "/api/homework?tab=done", lambda d: (bool(payload(d).get("items") is not None), "total=" + str(payload(d).get("total"))))
    check("GET /api/modules", "/api/modules", lambda d: (bool(payload(d).get("columns")), "columns=" + str([c.get("name") for c in payload(d).get("columns") or []])))
    check("GET /api/sets?column_id=1", "/api/sets?column_id=1&limit=5", lambda d: (bool(payload(d).get("items") is not None), "total=" + str(payload(d).get("total"))))
    check("GET /api/sets?column_id=88", "/api/sets?column_id=88&limit=5", lambda d: (bool(payload(d).get("items") is not None), "total=" + str(payload(d).get("total"))))
    check("GET /api/courses", "/api/courses", lambda d: (bool(payload(d).get("books")), f"books={len(payload(d).get('books') or [])} units={len(payload(d).get('units') or [])}"))
    check("GET /api/mistakes", "/api/mistakes", lambda d: (bool(payload(d).get("summary") is not None), "items=" + str(len(payload(d).get("items") or []))))
    check("GET /api/ecards", "/api/ecards", lambda d: (bool(payload(d).get("items") is not None), "cards=" + str(len(payload(d).get("items") or []))))
    check("GET /api/config", "/api/config", lambda d: (bool(payload(d).get("config")), "keys=" + str(payload(d).get("count"))))
    check("GET /api/about", "/api/about", lambda d: (bool(payload(d).get("endpoints")), "endpoints=" + str(len(payload(d).get("endpoints") or []))))

    # 详情 + 内容包 + 音频（取待完成作业的第一道题）
    todo_items = ((payload(home).get("homework") or {}).get("todo") or []) if home else []
    first_id = todo_items[0].get("id") if todo_items else "0"
    detail = check("GET /api/homework/<id>", f"/api/homework/{first_id}",
                   lambda d: (bool(payload(d).get("structure")), "structs=" + str(len(payload(d).get("structure") or []))))
    item = (payload(detail).get("structure") or [{}])[0] if detail else {}
    contents = item.get("contents") or []
    if contents:
        first = contents[0]
        content = check("GET /api/content（下载 + ZipCrypto 解密）",
                        f"/api/content?stid={first.get('stid')}&zip={first.get('zip_name')}",
                        lambda d: (bool(payload(d).get("content")), str(payload(d).get("structure_type")) + " · " + str(len(payload(d).get("material") or [])) + " 个媒体文件"))
        material = payload(content).get("material") or [] if content else []
        audio = next((m for m in material if m.get("kind") == "audio"), None)
        if audio:
            try:
                status_code, raw, meta = request(audio["url"])
                is_mp3 = raw[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3") or b"ID3" in raw[:16]
                results.append(("GET /api/audio（MP3 播放）", status_code == 200 and len(raw) > 1000 and is_mp3,
                                f"HTTP {status_code} · {len(raw)} B · {meta['elapsed']:.2f}s"))
            except Exception as exc:  # noqa: BLE001
                results.append(("GET /api/audio（MP3 播放）", False, str(exc)))
        else:
            results.append(("GET /api/audio（MP3 播放）", False, "题目无音频 material"))
    else:
        results.append(("GET /api/content（下载 + ZipCrypto 解密）", False, "详情无 contents"))

    print()
    passed = 0
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name:<42} {detail}")
        passed += 1 if ok else 0
    print(f"\n合计：{passed}/{len(results)} 通过")
    if not status:
        print("提示：若 /api/status 未登录，请先在浏览器点击“使用官方客户端 token”或“本机账号登录”。")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
