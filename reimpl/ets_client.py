"""E听说（学生端 PC）参考客户端 · API 客户端库。

纯逻辑库，不依赖 Web 框架：
  * 请求签名  sign = MD5("pcWin" + time_ms + base64(body_json) + KEY_V2)
  * 请求信封  {body: base64([{r, params}]), head: {version, sign, pid, time, time_second}}
  * 字段加密  AES-128-ECB / PKCS7 / key = k_serves
  * 登录 / token 持久化 / 只读接口封装
  * 题库资源包下载（cdnsubject / cdnfeis）与 ZipCrypto 解密
  * 音频缓存（包内音频 + 评测结果音频）

依赖：优先使用 requests + cryptography；两者不可用时自动退回
urllib + 内置纯 Python AES-128-ECB 实现（结果完全一致）。

凭据只从仓库外的 <WORK_DIR>/secrets/ 读取（可用环境变量覆盖），本文件不含任何凭据。
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import threading
import time
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量（来自 docs/08_signature.md、docs/03_api_protocol.md，均为协议常量而非凭据）
# ---------------------------------------------------------------------------

API_BASE = os.environ.get("ETS_API_BASE", "https://api.ets100.com").rstrip("/")
PID = "pcWin"
KEY_V2 = "94cfbda3fbfef02b93693f8bc153be82"
K_SERVES = "f05323cb91d422b2"
GLOBAL_CLIENT_VERSION = "5.7.9"
SN = "test"
SYSTEM = 4
HEAD_VERSION = "1.0"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)

COMMON_PARAMS = {
    "sign_response": 1,
    "sn": SN,
    "system": SYSTEM,
    "global_client_version": GLOBAL_CLIENT_VERSION,
}

REIMPL_DIR = Path(__file__).resolve().parent
ROOT_DIR = REIMPL_DIR.parent
STATE_DIR = Path(os.environ.get("ETS_REIMPL_STATE_DIR", str(REIMPL_DIR / ".state")))
ACCOUNT_FILE = Path(os.environ.get("ETS_ACCOUNT_FILE", str(ROOT_DIR / "secrets" / "account.json")))
APP_TOKEN_FILE = Path(os.environ.get("ETS_APP_TOKEN_FILE", str(ROOT_DIR / "secrets" / "app_token.txt")))
LEGACY_TOKEN_FILE = Path(os.environ.get("ETS_LEGACY_TOKEN_FILE", str(ROOT_DIR / "secrets" / "token.json")))
SAVED_TOKEN_FILE = STATE_DIR / "token.json"

CONTENT_BASE = "https://cdnsubject.ets100.com/made/"
MEDIA_HOSTS = {"ets60.ets100.com"}
MAX_DOWNLOAD_BYTES = 96 * 1024 * 1024
HTTP_TIMEOUT = 30

# 只读接口封装清单（与 work/reimpl_probe 的 23 个真实响应一一对应）
READONLY_ENDPOINTS = [
    "system/config",
    "system/time",
    "user/info",
    "user/get-record",
    "announcement/list",
    "m/ecard/list",
    "m/advertisement/list",
    "m/mistake/summary",
    "m/mistake/list",
    "g/homework/list",
    "g/resource/grade-list",
    "g/resource/book-list",
    "g/resource/expand-module",
    "g/resource/priority-instruction-book",
    "g/set/unit-list",
    "g/set/unit-info",
    "g/set/module-list",
    "g/set/list",
    "g/set/column-v2",
    "file/download",
    "g/data/sls-config",
    "p1/student/ability/sls/slsAppConfig",
    "config/config/getResourcePlatformToken",
    "ai/aiplat/getaitoken",
    "p1/student/config/config/ossEvaluateUploadStsToken",
]


# ---------------------------------------------------------------------------
# 错误
# ---------------------------------------------------------------------------

CODE_HINTS = {
    20004: (
        "当前账号已在其它会话（多半是官方客户端）登录，触发单会话互踢。"
        "请先完全退出官方客户端后再登录；或改用 secrets/app_token.txt 中官方客户端现有的 token。"
    ),
    30001: "登录态无效或账号密码不正确。请重新登录，或粘贴一个当前有效的 token。",
    80004: "没有找到有效班级：该账号未绑定有效 E 卡 / 班级。",
    10001: "接口参数不完整或被服务端拒绝。",
}


class EtsError(Exception):
    """参考客户端统一异常。"""

    def __init__(self, message, code=None, route=None, http_status=None, hint=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.route = route
        self.http_status = http_status
        self.hint = hint or CODE_HINTS.get(code)

    def to_dict(self):
        return {
            "message": self.message,
            "code": self.code,
            "route": self.route,
            "http_status": self.http_status,
            "hint": self.hint,
        }


# ---------------------------------------------------------------------------
# AES-128-ECB（优先 cryptography，缺失时使用内置纯 Python 实现）
# ---------------------------------------------------------------------------

_SBOX_HEX = (
    "637c777bf26b6fc53001672bfed7ab76"
    "ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d83115"
    "04c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f84"
    "53d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa8"
    "51a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d1973"
    "60814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479"
    "e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a"
    "703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df"
    "8ca1890dbfe6426841992d0fb054bb16"
)
_SBOX = bytes.fromhex(_SBOX_HEX)
_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _xtime(a: int) -> int:
    a <<= 1
    if a & 0x100:
        a ^= 0x11B
    return a & 0xFF


def _aes_expand_key(key: bytes) -> list[list[int]]:
    if len(key) != 16:
        raise ValueError("AES-128 需要 16 字节密钥")
    words = [list(key[i : i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        temp = list(words[i - 1])
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // 4 - 1]
        words.append([words[i - 4][j] ^ temp[j] for j in range(4)])
    return [byte for word in words for byte in word]


def _aes_encrypt_block(block: bytes, round_keys: list[list[int]]) -> bytes:
    state = list(block)

    def add_round_key(rnd: int) -> None:
        k = rnd * 16
        for i in range(16):
            state[i] ^= round_keys[k + i]

    add_round_key(0)
    for rnd in range(1, 11):
        state = [_SBOX[b] for b in state]
        # ShiftRows（state 为列优先：state[4*c+r]）
        shifted = [0] * 16
        for c in range(4):
            for r in range(4):
                shifted[4 * c + r] = state[4 * ((c + r) % 4) + r]
        state = shifted
        if rnd != 10:
            out = [0] * 16
            for c in range(4):
                a0, a1, a2, a3 = state[4 * c : 4 * c + 4]
                t = a0 ^ a1 ^ a2 ^ a3
                out[4 * c + 0] = a0 ^ t ^ _xtime(a0 ^ a1)
                out[4 * c + 1] = a1 ^ t ^ _xtime(a1 ^ a2)
                out[4 * c + 2] = a2 ^ t ^ _xtime(a2 ^ a3)
                out[4 * c + 3] = a3 ^ t ^ _xtime(a3 ^ a0)
            state = out
        add_round_key(rnd)
    return bytes(state)


def _aes128_ecb_encrypt(data: bytes, key: bytes) -> bytes:
    if len(data) % 16:
        raise ValueError("AES-ECB 数据长度必须是 16 的倍数")
    round_keys = _aes_expand_key(key)
    out = bytearray()
    for i in range(0, len(data), 16):
        out += _aes_encrypt_block(data[i : i + 16], round_keys)
    return bytes(out)


try:  # pragma: no cover - 取决于运行环境
    from cryptography.hazmat.primitives import padding as _crypt_padding
    from cryptography.hazmat.primitives.ciphers import Cipher as _CryptCipher
    from cryptography.hazmat.primitives.ciphers import algorithms as _CryptAlgorithms
    from cryptography.hazmat.primitives.ciphers import modes as _CryptModes

    _HAS_CRYPTOGRAPHY = True
except Exception:  # pragma: no cover
    _HAS_CRYPTOGRAPHY = False


def aes_ecb_encrypt_b64(plain: str, key: str = K_SERVES) -> str:
    """AES-128-ECB + PKCS7，返回 Base64；用于 phone / password 字段。"""
    raw = plain.encode("utf-8")
    pad = 16 - (len(raw) % 16)
    padded = raw + bytes([pad]) * pad
    key_bytes = key.encode("utf-8")
    if _HAS_CRYPTOGRAPHY:
        encryptor = _CryptCipher(_CryptAlgorithms.AES(key_bytes), _CryptModes.ECB()).encryptor()
        cipher = encryptor.update(padded) + encryptor.finalize()
    else:
        cipher = _aes128_ecb_encrypt(padded, key_bytes)
    return base64.b64encode(cipher).decode("ascii")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


class _HttpClient:
    """线程安全的轻量 HTTP 封装（requests 优先，urllib 兜底）。"""

    def __init__(self):
        self._local = threading.local()

    def _session(self):
        session = getattr(self._local, "session", None)
        if session is None:
            try:
                import requests  # noqa: F401

                session = requests.Session()
                session.headers.update(
                    {
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json, text/plain, */*",
                        "Content-Type": "application/json",
                        "Origin": "https://statics.ets100.com",
                        "Referer": "https://statics.ets100.com/",
                    }
                )
            except Exception:
                session = False
            self._local.session = session
        return session

    def post_json(self, url: str, payload: dict, timeout: int = HTTP_TIMEOUT):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        session = self._session()
        if session:
            resp = session.post(url, data=body, timeout=timeout)
            return resp.status_code, resp.content
        from urllib.request import Request, urlopen

        req = Request(
            url,
            data=body,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": "https://statics.ets100.com",
                "Referer": "https://statics.ets100.com/",
            },
        )
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 固定官方域名
            return resp.status, resp.read()

    def get_bytes(self, url: str, timeout: int = HTTP_TIMEOUT) -> bytes:
        session = self._session()
        if session:
            resp = session.get(url, timeout=timeout, headers={"Accept": "*/*"})
            if resp.status_code >= 400:
                raise EtsError(f"下载失败：HTTP {resp.status_code}", http_status=resp.status_code)
            data = resp.content
        else:
            from urllib.request import Request, urlopen

            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urlopen(req, timeout=timeout) as resp:  # noqa: S310
                data = resp.read()
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise EtsError("下载内容超过大小上限")
        return data


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sign_body(body_json: str, time_ms: str) -> str:
    """v2 请求签名：MD5(pid + time + base64(body) + KEY_V2)。"""
    b64 = base64.b64encode(body_json.encode("utf-8")).decode("ascii")
    return hashlib.md5((PID + time_ms + b64 + KEY_V2).encode("utf-8")).hexdigest()


def _mask_text(value: str, keep: int = 3) -> str:
    if not isinstance(value, str) or not value:
        return value
    if len(value) <= keep * 2:
        return value[0] + "*" * (len(value) - 1) if len(value) > 1 else "*"
    return value[:keep] + "*" * (len(value) - keep * 2) + value[-keep:]


def zipcrypto_password(package: bytes) -> str | None:
    """从包尾 336 字节口令块派生 ZipCrypto 口令（docs/06_data.md §4.2）。

    company=MSTCHINA、productid=EPLAT 时：
        pwd = MD5(pwd_text).upper() + MD5(MD5(pwd_text).upper()).upper()
    """

    def clean(b: bytes) -> str:
        return b.decode("utf-8", "replace").replace("\x00", "").strip()

    if len(package) >= 336:
        tail = package[-336:]
        company = clean(tail[0:8])
        product = clean(tail[144:176])
        if company == "MSTCHINA" and product == "EPLAT":
            first = md5_hex(clean(tail[16:144])).upper()
            return first + md5_hex(first).upper()
    # 旧/别种包的 40 字节尾：decode 后 substring(8) 再做两级 MD5
    if len(package) >= 40:
        text = clean(package[-40:])
        if len(text) > 8:
            first = md5_hex(text[8:]).upper()
            return first + md5_hex(first).upper()
    return None


def validate_zip_name(name: str) -> str:
    """只接受 cdnsubject/made 目录下的纯 zip 文件名。"""
    if not isinstance(name, str):
        raise EtsError("资源包文件名无效")
    name = name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}\.zip", name):
        raise EtsError("资源包文件名不合法（仅允许 <hash>.zip）")
    if name.startswith("."):
        raise EtsError("资源包文件名不合法")
    return name


def content_zip_url(zip_name: str) -> str:
    return CONTENT_BASE + validate_zip_name(zip_name)


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> list[str]:
    """安全解压：拒绝绝对路径 / .. 穿越 / 符号链接。"""
    dest = dest.resolve()
    files: list[str] = []
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        parts = [p for p in name.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise EtsError(f"压缩包包含非法路径：{name}")
        target = (dest / Path(*parts)).resolve()
        if not str(target).startswith(str(dest) + os.sep):
            raise EtsError(f"压缩包路径越界：{name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src:
            target.write_bytes(src.read())  # 读取时校验 CRC
        files.append("/".join(parts))
    return files


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# EtsClient
# ---------------------------------------------------------------------------


class EtsClient:
    """E听说 API 客户端。实例可被多线程共享（内部有锁）。"""

    def __init__(self, state_dir: Path | None = None):
        self.http = _HttpClient()
        self._lock = threading.RLock()
        self._download_locks: dict[str, threading.Lock] = {}
        self._download_locks_lock = threading.Lock()
        self.state_dir = Path(state_dir) if state_dir else STATE_DIR
        self.cache_dir = self.state_dir / "cache"
        self.content_cache = self.cache_dir / "content"
        self.template_cache = self.cache_dir / "template"
        self.media_cache = self.cache_dir / "media"
        for d in (self.state_dir, self.cache_dir, self.content_cache, self.template_cache, self.media_cache):
            d.mkdir(parents=True, exist_ok=True)
        self.token: str | None = None
        self.token_source: str | None = None
        self.token_expire: int | None = None

    # ----- token ---------------------------------------------------------

    def _read_token_file(self, path: Path) -> str | None:
        try:
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                return None
            if text.startswith("{"):
                data = json.loads(text)
                return (data.get("token") or "").strip() or None
            return text.splitlines()[0].strip() or None
        except Exception:
            return None

    def load_saved_token(self) -> bool:
        """优先使用本参考客户端保存的 token。"""
        try:
            if not SAVED_TOKEN_FILE.is_file():
                return False
            data = json.loads(SAVED_TOKEN_FILE.read_text(encoding="utf-8"))
            token = (data.get("token") or "").strip()
            if not token:
                return False
            with self._lock:
                self.token = token
                self.token_source = data.get("source") or "saved"
                self.token_expire = data.get("expire")
            return True
        except Exception:
            return False

    def load_token_from_secrets(self) -> bool:
        """其次使用官方客户端当前 token（secrets/app_token.txt）。"""
        token = self._read_token_file(APP_TOKEN_FILE)
        source = "app_token.txt"
        if not token:
            token = self._read_token_file(LEGACY_TOKEN_FILE)
            source = "token.json"
        if not token:
            return False
        with self._lock:
            self.token = token
            self.token_source = source
        return True

    def resolve_token(self) -> bool:
        if self.load_saved_token():
            return True
        return self.load_token_from_secrets()

    def save_token(self, token: str, source: str, expire: int | None = None) -> None:
        with self._lock:
            self.token = token
            self.token_source = source
            self.token_expire = expire
        payload = {
            "token": token,
            "source": source,
            "expire": expire,
            "saved_at": int(time.time()),
        }
        _atomic_write(SAVED_TOKEN_FILE, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        try:
            os.chmod(SAVED_TOKEN_FILE, 0o600)
        except Exception:
            pass

    def clear_saved_token(self) -> None:
        with self._lock:
            self.token = None
            self.token_source = None
            self.token_expire = None
        try:
            SAVED_TOKEN_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def mask_token(self) -> str | None:
        with self._lock:
            token = self.token
        if not token:
            return None
        return token[:10] + "…" + token[-6:]

    # ----- 协议 ----------------------------------------------------------

    def _call_once(self, route: str, params: dict, timeout: int = HTTP_TIMEOUT):
        body_arr = [{"r": route, "params": params}]
        body_json = json.dumps(body_arr, ensure_ascii=False, separators=(",", ":"))
        b64 = base64.b64encode(body_json.encode("utf-8")).decode("ascii")
        time_ms = str(int(time.time() * 1000))
        payload = {
            "body": b64,
            "head": {
                "version": HEAD_VERSION,
                "sign": sign_body(body_json, time_ms),
                "pid": PID,
                "time": time_ms,
                "time_second": int(time_ms),
            },
        }
        url = f"{API_BASE}/{route.lstrip('/')}"
        try:
            status, raw = self.http.post_json(url, payload, timeout=timeout)
        except EtsError:
            raise
        except Exception as exc:  # 网络层
            raise EtsError(f"网络请求失败：{exc}", route=route) from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise EtsError("服务端返回的不是合法 JSON", route=route, http_status=status) from exc
        if isinstance(data, list):
            item = data[0] if data else {}
        elif isinstance(data, dict):
            item = data
        else:
            raise EtsError("服务端返回结构异常", route=route, http_status=status)
        code = item.get("code")
        msg = item.get("msg") or ""
        if code != 0:
            raise EtsError(msg or f"接口返回 code={code}", code=code, route=route, http_status=status)
        return item.get("body")

    def call(self, route: str, params: dict | None = None, *, use_token: bool = True, timeout: int = HTTP_TIMEOUT):
        """通用 RPC 调用，返回响应 body；code != 0 时抛 EtsError。"""
        payload: dict = dict(COMMON_PARAMS)
        with self._lock:
            token = self.token
        if use_token and token:
            payload["token"] = token
        if params:
            payload.update(params)
        return self._call_once(route, payload, timeout=timeout)

    # ----- 登录 ----------------------------------------------------------

    @staticmethod
    def read_account_file() -> dict:
        if not ACCOUNT_FILE.is_file():
            raise EtsError(
                f"未找到账号文件：{ACCOUNT_FILE}。"
                "请按 README 准备 secrets/account.json（phone/password/device_name/device_code/local_ip）。"
            )
        try:
            data = json.loads(ACCOUNT_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            raise EtsError(f"账号文件不是合法 JSON：{exc}") from exc
        for key in ("phone", "password"):
            if not data.get(key):
                raise EtsError(f"账号文件缺少字段：{key}")
        return data

    def login(self, phone: str, password: str, device_name: str = "PC",
              device_code: str = "0000000000000000", local_ip: str = "127.0.0.1") -> dict:
        params = dict(COMMON_PARAMS)
        params.update(
            {
                "phone": aes_ecb_encrypt_b64(phone),
                "password": aes_ecb_encrypt_b64(password),
                "device_name": device_name,
                "device_code": device_code,
                "local_ip": local_ip,
                "version": 4,
            }
        )
        body = self._call_once("user/login", params)
        token = (body or {}).get("token")
        if not token:
            raise EtsError("登录响应中没有 token", route="user/login")
        self.save_token(token, source="account", expire=(body or {}).get("expire"))
        return body or {}

    def login_with_account_file(self) -> dict:
        account = self.read_account_file()
        return self.login(
            account["phone"],
            account["password"],
            device_name=account.get("device_name") or "PC",
            device_code=account.get("device_code") or "0000000000000000",
            local_ip=account.get("local_ip") or "127.0.0.1",
        )

    def use_existing_token(self, token: str | None = None, source: str = "manual") -> dict:
        if token is None:
            token = self._read_token_file(APP_TOKEN_FILE)
            source = "app_token.txt"
            if not token:
                token = self._read_token_file(LEGACY_TOKEN_FILE)
                source = "token.json"
        if not token:
            raise EtsError(f"未找到可用的 token 文件：{APP_TOKEN_FILE}")
        with self._lock:
            previous = (self.token, self.token_source, self.token_expire)
            self.token = token.strip()
            self.token_source = source
        try:
            user = self.call("user/info")
        except EtsError:
            # 校验失败时恢复原有登录态，避免“粘错 token”把当前会话登出
            with self._lock:
                self.token, self.token_source, self.token_expire = previous
            raise
        self.save_token(token.strip(), source=source, expire=None)
        return user or {}

    # ----- 只读接口封装 --------------------------------------------------

    def system_config(self, keywork: list[str] | None = None):
        params = {"checkToken": False}
        if keywork:
            params["keywork"] = keywork
        return self.call("system/config", params)

    def system_time(self):
        return self.call("system/time")

    def announcement_list(self):
        return self.call("announcement/list", {"checkToken": False})

    def user_info(self):
        return self.call("user/info")

    def user_get_record(self, resource_id="239", types=None):
        return self.call(
            "user/get-record",
            {
                "resource_id": str(resource_id),
                "type": types or ["Listen_Class_Complete_Rate"],
                "record_system": SYSTEM,
            },
        )

    def ecard_list(self):
        return self.call("m/ecard/list", {"school_level_filter": 0, "version": "2", "json_type": "1"})

    def advertisement_list(self, resource_id="239"):
        return self.call("m/advertisement/list", {"type": 1, "resource_id": str(resource_id)})

    def mistake_summary(self, parent_account_id: str):
        return self.call("m/mistake/summary", {"parent_account_id": str(parent_account_id)})

    def mistake_list(self, parent_account_id: str, type_: int = 1, status: int = 0,
                     offset: int = 0, limit: int = 20):
        return self.call(
            "m/mistake/list",
            {
                "parent_account_id": str(parent_account_id),
                "status": status,
                "random": "0",
                "max_id": "0",
                "max_update_time": "",
                "type": type_,
                "limit": limit,
                "offset": offset,
            },
        )

    def homework_list(self, parent_account_id: str, status: int = 1, offset: int = 0,
                      limit: int = 10, use_https: int = 1):
        return self.call(
            "g/homework/list",
            {
                "version": 11,
                "parent_account_id": str(parent_account_id),
                "offset": offset,
                "status": status,
                "get_all_count": 1,
                "limit": limit,
                "get_to_do_count": 1,
                "get_to_overtime_count": 1,
                "check_pass": 1,
                "show_old_homework": 1,
                "get_audio_task": 1,
                "use_https": use_https,
                "use_homework_privilege": 1,
            },
        )

    def homeworks(self, parent_account_id: str, statuses=(0, 2, 3), limit: int = 20) -> list[dict]:
        """合并多个状态的作业列表，按 id 去重。"""
        seen: set[str] = set()
        items: list[dict] = []
        last_error: EtsError | None = None
        for status in statuses:
            try:
                body = self.homework_list(parent_account_id, status=status, limit=limit)
            except EtsError as exc:
                last_error = exc
                continue
            for item in (body or {}).get("data") or []:
                key = str(item.get("id") or "")
                if key and key not in seen:
                    seen.add(key)
                    items.append(item)
        if not items and last_error:
            raise last_error
        return items

    def grade_list(self, parent_resource_id="274"):
        return self.call("g/resource/grade-list", {"parent_resource_id": str(parent_resource_id)})

    def book_list(self, parent_resource_id="274"):
        return self.call("g/resource/book-list", {"parent_resource_id": str(parent_resource_id)})

    def expand_module(self, parent_resource_id="274", parent_account_id=None):
        params = {"parent_resource_id": str(parent_resource_id), "version": "1.0"}
        if parent_account_id:
            params["parent_account_id"] = str(parent_account_id)
        return self.call("g/resource/expand-module", params)

    def priority_instruction_book(self, parent_resource_id="274", parent_account_id=None):
        params = {"parent_resource_id": str(parent_resource_id), "version": "3"}
        if parent_account_id:
            params["parent_account_id"] = str(parent_account_id)
        return self.call("g/resource/priority-instruction-book", params)

    def unit_list(self, resource_id, book_id, is_need_score=0):
        return self.call(
            "g/set/unit-list",
            {"resource_id": int(resource_id), "book_id": int(book_id), "is_need_score": is_need_score},
        )

    def unit_info(self, resource_id, book_id, unit_id, is_need_score=1):
        return self.call(
            "g/set/unit-info",
            {
                "resource_id": int(resource_id),
                "book_id": int(book_id),
                "unit_id": int(unit_id),
                "is_need_score": is_need_score,
            },
        )

    def module_list(self, resource_id, book_id, unit_id):
        return self.call(
            "g/set/module-list",
            {
                "resource_id": int(resource_id),
                "book_id": int(book_id),
                "unit_id": int(unit_id),
                "version": 2,
                "support_credential_resource": 1,
            },
        )

    def set_list(self, resource_id, first_column_id=None, show_empty=0, use_https=1):
        params = {
            "resource_id": str(resource_id),
            "show_empty": show_empty,
            "use_https": use_https,
        }
        if first_column_id is not None:
            params["first_column_id"] = list(first_column_id)
        return self.call("g/set/list", params)

    def column_v2(self, resource_id, tag_id=1, hide_set_count=1):
        return self.call(
            "g/set/column-v2",
            {"resource_id": int(resource_id), "tag_id": int(tag_id), "hide_set_count": hide_set_count},
        )

    def file_download(self, key="pc_set_common_stic"):
        return self.call("file/download", {"key": key, "use_https": 1})

    def sls_config(self):
        return self.call("g/data/sls-config")

    def sls_app_config(self):
        return self.call("p1/student/ability/sls/slsAppConfig")

    def resource_platform_token(self):
        return self.call("config/config/getResourcePlatformToken")

    def ai_token(self):
        return self.call("ai/aiplat/getaitoken")

    def oss_evaluate_sts_token(self):
        return self.call("p1/student/config/config/ossEvaluateUploadStsToken")

    def account_bind_info(self, account=None):
        params = {}
        if account:
            params["account"] = account
        return self.call("account/get-bind-info", params)

    # ----- 资源包 / 音频缓存 --------------------------------------------

    def _download_lock(self, key: str) -> threading.Lock:
        with self._download_locks_lock:
            lock = self._download_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._download_locks[key] = lock
            return lock

    def _ensure_package(self, kind: str, cache_key: str, zip_name: str) -> Path:
        """下载 + 解密 + 解压一个 zip 包，返回解压目录。"""
        zip_name = validate_zip_name(zip_name)
        base = self.content_cache if kind == "content" else self.template_cache
        dest = base / cache_key
        marker = dest / ".package.json"
        if marker.is_file():
            try:
                json.loads(marker.read_text(encoding="utf-8"))
                return dest
            except Exception:
                pass
        lock = self._download_lock(f"{kind}:{cache_key}")
        with lock:
            if marker.is_file():
                return dest
            url = content_zip_url(zip_name)
            package = self.http.get_bytes(url)
            password = zipcrypto_password(package)
            try:
                zf = zipfile.ZipFile(io.BytesIO(package))
            except zipfile.BadZipFile as exc:
                raise EtsError(f"资源包不是合法 zip：{zip_name}") from exc
            encrypted = any(info.flag_bits & 0x1 for info in zf.infolist())
            if encrypted:
                if not password:
                    raise EtsError("资源包已加密，但未能从包尾派生 ZipCrypto 口令")
                zf.setpassword(password.encode("ascii"))
            if dest.exists():
                # 残留目录优先清理，避免半包
                for child in dest.iterdir():
                    if child.is_dir():
                        import shutil

                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
            dest.mkdir(parents=True, exist_ok=True)
            try:
                files = _safe_extract(zf, dest)
            except (RuntimeError, zipfile.BadZipFile) as exc:
                raise EtsError(f"资源包解密/解压失败：{exc}") from exc
            meta = {
                "kind": kind,
                "cache_key": cache_key,
                "zip_name": zip_name,
                "url": url,
                "sha256": hashlib.sha256(package).hexdigest(),
                "size": len(package),
                "encrypted": encrypted,
                "files": files,
                "downloaded_at": int(time.time()),
            }
            _atomic_write(marker, json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
            return dest

    def ensure_content(self, stid, zip_name: str) -> dict:
        """下载/复用 content_<stid>.zip，返回 {dir, content, content2, info, material, meta}。"""
        stid = str(stid)
        if not re.fullmatch(r"[0-9]{1,20}", stid):
            raise EtsError("题目 id 不合法")
        dest = self._ensure_package("content", stid, zip_name)
        return self._read_content_dir(dest, stid)

    @staticmethod
    def _read_json(path: Path, default=None):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _read_content_dir(self, dest: Path, stid: str) -> dict:
        content = self._read_json(dest / "content.json")
        content2 = self._read_json(dest / "content2.json")
        info = self._read_json(dest / "info.json", [])
        meta = self._read_json(dest / ".package.json", {})
        if content is None:
            raise EtsError("资源包中缺少 content.json")
        material = []
        for path in sorted(dest.rglob("*")):
            if not path.is_file() or path.name.startswith(".package"):
                continue
            rel = path.relative_to(dest).as_posix()
            lower = rel.lower()
            if lower.endswith((".mp3", ".wav", ".m4a")):
                kind = "audio"
            elif lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                kind = "image"
            elif lower.endswith((".json", ".xml")):
                continue
            else:
                kind = "file"
            material.append({"path": rel, "kind": kind, "size": path.stat().st_size})
        return {
            "stid": stid,
            "content": content,
            "content2": content2 or content,
            "info": info,
            "material": material,
            "meta": meta,
        }

    def ensure_template(self, template_id, zip_name: str) -> dict:
        template_id = str(template_id)
        if not re.fullmatch(r"[0-9]{1,20}", template_id):
            raise EtsError("模板 id 不合法")
        dest = self._ensure_package("template", template_id, zip_name)
        meta = self._read_json(dest / ".package.json", {})
        audio = []
        for path in sorted(dest.rglob("*")):
            if path.is_file() and path.suffix.lower() in (".mp3", ".wav"):
                audio.append(path.relative_to(dest).as_posix())
        return {
            "template_id": template_id,
            "info": self._read_json(dest / "info.json", []),
            "res": self._read_json(dest / "res.json", {}),
            "ctrl": self._read_json(dest / "ctrl.json", []),
            "audio": audio,
            "meta": meta,
        }

    def content_media_path(self, stid, rel_path: str) -> Path | None:
        stid = str(stid)
        if not re.fullmatch(r"[0-9]{1,20}", stid):
            return None
        base = (self.content_cache / stid).resolve()
        candidate = (base / Path(*[p for p in rel_path.replace("\\", "/").split("/") if p])).resolve()
        if not str(candidate).startswith(str(base) + os.sep):
            return None
        return candidate if candidate.is_file() else None

    def template_media_path(self, template_id, rel_path: str) -> Path | None:
        template_id = str(template_id)
        if not re.fullmatch(r"[0-9]{1,20}", template_id):
            return None
        base = (self.template_cache / template_id).resolve()
        candidate = (base / Path(*[p for p in rel_path.replace("\\", "/").split("/") if p])).resolve()
        if not str(candidate).startswith(str(base) + os.sep):
            return None
        return candidate if candidate.is_file() else None

    def cache_remote_media(self, url: str) -> Path:
        """缓存评测结果等外部音频（只允许 ets60.ets100.com）。"""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc not in MEDIA_HOSTS:
            raise EtsError("仅允许缓存 ets60.ets100.com 的评测音频")
        suffix = Path(parsed.path).suffix.lower() or ".bin"
        if suffix not in (".mp3", ".wav", ".xml", ".bin"):
            suffix = ".bin"
        key = hashlib.sha256(url.encode("utf-8")).hexdigest() + suffix
        target = self.media_cache / key
        if target.is_file() and target.stat().st_size > 0:
            return target
        lock = self._download_lock("media:" + key)
        with lock:
            if target.is_file() and target.stat().st_size > 0:
                return target
            data = self.http.get_bytes(url)
            _atomic_write(target, data)
        return target

    # ----- 组合上下文 ----------------------------------------------------

    def current_ecard(self, ecards: list[dict] | None = None) -> dict | None:
        if ecards is None:
            body = self.ecard_list() or {}
            ecards = body.get("data") or []
        if not ecards:
            return None
        active = [e for e in ecards if not e.get("out_of_date")]
        pool = active or ecards
        return sorted(pool, key=lambda e: str(e.get("bind_time") or ""), reverse=True)[0]
