#!/usr/bin/env python3
"""E 听说 · ISE 口语评测客户端（参考实现）

基于真实抓包还原的协议（见 docs/15_practice_protocol.md）：
  wss://oe-pub.eduaiplat.com/ws/v2/ise，全 binary protobuf 消息
  init（含第一块音频 + 会话参数） → 若干音频帧（每块 212B speex） → 结束帧 → 结果帧（XML）

纯标准库实现（TLS/WebSocket/Protobuf 均内置），无第三方依赖。

用法（回放抓包里的 spx 验证协议）：
  python reimpl/ets_ise.py --capture-run <capture/runs/xxx> --spx <file.spx>
  python reimpl/ets_ise.py --capture-run <capture/runs/xxx> --spx <file.spx> --fetch-token
  python reimpl/ets_ise.py --capture-run <capture/runs/xxx> --pcm <pcm16k.raw> --chunk 640 --codec pcm

  --capture-run 目录需含 ws.jsonl（capture/cdp_capture.js 输出）与 files/（二进制帧）。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import ssl
import struct
import sys
import time
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

ISE_HOST = "oe-pub.eduaiplat.com"
ISE_PORT = 443
ISE_PATH = "/ws/v2/ise"
CHUNK_SIZE = 212


# ---------------------------------------------------------------------------
# protobuf (wire format only, no schema needed)
# ---------------------------------------------------------------------------
def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def tag(field: int, wire: int) -> bytes:
    return varint((field << 3) | wire)


def bytes_field(field: int, data: bytes) -> bytes:
    return tag(field, 2) + varint(len(data)) + data


def varint_field(field: int, value: int) -> bytes:
    return tag(field, 0) + varint(value)


def parse_fields(buf: bytes):
    out = []
    i = 0

    def rv():
        nonlocal i
        shift = val = 0
        while True:
            b = buf[i]
            i += 1
            val |= (b & 0x7F) << shift
            if not b & 0x80:
                return val
            shift += 7

    while i < len(buf):
        key = rv()
        f, wt = key >> 3, key & 7
        if wt == 0:
            out.append({"f": f, "wt": 0, "v": rv()})
        elif wt == 2:
            ln = rv()
            d = buf[i:i + ln]
            i += ln
            out.append({"f": f, "wt": 2, "d": d})
        elif wt == 5:
            out.append({"f": f, "wt": 5, "d": buf[i:i + 4]})
            i += 4
        elif wt == 1:
            out.append({"f": f, "wt": 1, "d": buf[i:i + 8]})
            i += 8
        else:
            raise ValueError(f"bad wire type {wt}")
    return out


def enc_fields(fields) -> bytes:
    parts = []
    for x in fields:
        if x["wt"] == 0:
            parts.append(varint_field(x["f"], x["v"]))
        elif x["wt"] == 2:
            parts.append(bytes_field(x["f"], x["d"]))
        elif x["wt"] == 5:
            parts.append(tag(x["f"], 5) + x["d"])
        elif x["wt"] == 1:
            parts.append(tag(x["f"], 1) + x["d"])
    return b"".join(parts)


# ---------------------------------------------------------------------------
# minimal WebSocket client (TLS + RFC6455)
# ---------------------------------------------------------------------------
class WsClient:
    def __init__(self, host=ISE_HOST, port=ISE_PORT, path=ISE_PATH, timeout=60):
        self.host = host
        self.port = port
        self.path = path
        self.timeout = timeout
        ctx = ssl.create_default_context()
        raw = socket.create_connection((host, port), timeout=timeout)
        self.sock = ctx.wrap_socket(raw, server_hostname=host)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Origin: https://statics.ets100.com\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36\r\n"
            "\r\n"
        )
        self.sock.sendall(req.encode())
        self._buf = b""
        head = self._read_until(b"\r\n\r\n")
        status = head.split(b"\r\n", 1)[0].decode("latin1")
        if "101" not in status:
            raise ConnectionError(f"WebSocket upgrade failed: {status}")
        self.closed = False

    # -- low level --
    def _read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(max(4096, n - len(self._buf)))
            if not chunk:
                raise ConnectionError("socket closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_until(self, marker: bytes) -> bytes:
        while marker not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("socket closed")
            self._buf += chunk
        idx = self._buf.index(marker) + len(marker)
        out, self._buf = self._buf[:idx], self._buf[idx:]
        return out

    @staticmethod
    def _frame(opcode: int, payload: bytes) -> bytes:
        mask = os.urandom(4)
        ln = len(payload)
        if ln < 126:
            header = bytes([0x80 | opcode, 0x80 | ln])
        elif ln < 65536:
            header = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack(">H", ln)
        else:
            header = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack(">Q", ln)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return header + mask + masked

    def send_binary(self, data: bytes):
        self.sock.sendall(self._frame(0x2, data))

    def recv_message(self) -> bytes:
        parts = []
        while True:
            b1, b2 = self._read_exact(2)
            fin = b1 & 0x80
            opcode = b1 & 0x0F
            masked = b2 & 0x80
            ln = b2 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read_exact(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(ln)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                self.closed = True
                raise ConnectionError("server closed")
            if opcode == 0x9:  # ping
                self.sock.sendall(self._frame(0xA, payload))
                continue
            if opcode == 0xA:
                continue
            parts.append(payload)
            if fin:
                return b"".join(parts)

    def close(self):
        try:
            self.sock.sendall(self._frame(0x8, b""))
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ISE protobuf messages
# ---------------------------------------------------------------------------
def build_init(session: dict, token: str, first_chunk: bytes, sample_rate=16000, codec="speex") -> bytes:
    """按抓包还原的字段构造 init。session 键见 docs/15。"""
    info = b"".join([
        bytes_field(1, session.get("client_id", "ksyyyxx-etszx").encode()),
        bytes_field(2, str(session.get("account_id", "")).encode()),
        bytes_field(3, session.get("mac", "00-00-00-00-00-00").encode()),
        bytes_field(4, session.get("app_id", "ets_70").encode()),
        bytes_field(5, session.get("sdk_key", "SDK_pY1wOPU8").encode()),
        bytes_field(6, str(session.get("request_id") or uuid.uuid4().hex).encode()),
        bytes_field(7, token.encode()),
        bytes_field(8, b""),
        b"".join(
            bytes_field(9, bytes_field(1, k.encode()) + bytes_field(2, str(v).encode()))
            for k, v in session.get("meta", {}).items()
        ),
    ])
    params = b"".join(
        bytes_field(11, bytes_field(1, k.encode()) + bytes_field(2, str(v).encode()))
        for k, v in session.get("params", {}).items()
    )
    return b"".join([
        bytes_field(1, info),
        bytes_field(2, session.get("lang", "en").encode()),
        bytes_field(3, b""),
        varint_field(4, 1),
        bytes_field(5, first_chunk),
        varint_field(6, sample_rate),
        bytes_field(7, codec.encode()),
        varint_field(8, 0),
        varint_field(9, 0),
        varint_field(10, 0),
        params,
        bytes_field(12, b""),
        varint_field(13, 3),
    ])


def build_audio_frame(chunk: bytes, codec="speex") -> bytes:
    return b"".join([
        bytes_field(5, chunk),
        bytes_field(7, codec.encode()),
        varint_field(8, 0),
    ])


def build_end_frame(codec="speex") -> bytes:
    return b"".join([
        bytes_field(5, b"\x00" * 10),
        bytes_field(7, codec.encode()),
        varint_field(8, 1),
    ])


def parse_result(data: bytes) -> dict:
    out = {"code": "", "msg": "", "traceId": "", "xml": ""}
    try:
        fields = parse_fields(data)
    except Exception:
        out["raw"] = data.hex()
        return out
    for x in fields:
        if x["wt"] != 2:
            continue
        if x["f"] == 1:
            out["code"] = x["d"].decode("utf-8", "replace")
        elif x["f"] == 2:
            out["msg"] = x["d"].decode("utf-8", "replace")
        elif x["f"] == 3:
            out["traceId"] = x["d"].decode("utf-8", "replace")
        elif x["f"] == 4:
            try:
                inner = parse_fields(x["d"])
                if len(inner) >= 2 and inner[0].get("wt") == 2 and inner[0]["d"] == b"result":
                    out["xml"] = inner[1]["d"].decode("utf-8", "replace")
            except Exception:
                pass
    if not out["xml"]:
        m = re.search(r"<xml_result[\s\S]*</xml_result>", data.decode("utf-8", "replace"))
        if m:
            out["xml"] = m.group(0)
    return out


def xml_summary(xml: str) -> dict:
    if not xml:
        return {}
    try:
        root = ET.fromstring(xml)
    except Exception:
        return {"xml_len": len(xml)}
    node = None
    for el in root.iter():
        if "accuracy_score" in el.attrib or el.tag.endswith("_chapter"):
            node = el
            break
    if node is None:
        return {"xml_len": len(xml)}
    attrs = dict(node.attrib)
    keep = ["accuracy_score", "fluency_score", "integrity_score", "standard_score",
            "total_score", "is_rejected", "reject_type", "except_info", "content", "word_count"]
    return {k: attrs.get(k) for k in keep if k in attrs}


# ---------------------------------------------------------------------------
# 抓包模板
# ---------------------------------------------------------------------------
def load_capture_template(run_dir: Path):
    ws_path = run_dir / "ws.jsonl"
    if not ws_path.is_file():
        raise FileNotFoundError(f"{ws_path} 不存在")
    events = []
    for line in ws_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    created = {e["id"]: e.get("url", "") for e in events if e.get("kind") == "created"}
    by_id = {}
    for e in events:
        if e.get("kind") in ("send", "recv"):
            by_id.setdefault(e["id"], []).append(e)
    ise_ids = [sid for sid in by_id if "ise" in str(created.get(sid, ""))]
    if not ise_ids:
        raise ValueError("抓包里没有 ISE WebSocket 会话")
    frames = by_id[ise_ids[0]]
    if not frames:
        raise ValueError("ISE 会话没有帧")
    init = (run_dir / frames[0]["file"]).read_bytes()
    return init, frames


def template_fields(init: bytes):
    top = parse_fields(init)
    sess = next(x for x in top if x["f"] == 1 and x["wt"] == 2)
    return top, parse_fields(sess["d"])


def replace_field(fields, f, data=None, value=None, wt=2):
    for x in fields:
        if x["f"] == f:
            if value is not None:
                x["wt"] = 0
                x["v"] = value
            else:
                x["wt"] = 2
                x["d"] = data
            return True
    return False


# ---------------------------------------------------------------------------
# 评测
# ---------------------------------------------------------------------------
def evaluate(chunks, token=None, session=None, capture_run=None, codec="speex",
             sample_rate=16000, timeout=120, verbose=True) -> dict:
    """chunks: list[bytes]，每块默认 212B speex（或其它 codec 块）。"""
    if not chunks:
        raise ValueError("没有音频块")
    if capture_run:
        init, _ = load_capture_template(Path(capture_run))
        top, sess = template_fields(init)
        if token:
            replace_field(sess, 7, token.encode())
        replace_field(sess, 6, uuid.uuid4().hex.encode())
        # 用实际音频替换 init 的第一块
        replace_field(top, 5, chunks[0])
        replace_field(top, 7, codec.encode())
        replace_field(top, 6, value=sample_rate)
        init_bytes = enc_fields([{**x, "d": enc_fields(sess)} if x["f"] == 1 and x["wt"] == 2 else x for x in top])
    else:
        session = session or {}
        session.setdefault("request_id", uuid.uuid4().hex)
        init_bytes = build_init(session, token or "", chunks[0], sample_rate=sample_rate, codec=codec)

    ws = WsClient(timeout=timeout)
    if verbose:
        print(f"[ise] connected {ISE_HOST}{ISE_PATH}, chunks={len(chunks)}, codec={codec}")
    t0 = time.time()
    ws.send_binary(init_bytes)
    for i, ch in enumerate(chunks[1:], 1):
        ws.send_binary(build_audio_frame(ch, codec))
        if verbose and i % 50 == 0:
            print(f"[ise] sent {i}/{len(chunks)-1} chunks")
        time.sleep(0.005)
    ws.send_binary(build_end_frame(codec))
    if verbose:
        print("[ise] end frame sent, waiting result...")
    data = ws.recv_message()
    ws.close()
    result = parse_result(data)
    result["elapsed_ms"] = int((time.time() - t0) * 1000)
    result["scores"] = xml_summary(result.get("xml", ""))
    if verbose:
        print(f"[ise] result {len(data)}B in {result['elapsed_ms']}ms code={result['code']} msg={result['msg']} trace={result['traceId']}")
        print("[ise] scores:", json.dumps(result["scores"], ensure_ascii=False))
    return result


def fetch_token_from_client() -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ets_client import EtsClient  # noqa

    client = EtsClient()
    if not client.load_saved_token():
        client.load_token_from_secrets()
    if not client.token:
        raise SystemExit("没有可用登录 token：请先运行 reimpl/server.py 登录，或放置 secrets/app_token.txt")
    body = client.call("ai/aiplat/getaitoken", {})
    token = (body or {}).get("accessToken") if isinstance(body, dict) else None
    if not token:
        raise SystemExit(f"getaitoken 返回异常：{body}")
    return token


def main():
    ap = argparse.ArgumentParser(description="ISE 口语评测客户端（参考实现）")
    ap.add_argument("--capture-run", help="抓包目录（含 ws.jsonl 与 files/），用其中的 init 模板")
    ap.add_argument("--spx", help="spx 文件（212B 一块）")
    ap.add_argument("--pcm", help="PCM s16le 16k 单声道文件（按 --chunk 切块）")
    ap.add_argument("--chunk", type=int, default=CHUNK_SIZE, help="块大小（spx 默认 212；pcm 建议 640）")
    ap.add_argument("--codec", default="speex", help="init 中的 codec 字符串（默认 speex）")
    ap.add_argument("--token", help="ISE accessToken；缺省用抓包模板里的 token")
    ap.add_argument("--fetch-token", action="store_true", help="通过 ai/aiplat/getaitoken 获取新 token")
    ap.add_argument("--json-out", help="把结果（含 XML）写到 JSON 文件")
    ap.add_argument("--xml-out", help="把结果 XML 写到文件")
    args = ap.parse_args()

    if not args.capture_run:
        raise SystemExit("必须提供 --capture-run（init 模板来源）")
    chunks = []
    if args.spx:
        data = Path(args.spx).read_bytes()
        chunks = [data[i:i + args.chunk] for i in range(0, len(data), args.chunk)]
    elif args.pcm:
        data = Path(args.pcm).read_bytes()
        chunks = [data[i:i + args.chunk] for i in range(0, len(data), args.chunk)]
    else:
        raise SystemExit("提供 --spx 或 --pcm")

    token = args.token
    if args.fetch_token:
        token = fetch_token_from_client()

    result = evaluate(chunks, token=token, capture_run=args.capture_run, codec=args.codec,
                      sample_rate=16000 if args.codec == "speex" else 16000)
    if args.xml_out:
        Path(args.xml_out).write_text(result.get("xml", ""), encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if str(result.get("code", "")).startswith("00000") else 1


if __name__ == "__main__":
    sys.exit(main())
