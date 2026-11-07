#!/usr/bin/env python3
"""E听说（学生端 PC）参考客户端 · 本地 Web 服务器。

用法：
    python reimpl/server.py            # 默认 http://127.0.0.1:8787
    python reimpl/server.py --port 8790 --open

只监听 127.0.0.1，静态托管 static/，/api/* 代理真实 api.ets100.com。
凭据只从仓库外的 <WORK_DIR>/secrets/ 读取；本文件不含任何凭据。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import threading
import time
import traceback
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ets_client as ec  # noqa: E402

VERSION = "0.1.0"
APP_TITLE = "E听说 · 参考客户端"
IMPL_VERSION = "V5.7.9-ref"
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787

NOT_IMPLEMENTED = [
    "录音（麦克风采集 / SndHelper）",
    "ISE / AI 评测（wss://oe-pub.eduaiplat.com，双通道评分）",
    "考试提交 / 作业完成上报（m/audio/sync-v2、g/homework/checkstart 等写接口）",
    "阿里云 OSS / SLS 上传（录音 mp3/spx/xml、埋点日志）",
    "客户端自动更新器（EtsUpdate.exe）",
    "读写模拟题型渲染（服务端返回的 rw_data 无 content 包结构）",
]

SENSITIVE_KEYS = {
    "password",
    "raw_phone",
    "bind_mobile",
    "teacher_phone",
    "family_phone",
    "mobile",
    "machine_code",
    "securityToken",
    "accessKeySecret",
    "accessKeyId",
    "security_token",
    "access_key_secret",
    "access_key_id",
}
AUDIO_EXT = {".mp3", ".wav", ".m4a"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def mask_deep(value):
    """递归遮蔽敏感字段（只用于返回给浏览器的数据）。"""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in SENSITIVE_KEYS and isinstance(item, (str, int)) and str(item):
                text = str(item)
                out[key] = text[:2] + "*" * max(1, len(text) - 2) if len(text) > 2 else "*"
            else:
                out[key] = mask_deep(item)
        return out
    if isinstance(value, list):
        return [mask_deep(item) for item in value]
    return value


def normalize_structs(item: dict) -> list[dict]:
    structs = item.get("structs")
    if not structs and item.get("struct"):
        structs = [item["struct"]]
    result = []
    for struct in structs or []:
        if not isinstance(struct, dict):
            continue
        contents = []
        for content in struct.get("contents") or []:
            if not isinstance(content, dict):
                continue
            contents.append(
                {
                    "code_id": content.get("code_id"),
                    "stid": str(content.get("real_id") or ""),
                    "group_name": content.get("group_name") or content.get("first_type_name") or "",
                    "first_type_name": content.get("first_type_name") or "",
                    "zip_name": content.get("url") or "",
                    "ppr": content.get("ppr") or "",
                    "size": content.get("size") or 0,
                    "read_type": content.get("read_type"),
                    "audio_url": content.get("audio_url") or "",
                }
            )
        template = struct.get("template") or {}
        result.append(
            {
                "set_name": struct.get("set_name") or item.get("set_name") or item.get("name") or "",
                "set_id": str(struct.get("set_id") or item.get("set_id") or ""),
                "template": {"id": str(template.get("id") or ""), "zip_name": template.get("url") or "", "size": template.get("size") or 0},
                "contents": contents,
            }
        )
    return result


def homeworks_to_items(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        rows = normalize_structs(item)
        out.append(
            {
                "id": str(item.get("id") or ""),
                "set_id": str(item.get("set_id") or ""),
                "name": item.get("name") or item.get("set_name") or "",
                "set_name": item.get("set_name") or "",
                "set_module_name": item.get("set_module_name") or "",
                "first_column_name": item.get("first_column_name") or "",
                "first_column_id": str(item.get("first_column_id") or ""),
                "set_module_id": str(item.get("set_module_id") or ""),
                "point": item.get("point"),
                "total_point": item.get("total_point"),
                "complete": item.get("complete"),
                "status": item.get("status"),
                "overtime": item.get("overtime"),
                "pass": item.get("pass"),
                "pass_line": item.get("pass_line"),
                "begin": item.get("begin"),
                "end": item.get("end"),
                "use_time": item.get("use_time"),
                "practise_count": item.get("practise_count"),
                "difficulty_rate": item.get("difficulty_rate"),
                "remark": item.get("remark") or "",
                "introduction": item.get("introduction") or "",
                "engine_area": item.get("engine_area") or "",
                "mock": item.get("mock"),
                "structure": rows,
            }
        )
    return out


def phase_of(item: dict, now_ts: float | None = None) -> str:
    complete = item.get("complete")
    if isinstance(complete, (int, float)) and complete >= 100:
        return "done"
    if item.get("overtime") in (1, True):
        return "overtime"
    end = item.get("end")
    if isinstance(end, (int, float)) and end > 0 and now_ts and end < now_ts:
        return "overtime"
    status = item.get("status")
    if status in (2, True):
        return "overtime"
    return "todo"


def display_class(card: dict | None, user: dict | None = None) -> str:
    card = card or {}
    user = user or {}
    grade = card.get("class_grade") or card.get("grade") or user.get("grade_name") or ""
    name = str(card.get("class_name") or "")
    if name and name.isdigit():
        return f"{grade} {name}班".strip()
    return name or grade


class AppState:
    def __init__(self):
        self.client = ec.EtsClient()
        self.client.resolve_token()
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[float, object]] = {}
        self._hw_cache: tuple[float, list[dict]] | None = None
        self._mistake_cache: tuple[float, dict] | None = None
        self._context_cache: tuple[float, dict] | None = None
        self._set_cache: dict[int, tuple[float, dict]] = {}
        self._login_lock = threading.Lock()
        self.server_time: dict | None = None

    # -- 缓存 ---------------------------------------------------------
    def cache_get(self, key: str, ttl: float):
        with self._lock:
            entry = self._cache.get(key)
            if entry and time.time() - entry[0] < ttl:
                return entry[1]
        return None

    def cache_set(self, key: str, value):
        with self._lock:
            self._cache[key] = (time.time(), value)

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hw_cache = None
            self._mistake_cache = None
            self._context_cache = None
            self._set_cache.clear()
            self.server_time = None

    # -- 登录态 -------------------------------------------------------
    def logged_in(self) -> bool:
        return bool(self.client.token)

    def require_login(self) -> None:
        if not self.logged_in():
            raise ec.EtsError("尚未登录。请先点击“使用本机账号登录”或“使用官方客户端 token”。", code=30001)

    # -- 组合上下文 ---------------------------------------------------
    def context(self) -> dict:
        now = time.time()
        with self._lock:
            if self._context_cache and now - self._context_cache[0] < 300:
                return self._context_cache[1]
        self.require_login()
        user = self.client.user_info() or {}
        try:
            ecards_body = self.client.ecard_list() or {}
            ecards = ecards_body.get("data") or []
        except ec.EtsError:
            ecards = []
        card = self.client.current_ecard(ecards)
        parent_account_id = str((card or {}).get("parent_id") or "")
        parent_resource_id = str((card or {}).get("parent_resource_id") or "")
        grade = None
        grades: list[dict] = []
        if parent_resource_id:
            try:
                grades_body = self.client.grade_list(parent_resource_id) or {}
                grades = grades_body.get("grades") or []
                grade = next((g for g in grades if g.get("id") == user.get("grade_id")), None)
            except ec.EtsError:
                grades = []
        resource_id = str((grade or {}).get("resource_id") or "")
        ctx = {
            "user": user,
            "ecards": ecards,
            "ecard": card,
            "parent_account_id": parent_account_id,
            "parent_resource_id": parent_resource_id,
            "grades": grades,
            "grade": grade,
            "resource_id": resource_id,
            "grade_name": user.get("grade_name") or "",
        }
        with self._lock:
            self._context_cache = (now, ctx)
        return ctx

    def get_server_time(self) -> dict:
        with self._lock:
            if self.server_time:
                return self.server_time
        try:
            data = self.client.system_time() or {}
        except ec.EtsError:
            data = {}
        with self._lock:
            self.server_time = data
        return data

    def homeworks_all(self, limit: int = 30) -> list[dict]:
        ctx = self.context()
        now = time.time()
        with self._lock:
            if self._hw_cache and now - self._hw_cache[0] < 60:
                return self._hw_cache[1]
        items = self.client.homeworks(ctx["parent_account_id"], statuses=(0, 2, 3), limit=limit)
        normalized = homeworks_to_items(items)
        with self._lock:
            self._hw_cache = (now, normalized)
        return normalized

    def find_homework(self, homework_id: str) -> dict | None:
        for item in self.homeworks_all():
            if item["id"] == homework_id:
                return item
        # 缓存过期时刷新一次
        with self._lock:
            self._hw_cache = None
        for item in self.homeworks_all():
            if item["id"] == homework_id:
                return item
        return None

    def mistakes(self) -> dict:
        ctx = self.context()
        now = time.time()
        with self._lock:
            if self._mistake_cache and now - self._mistake_cache[0] < 60:
                return self._mistake_cache[1]
        summary = {}
        try:
            summary = self.client.mistake_summary(ctx["parent_account_id"]) or {}
        except ec.EtsError:
            summary = {}
        items: list[dict] = []
        list_error = None
        for type_ in (1, 2):
            try:
                body = self.client.mistake_list(ctx["parent_account_id"], type_=type_, limit=50) or {}
                for row in body.get("mistake") or []:
                    row["_mistake_type"] = type_
                    items.append(row)
            except ec.EtsError as exc:
                list_error = exc.to_dict()
        result = {"summary": summary, "items": items, "base_url": ec.CONTENT_BASE, "list_error": list_error}
        with self._lock:
            self._mistake_cache = (now, result)
        return result

    def modules(self) -> dict:
        ctx = self.context()
        cache_key = f"modules:{ctx.get('resource_id')}"
        cached = self.cache_get(cache_key, 120)
        if cached is not None:
            return cached
        resource_id = ctx.get("resource_id") or "239"
        body = self.client.column_v2(resource_id, tag_id=1) or {}
        columns = []
        for row in body.get("data") or []:
            columns.append(
                {
                    "id": row.get("column_id"),
                    "name": row.get("column_name") or "",
                    "count": row.get("column_set_count") or 0,
                    "complete_count": row.get("column_set_complete_count") or 0,
                    "score_average": row.get("column_score_average") or 0,
                }
            )
        expand = {}
        try:
            expand = self.client.expand_module(ctx.get("parent_resource_id") or "274", ctx.get("parent_account_id")) or {}
        except ec.EtsError:
            expand = {}
        data = {"resource_id": resource_id, "columns": columns, "expand": expand}
        self.cache_set(cache_key, data)
        return data

    def sets_for_column(self, column_id: int) -> dict:
        ctx = self.context()
        resource_id = ctx.get("resource_id") or "239"
        now = time.time()
        with self._lock:
            entry = self._set_cache.get(column_id)
            if entry and now - entry[0] < 120:
                return entry[1]
        body = self.client.set_list(resource_id, first_column_id=[column_id]) or {}
        items: list[dict] = []
        for row in body.get("data") or []:
            if not isinstance(row, dict):
                continue
            rows = normalize_structs(row)
            items.append(
                {
                    "id": str(row.get("id") or ""),
                    "name": row.get("name") or row.get("set_name") or "",
                    "set_name": row.get("set_name") or row.get("name") or "",
                    "column": row.get("column") or row.get("first_column_name") or "",
                    "first_column_name": row.get("first_column_name") or "",
                    "size": row.get("size") or 0,
                    "set_type": row.get("set_type"),
                    "link": row.get("link") or "",
                    "cover": row.get("cover") or "",
                    "create": row.get("create") or "",
                    "difficulty_rate": row.get("difficulty_rate"),
                    "structure": rows,
                }
            )
        for row in body.get("rw_data") or []:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "id": str(row.get("id") or ""),
                    "name": row.get("name") or "",
                    "set_name": row.get("name") or "",
                    "column": row.get("column") or "",
                    "first_column_name": row.get("column") or "读写模拟",
                    "size": row.get("size") or 0,
                    "set_type": row.get("type"),
                    "link": "",
                    "cover": "",
                    "create": "",
                    "difficulty_rate": row.get("difficulty_rate"),
                    "structure": [],
                    "rw": True,
                }
            )
        counts = []
        for count in body.get("set_count") or []:
            if isinstance(count, dict):
                counts.append({"column_id": count.get("column_id"), "count": count.get("count")})
        data = {"column_id": column_id, "resource_id": resource_id, "items": items, "counts": counts}
        with self._lock:
            self._set_cache[column_id] = (now, data)
        return data

    def course(self, book_id: str | None = None, unit_id: str | None = None) -> dict:
        ctx = self.context()
        cache_key = f"course:{book_id}:{unit_id}"
        cached = self.cache_get(cache_key, 180)
        if cached is not None:
            return cached
        books: list[dict] = []
        grades = ctx.get("grades") or []
        parent_resource_id = ctx.get("parent_resource_id") or "274"
        try:
            books = (self.client.book_list(parent_resource_id) or {}).get("books") or []
        except ec.EtsError:
            books = []
        grade_name = ctx.get("grade_name") or ""
        grade_books = [b for b in books if b.get("grade_name") == grade_name] or books
        selected_book = None
        if book_id:
            selected_book = next((b for b in books if str(b.get("id")) == str(book_id)), None)
        if not selected_book and grade_books:
            selected_book = grade_books[0]
        units: list[dict] = []
        modules: list[dict] = []
        if selected_book:
            try:
                units = (self.client.unit_list(selected_book.get("resource_id"), selected_book.get("id")) or {}).get("data") or []
            except ec.EtsError:
                units = []
            selected_unit = None
            if unit_id:
                selected_unit = next((u for u in units if str(u.get("unit_id")) == str(unit_id)), None)
            if not selected_unit and units:
                selected_unit = units[0]
            if selected_unit:
                try:
                    module_body = self.client.module_list(
                        selected_book.get("resource_id"), selected_book.get("id"), selected_unit.get("unit_id")
                    ) or {}
                    modules = module_body.get("data") or []
                except ec.EtsError:
                    modules = []
        data = {
            "grades": grades,
            "books": books,
            "grade_books": grade_books,
            "selected": {
                "book_id": selected_book.get("id") if selected_book else None,
                "resource_id": selected_book.get("resource_id") if selected_book else None,
                "unit_id": (modules and None) or None,
            },
            "units": units,
            "modules": modules,
            "selected_unit_id": None,
        }
        if selected_book and units:
            selected_unit = None
            if unit_id:
                selected_unit = next((u for u in units if str(u.get("unit_id")) == str(unit_id)), None)
            selected_unit = selected_unit or units[0]
            data["selected_unit_id"] = selected_unit.get("unit_id")
            data["selected"]["unit_id"] = selected_unit.get("unit_id")
        self.cache_set(cache_key, data)
        return data


STATE = AppState()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "ETSRef/" + VERSION
    protocol_version = "HTTP/1.1"

    # -- 基础输出 -----------------------------------------------------
    def _send_bytes(self, data: bytes, content_type: str, status: int = 200,
                    extra_headers: dict | None = None, cache_control: str = "no-cache"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _send_json(self, payload, status: int = 200):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status)

    def _send_error_json(self, exc: Exception, status: int = 500):
        if isinstance(exc, ec.EtsError):
            code = exc.code
            if code == 20004:
                status = 409
            elif code == 30001:
                status = 401
            elif status == 500:
                status = 502
            self._send_json({"ok": False, "error": exc.to_dict()}, status)
        else:
            log("内部错误: " + "".join(traceback.format_exception(exc)))
            self._send_json({"ok": False, "error": {"message": "服务器内部错误", "detail": str(exc)}}, 500)

    def _send_file(self, path: Path, content_type: str | None = None):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self._send_json({"ok": False, "error": {"message": "文件不存在"}}, 404)
            return
        ctype = content_type or CONTENT_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        cache = "public, max-age=86400" if ctype.startswith(("audio/", "image/")) else "no-cache"
        range_header = self.headers.get("Range")
        if range_header and ctype.startswith(("audio/", "image/")):
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if match:
                total = len(data)
                start = int(match.group(1)) if match.group(1) else 0
                end = int(match.group(2)) if match.group(2) else total - 1
                start = max(0, min(start, total - 1))
                end = max(start, min(end, total - 1))
                chunk = data[start : end + 1]
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", cache)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(chunk)
                return
        self._send_bytes(data, ctype, extra_headers={"Accept-Ranges": "bytes"}, cache_control=cache)

    # -- 路由 ---------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/"):
                self.handle_api("GET", parsed.path, parse_qs(parsed.query))
            else:
                self.serve_static(parsed.path)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # pragma: no cover
            self._send_error_json(exc)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/"):
                self.handle_api("HEAD", parsed.path, parse_qs(parsed.query))
            else:
                self.serve_static(parsed.path)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # pragma: no cover
            self._send_error_json(exc)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/"):
                self.handle_api("POST", parsed.path, parse_qs(parsed.query))
            else:
                self._send_json({"ok": False, "error": {"message": "只支持 GET/HEAD"}}, 405)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # pragma: no cover
            self._send_error_json(exc)

    def read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 1024 * 1024))
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            raise ec.EtsError("请求体不是合法 JSON", code=10001)

    # -- 静态文件 -----------------------------------------------------
    def serve_static(self, path: str):
        clean = unquote(path)
        if clean in ("", "/"):
            clean = "/index.html"
        target = (STATIC_DIR / clean.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve()) + os.sep) and target != STATIC_DIR.resolve():
            self._send_json({"ok": False, "error": {"message": "非法路径"}}, 400)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            # SPA 回退：未知前端路由返回 index.html
            target = STATIC_DIR / "index.html"
        self._send_file(target)

    # -- API ----------------------------------------------------------
    def handle_api(self, method: str, path: str, query: dict):
        def q(name: str, default: str | None = None) -> str | None:
            values = query.get(name)
            return unquote(values[0]) if values else default

        try:
            if path == "/api/status" and method in ("GET", "HEAD"):
                return self._send_json(status_payload())
            if path == "/api/about" and method in ("GET", "HEAD"):
                return self._send_json(about_payload())
            if path == "/api/login" and method == "POST":
                body = self.read_json_body()
                return self._send_json(login_payload(body))
            if path == "/api/logout" and method == "POST":
                STATE.client.clear_saved_token()
                STATE.invalidate()
                return self._send_json({"ok": True, "data": status_payload()})
            if path == "/api/home" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": home_payload()})
            if path == "/api/homework" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": homework_payload(q("tab", "todo"), int(q("offset", "0") or 0), int(q("limit", "20") or 20))})
            m = re.fullmatch(r"/api/homework/([^/]+)", path)
            if m and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": homework_detail(m.group(1))})
            if path == "/api/modules" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": STATE.modules()})
            if path == "/api/sets" and method in ("GET", "HEAD"):
                column_id = int(q("column_id", "1") or 1)
                offset = int(q("offset", "0") or 0)
                limit = int(q("limit", "24") or 24)
                search = (q("q", "") or "").strip().lower()
                return self._send_json({"ok": True, "data": sets_payload(column_id, offset, limit, search)})
            if path == "/api/sets/detail" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": set_detail(int(q("column_id", "1") or 1), q("set_id", "") or "")})
            if path == "/api/courses" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": STATE.course(q("book_id"), q("unit_id"))})
            if path == "/api/content" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": content_payload(q("stid", "") or "", q("zip", "") or "")})
            if path == "/api/template" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": template_payload(q("template_id", "") or "", q("zip", "") or "")})
            if path == "/api/config" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": config_payload()})
            if path == "/api/mistakes" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": mistakes_payload()})
            m = re.fullmatch(r"/api/mistake/([^/]+)", path)
            if m and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": mistake_detail(m.group(1))})
            if path == "/api/ecards" and method in ("GET", "HEAD"):
                return self._send_json({"ok": True, "data": ecards_payload()})
            m = re.fullmatch(r"/api/audio/([0-9]+)/(.+)", path)
            if m and method in ("GET", "HEAD"):
                return self.serve_media("audio", m.group(1), m.group(2))
            m = re.fullmatch(r"/api/asset/([0-9]+)/(.+)", path)
            if m and method in ("GET", "HEAD"):
                return self.serve_media("asset", m.group(1), m.group(2))
            m = re.fullmatch(r"/api/template-audio/([0-9]+)/(.+)", path)
            if m and method in ("GET", "HEAD"):
                return self.serve_media("template-audio", m.group(1), m.group(2))
            if path == "/api/remote-audio" and method in ("GET", "HEAD"):
                url = q("url", "") or ""
                return self.serve_remote_media(url)
            self._send_json({"ok": False, "error": {"message": f"未知接口：{path}"}}, 404)
        except Exception as exc:
            self._send_error_json(exc)

    def serve_media(self, kind: str, item_id: str, rel_path: str):
        rel_path = unquote(rel_path)
        if kind == "template-audio":
            path = STATE.client.template_media_path(item_id, rel_path)
        else:
            path = STATE.client.content_media_path(item_id, rel_path)
        if path is None:
            self._send_json({"ok": False, "error": {"message": "媒体文件不存在（资源包可能尚未下载）"}}, 404)
            return
        self._send_file(path)

    def serve_remote_media(self, url: str):
        if not url:
            self._send_json({"ok": False, "error": {"message": "缺少 url 参数"}}, 400)
            return
        path = STATE.client.cache_remote_media(url)
        self._send_file(path)

    def log_message(self, fmt, *args):  # 降噪：只记录 API 请求
        if "/api/" in self.path:
            log(f"{self.address_string()} {fmt % args}")


# ---------------------------------------------------------------------------
# 业务聚合
# ---------------------------------------------------------------------------


def status_payload() -> dict:
    data = {
        "ok": True,
        "loggedIn": STATE.logged_in(),
        "tokenSource": STATE.client.token_source,
        "tokenMasked": STATE.client.mask_token(),
        "version": IMPL_VERSION,
        "title": APP_TITLE,
        "notImplemented": NOT_IMPLEMENTED,
        "secrets": {
            "accountFile": str(ec.ACCOUNT_FILE),
            "accountFileExists": ec.ACCOUNT_FILE.is_file(),
            "appTokenFile": str(ec.APP_TOKEN_FILE),
            "appTokenFileExists": ec.APP_TOKEN_FILE.is_file(),
        },
        "stateDir": str(ec.STATE_DIR),
    }
    if STATE.logged_in():
        try:
            ctx = STATE.context()
            user = ctx["user"]
            data["user"] = mask_deep(
                {
                    "name": user.get("name"),
                    "phone": user.get("phone"),
                    "raw_phone": user.get("raw_phone"),
                    "grade_name": user.get("grade_name"),
                    "school_year_name": user.get("school_year_name"),
                    "class_name": display_class(ctx.get("ecard"), user),
                    "city_name": user.get("city_name"),
                    "province_name": user.get("province_name"),
                    "cover": user.get("cover"),
                    "recent_account_id": user.get("recent_account_id"),
                }
            )
            data["ecard"] = mask_deep(
                {
                    "number": (ctx.get("ecard") or {}).get("number"),
                    "name": (ctx.get("ecard") or {}).get("name"),
                    "class_name": display_class(ctx.get("ecard"), user),
                    "grade": (ctx.get("ecard") or {}).get("class_grade") or (ctx.get("ecard") or {}).get("grade"),
                    "expire_time": (ctx.get("ecard") or {}).get("expire_time"),
                    "parent_id": (ctx.get("ecard") or {}).get("parent_id"),
                }
            )
            data["serverTime"] = STATE.get_server_time()
        except ec.EtsError as exc:
            data["loggedIn"] = False
            data["authError"] = exc.to_dict()
    return data


def login_payload(body: dict) -> dict:
    mode = (body.get("mode") or "auto").strip()
    with STATE._login_lock:
        try:
            if mode == "account":
                STATE.client.login_with_account_file()
            elif mode == "token":
                token = (body.get("token") or "").strip() or None
                STATE.client.use_existing_token(token)
            elif mode == "auto":
                if STATE.logged_in():
                    STATE.client.user_info()
                else:
                    STATE.client.resolve_token()
                    if not STATE.logged_in():
                        raise ec.EtsError("没有可用 token，请选择一种登录方式。", code=30001)
                    STATE.client.user_info()
            else:
                raise ec.EtsError(f"未知登录方式：{mode}", code=10001)
        finally:
            STATE.invalidate()
    log(f"登录成功，token 来源={STATE.client.token_source}")
    return status_payload()


def about_payload() -> dict:
    return {
        "ok": True,
        "data": {
            "title": APP_TITLE,
            "version": IMPL_VERSION,
            "targetVersion": ec.GLOBAL_CLIENT_VERSION,
            "endpoints": ec.READONLY_ENDPOINTS,
            "notImplemented": NOT_IMPLEMENTED,
            "notes": [
                "仅调用只读接口；不发送录音、不做评测、不提交作业、不上传 OSS。",
                "凭据只从 secrets/ 读取，reimpl/ 内不保存凭据副本；token 仅写入 .state/token.json（.gitignore）。",
                "题库 content 包按 docs/06_data.md §4.2 的 336 字节口令块派生 ZipCrypto 口令后本地解密。",
            ],
            "signature": "MD5(pcWin + time_ms + base64(body) + KEY_V2)",
            "aes": "AES-128-ECB / k_serves，仅用于登录 phone/password 字段",
        },
    }


def home_payload() -> dict:
    ctx = STATE.context()
    errors: list[dict] = []
    result: dict = {
        "user": mask_deep(
            {
                "name": ctx["user"].get("name"),
                "phone": ctx["user"].get("phone"),
                "raw_phone": ctx["user"].get("raw_phone"),
                "grade_name": ctx["user"].get("grade_name"),
                "school_year_name": ctx["user"].get("school_year_name"),
                "city_name": ctx["user"].get("city_name"),
                "province_name": ctx["user"].get("province_name"),
                "cover": ctx["user"].get("cover"),
                "recent_account_id": ctx["user"].get("recent_account_id"),
                "class_name": display_class(ctx.get("ecard"), ctx["user"]),
            }
        ),
        "ecard": mask_deep(
            {
                "number": (ctx.get("ecard") or {}).get("number"),
                "name": (ctx.get("ecard") or {}).get("name"),
                "class_name": display_class(ctx.get("ecard"), ctx["user"]),
                "grade": (ctx.get("ecard") or {}).get("class_grade") or (ctx.get("ecard") or {}).get("grade"),
                "expire_time": (ctx.get("ecard") or {}).get("expire_time"),
            }
        ),
        "serverTime": STATE.get_server_time(),
        "predictedScore": {
            "value": None,
            "available": False,
            "reason": "原作成长/预测分接口未在本次只读接口清单中开放，参考客户端不伪造分数。",
        },
        "errors": errors,
    }

    def safe(name, fn, default):
        try:
            return name, fn(), None
        except ec.EtsError as exc:
            return name, default, exc.to_dict()
        except Exception as exc:  # pragma: no cover
            return name, default, {"message": str(exc)}

    jobs = [
        ("homework", lambda: STATE.homeworks_all(), []),
        ("modules", lambda: STATE.modules(), {"columns": []}),
        ("mistakes", lambda: STATE.mistakes(), {}),
        ("advertisements", lambda: STATE.client.advertisement_list(ctx.get("resource_id") or "239"), {}),
        ("announcement", lambda: STATE.client.announcement_list(), {}),
    ]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(safe, name, fn, default) for name, fn, default in jobs]
        outputs = [f.result() for f in futures]
    for name, value, error in outputs:
        if error:
            errors.append({"scope": name, **error})
    homework = next(v for n, v, _ in outputs if n == "homework") or []
    modules = next(v for n, v, _ in outputs if n == "modules") or {"columns": []}
    mistakes = next(v for n, v, _ in outputs if n == "mistakes") or {}
    ads = next(v for n, v, _ in outputs if n == "advertisements") or {}
    announcement = next(v for n, v, _ in outputs if n == "announcement") or {}
    now_ts = _now_ts()
    todo = [h for h in homework if phase_of(h, now_ts) == "todo"]
    done = [h for h in homework if phase_of(h, now_ts) == "done"]
    overtime = [h for h in homework if phase_of(h, now_ts) == "overtime"]
    result["homework"] = {
        "counts": {"all": len(homework), "todo": len(todo), "done": len(done), "overtime": len(overtime)},
        "todo": todo[:6],
        "done": done[:3],
    }
    result["modules"] = modules
    result["mistakes"] = {
        "summary": mistakes.get("summary") or {},
        "items": (mistakes.get("items") or [])[:6],
        "listError": mistakes.get("list_error"),
    }
    result["advertisements"] = (ads or {}).get("advertisement") or []
    result["announcement"] = announcement or {}
    return result


def _now_ts() -> float:
    server = STATE.get_server_time()
    ts = server.get("time_stamp") if isinstance(server, dict) else None
    return float(ts) if ts else time.time()


def homework_payload(tab: str, offset: int, limit: int) -> dict:
    items = STATE.homeworks_all()
    now_ts = _now_ts()
    mapping = {"todo": "todo", "done": "done", "overtime": "overtime", "all": None}
    phase = mapping.get(tab, "todo")
    selected = items if phase is None else [h for h in items if phase_of(h, now_ts) == phase]
    counts = {
        "all": len(items),
        "todo": sum(1 for h in items if phase_of(h, now_ts) == "todo"),
        "done": sum(1 for h in items if phase_of(h, now_ts) == "done"),
        "overtime": sum(1 for h in items if phase_of(h, now_ts) == "overtime"),
    }
    page = selected[offset : offset + limit]
    return {"tab": tab, "counts": counts, "total": len(selected), "offset": offset, "limit": limit, "items": page}


def homework_detail(homework_id: str) -> dict:
    item = STATE.find_homework(homework_id)
    if not item:
        raise ec.EtsError(f"未找到作业：{homework_id}", code=10001)
    return detail_from_item(item, kind="homework")


def detail_from_item(item: dict, kind: str = "homework") -> dict:
    structure = item.get("structure") or []
    template_summary = None
    first_template = None
    for struct in structure:
        if struct.get("template", {}).get("id"):
            first_template = struct["template"]
            break
    if first_template:
        try:
            tpl = STATE.client.ensure_template(first_template["id"], first_template["zip_name"])
            template_summary = summarize_template(tpl)
        except ec.EtsError as exc:
            template_summary = {"error": exc.to_dict()}
    return {
        "kind": kind,
        "id": item.get("id"),
        "set_id": item.get("set_id"),
        "name": item.get("name"),
        "set_name": item.get("set_name"),
        "first_column_name": item.get("first_column_name"),
        "set_module_name": item.get("set_module_name"),
        "point": item.get("point"),
        "total_point": item.get("total_point"),
        "complete": item.get("complete"),
        "status": item.get("status"),
        "phase": phase_of(item, _now_ts()) if kind == "homework" else "set",
        "begin": item.get("begin"),
        "end": item.get("end"),
        "use_time": item.get("use_time"),
        "practise_count": item.get("practise_count"),
        "difficulty_rate": item.get("difficulty_rate"),
        "remark": item.get("remark"),
        "introduction": item.get("introduction"),
        "engine_area": item.get("engine_area"),
        "structure": structure,
        "template": template_summary,
    }


def summarize_template(tpl: dict) -> dict:
    res = tpl.get("res") or {}
    sections = []
    for exam_type in res.get("exam_type_list") or []:
        sections.append(
            {
                "name": exam_type.get("exam_type_name") or "",
                "collect": exam_type.get("exam_type_collect") or "",
                "score": exam_type.get("exam_type_score") or "",
                "count": exam_type.get("exam_type_count") or "",
                "intro": exam_type.get("exam_type_intro") or "",
            }
        )
    audio = []
    for rel in tpl.get("audio") or []:
        audio.append({"path": rel, "url": f"/api/template-audio/{tpl['template_id']}/{quote(rel)}"})
    return {
        "template_id": tpl.get("template_id"),
        "set_score": res.get("set_score"),
        "set_intro": res.get("set_intro"),
        "sections": sections,
        "audio": audio,
        "info": tpl.get("info") or [],
    }


def sets_payload(column_id: int, offset: int, limit: int, search: str) -> dict:
    data = STATE.sets_for_column(column_id)
    items = data["items"]
    if search:
        items = [item for item in items if search in (item.get("name") or "").lower() or search in (item.get("set_name") or "").lower()]
    total = len(items)
    page = items[offset : offset + limit]
    return {
        "column_id": column_id,
        "resource_id": data.get("resource_id"),
        "total": total,
        "offset": offset,
        "limit": limit,
        "counts": data.get("counts"),
        "items": page,
    }


def set_detail(column_id: int, set_id: str) -> dict:
    if not set_id:
        raise ec.EtsError("缺少 set_id", code=10001)
    data = STATE.sets_for_column(column_id)
    item = next((x for x in data["items"] if str(x.get("id")) == str(set_id)), None)
    if not item:
        raise ec.EtsError(f"未找到套卷：{set_id}", code=10001)
    detail = detail_from_item(item, kind="set")
    detail["phase"] = "set"
    return detail


def content_payload(stid: str, zip_name: str) -> dict:
    if not re.fullmatch(r"[0-9]{1,20}", stid or ""):
        raise ec.EtsError("stid 不合法", code=10001)
    if not zip_name:
        raise ec.EtsError("缺少资源包名 zip 参数", code=10001)
    data = STATE.client.ensure_content(stid, zip_name)
    material = []
    for entry in data.get("material") or []:
        rel = entry["path"]
        if entry["kind"] == "audio":
            url = f"/api/audio/{stid}/{quote(rel)}"
        elif entry["kind"] == "image":
            url = f"/api/asset/{stid}/{quote(rel)}"
        else:
            url = None
        material.append({**entry, "url": url})
    content = data.get("content") or {}
    return {
        "stid": stid,
        "structure_type": content.get("structure_type") or "unknown",
        "content": content,
        "content2": data.get("content2"),
        "info": data.get("info"),
        "material": material,
        "package": {
            "zip_name": (data.get("meta") or {}).get("zip_name"),
            "size": (data.get("meta") or {}).get("size"),
            "sha256": (data.get("meta") or {}).get("sha256"),
            "encrypted": (data.get("meta") or {}).get("encrypted"),
            "url": (data.get("meta") or {}).get("url"),
        },
    }


def template_payload(template_id: str, zip_name: str) -> dict:
    if not re.fullmatch(r"[0-9]{1,20}", template_id or ""):
        raise ec.EtsError("template_id 不合法", code=10001)
    if not zip_name:
        raise ec.EtsError("缺少资源包名 zip 参数", code=10001)
    data = STATE.client.ensure_template(template_id, zip_name)
    return summarize_template(data)


def config_payload() -> dict:
    cached = STATE.cache_get("system_config", 300)
    if cached is not None:
        return cached
    config = STATE.client.system_config() or {}
    result = {
        "count": len(config),
        "config": config,
        "serverTime": STATE.get_server_time(),
        "fetchedAt": int(time.time()),
    }
    STATE.cache_set("system_config", result)
    return result


def mistakes_payload() -> dict:
    data = STATE.mistakes()
    items = []
    for row in data.get("items") or []:
        items.append(
            {
                "id": str(row.get("id") or ""),
                "question_type": row.get("question_type") or "",
                "type": row.get("type"),
                "score_rate": row.get("score_rate"),
                "total_point": row.get("total_point"),
                "update_time": row.get("update_time") or "",
                "wrong_count": row.get("wrong_count"),
                "first_column_id": row.get("first_column_id"),
                "mistake_type": row.get("_mistake_type"),
                "structure": normalize_structs(row),
            }
        )
    return {
        "summary": data.get("summary") or {},
        "items": items,
        "total": len(items),
        "listError": data.get("list_error"),
    }


def mistake_detail(mistake_id: str) -> dict:
    data = STATE.mistakes()
    row = next((x for x in data.get("items") or [] if str(x.get("id")) == str(mistake_id)), None)
    if not row:
        # 刷新一次
        with STATE._lock:
            STATE._mistake_cache = None
        data = STATE.mistakes()
        row = next((x for x in data.get("items") or [] if str(x.get("id")) == str(mistake_id)), None)
    if not row:
        raise ec.EtsError(f"未找到错题：{mistake_id}", code=10001)
    structure = normalize_structs(row)
    content = None
    content_error = None
    if structure and structure[0]["contents"]:
        target = structure[0]["contents"][0]
        try:
            loaded = content_payload(target["stid"], target["zip_name"])
            content = loaded
        except ec.EtsError as exc:
            content_error = exc.to_dict()
    score_detail = []
    for detail in row.get("score_detail") or []:
        if not isinstance(detail, dict):
            continue
        audio = detail.get("audio") or ""
        detail_file = detail.get("detail_file") or ""
        score_detail.append(
            {
                "entity_id": detail.get("entity_id"),
                "order": detail.get("order"),
                "score_rate": detail.get("score_rate"),
                "standard_score": detail.get("standard_score"),
                "total_point": detail.get("total_point"),
                "detail": _parse_json_text(detail.get("detail")),
                "audioUrl": f"/api/remote-audio?url={quote(audio, safe='')}" if audio else None,
                "detailFileUrl": f"/api/remote-audio?url={quote(detail_file, safe='')}" if detail_file else None,
            }
        )
    return {
        "id": str(row.get("id") or ""),
        "question_type": row.get("question_type") or "",
        "score_rate": row.get("score_rate"),
        "total_point": row.get("total_point"),
        "update_time": row.get("update_time") or "",
        "structure": structure,
        "content": content,
        "contentError": content_error,
        "scoreDetail": score_detail,
        "baseUrl": data.get("base_url") or ec.CONTENT_BASE,
    }


def _parse_json_text(value):
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def ecards_payload() -> dict:
    ctx = STATE.context()
    cards = ctx.get("ecards") or []
    return {"items": mask_deep(cards), "count": len(cards)}


class RefHTTPServer(ThreadingHTTPServer):
    """本地参考服务器：忽略浏览器主动断连等无害网络错误。"""

    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError)):
            return
        log("请求处理异常: " + "".join(traceback.format_exception(exc)))
        super().handle_error(request, client_address)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="E听说参考客户端本地服务器")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=int(os.environ.get("ETS_REIMPL_PORT", DEFAULT_PORT)))
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args(argv)

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        log("警告：参考客户端只应在本机运行，已强制监听 127.0.0.1")
        args.host = "127.0.0.1"

    if not (STATIC_DIR / "index.html").is_file():
        log(f"错误：缺少静态文件 {STATIC_DIR / 'index.html'}")
        return 2

    server = RefHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    log(f"{APP_TITLE} {IMPL_VERSION} 启动：{url}")
    log(f"静态目录：{STATIC_DIR}")
    log(f"凭据：account={ec.ACCOUNT_FILE.is_file()} app_token={ec.APP_TOKEN_FILE.is_file()} state={ec.STATE_DIR}")
    if STATE.logged_in():
        log(f"已载入 token（来源 {STATE.client.token_source}）")
    else:
        log("未载入 token：请在页面登录，或准备 secrets/app_token.txt")
    log("未实现：录音 / ISE 评测 / 考试提交 / OSS 上传 / 更新器（页面已标注）")
    if args.open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("收到 Ctrl+C，正在关闭 …")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
