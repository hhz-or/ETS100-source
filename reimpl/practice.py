#!/usr/bin/env python3
"""E 听说 · 练习写链路参考实现（checkstart / OSS 上传 / sync-v2 / 错题 / 用时）

协议见 docs/15_practice_protocol.md。默认只做**只读检查与打印**；所有写操作都需要显式 --apply。

用法：
  python reimpl/practice.py sts                          # 获取 OSS STS（只读）
  python reimpl/practice.py upload --file a.xml --kind xml --apply   # 上传单个文件
  python reimpl/practice.py sync --params p.json --apply             # 回传成绩
  python reimpl/practice.py checkstart --homework-id 111203417 --apply
  python reimpl/practice.py set-use-time --homework-id 111203417 --seconds 300 --apply

前置：reimpl/.state/token.json 或 secrets/app_token.txt 中有登录 token。
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ets_client import EtsClient, EtsError  # noqa: E402

STS_ROUTE = "p1/student/config/config/ossEvaluateUploadStsToken"
OSS_HOST = "https://ets60.oss-cn-hangzhou.aliyuncs.com"
KEY_PREFIX = "ugc/evaluate"


def make_client() -> EtsClient:
    c = EtsClient()
    # 优先使用官方客户端当前 token（secrets/app_token.txt），其次才用本客户端保存的 token
    c.load_token_from_secrets()
    if not c.token:
        c.load_saved_token()
    if not c.token:
        raise SystemExit("没有可用登录 token：先运行 reimpl/server.py 登录，或放置 secrets/app_token.txt")
    return c


def fetch_sts(client: EtsClient) -> dict:
    body = client.call(STS_ROUTE, {})
    # 兼容不同返回包裹
    if isinstance(body, dict) and "data" in body and isinstance(body["data"], dict):
        body = body["data"]
    return body or {}


def oss_upload(local_file: str, kind: str, sts: dict, *, key: str | None = None,
               timeout: int = 120) -> str:
    """表单上传到 OSS，返回公网 URL。kind: mp3|speex|xml。"""
    import requests  # reimpl 依赖项

    local = Path(local_file)
    if not local.is_file():
        raise SystemExit(f"文件不存在：{local}")
    upload = sts.get("upload") or sts
    bucket = upload.get("bucket") or "ets60"
    endpoint = upload.get("endpoint") or "oss-cn-hangzhou.aliyuncs.com"
    cname = upload.get("cname") or f"https://{bucket}.{endpoint}"
    if key is None:
        path_map = {"mp3": "mp3Path", "speex": "spxPath", "xml": "xmlPath"}
        prefix = sts.get(path_map[kind]) or f"{KEY_PREFIX}/{'speex' if kind=='speex' else kind}/middleApp/pc/"
        ext = {"mp3": ".mp3", "speex": ".spx", "xml": ".xml"}[kind]
        key = f"{prefix}public_{uuid.uuid4().hex}_{int(time.time()*1000)}{ext}"
    if not key.startswith("ugc/"):
        key = f"{KEY_PREFIX}/{key.lstrip('/')}"

    access_id = upload.get("accessKeyId")
    access_secret = upload.get("accessKeySecret")
    security_token = upload.get("securityToken")
    if not (access_id and access_secret and security_token):
        raise SystemExit(f"STS 字段缺失，实际字段：{list(upload)}")

    import base64
    import hashlib
    import hmac

    expiration = upload.get("expiration") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 900))
    policy_doc = {"expiration": expiration, "conditions": [
        ["content-length-range", 0, 524288000],
        ["eq", "$bucket", bucket],
        ["eq", "$key", key],
    ]}
    policy = base64.b64encode(json.dumps(policy_doc, separators=(",", ":")).encode()).decode()
    signature = base64.b64encode(hmac.new(access_secret.encode(), policy.encode(), hashlib.sha1).digest()).decode()

    data = {
        "OSSAccessKeyId": access_id,
        "policy": policy,
        "Signature": signature,
        "x-oss-security-token": security_token,
        "x-oss-object-acl": "public-read",
        "key": key,
        "submit": "Submit",
        "success_action_status": "200",
    }
    mime = mimetypes.guess_type(str(local))[0] or "application/octet-stream"
    with local.open("rb") as fh:
        files = {"file": (local.name, fh, mime)}
        resp = requests.post(f"https://{bucket}.{endpoint}/", data=data, files=files, timeout=timeout)
    if resp.status_code not in (200, 201, 204):
        raise SystemExit(f"OSS 上传失败 {resp.status_code}: {resp.text[:300]}")
    return cname.rstrip("/") + "/" + key


def upload_artifacts(mp3: str, spx: str, xml: str, sts: dict) -> dict:
    url_mp3 = oss_upload(mp3, "mp3", sts)
    url_spx = oss_upload(spx, "speex", sts, key=url_mp3.replace(OSS_HOST + "/", "").replace("https://ets60.ets100.com/", "ugc/evaluate/mp3/", 1).replace("/mp3/", "/speex/", 1) + ".spx")
    url_xml = oss_upload(xml, "xml", sts, key=url_spx.replace("ugc/evaluate/speex/", "ugc/evaluate/xml/", 1).rsplit(".spx", 1)[0] + ".xml")
    return {"mp3": url_mp3, "spx": url_spx, "xml": url_xml}


def build_sync_params(score_json: dict, urls: dict, *, resource_id: str, set_id: str,
                      entity_id: str, order: str, homework_id: str, first_column_id: str = "1",
                      question_type_score: str = "0.5", trace_id: str = "", real_score: float = 0,
                      score: float = 0, rate_scale: int = 1, graduation: str = "0.125") -> dict:
    score_detail = {
        "accuracy_score": float(score_json.get("accuracy_score", 0) or 0),
        "fluency_score": float(score_json.get("fluency_score", 0) or 0),
        "integrity_score": float(score_json.get("integrity_score", 0) or 0),
        "standard_score": float(score_json.get("standard_score", 0) or 0),
        "total_score": float(score_json.get("total_score", 0) or 0),
        "real_score": float(real_score),
        "category": score_json.get("category", "read_sentence"),
        "rate_scale": 1,
    }
    return {
        "resource_id": str(resource_id),
        "real_score": real_score,
        "score": score,
        "set_id": str(set_id),
        "entity_id": str(entity_id),
        "order": str(order),
        "mistake_id": "",
        "upload_file_id": "",
        "upload_file_url": urls["mp3"],
        "spx_file_url": urls["spx"],
        "mark_trace_id": trace_id,
        "detail_file_id": "",
        "detail_file_url": urls["xml"],
        "score_detail": json.dumps(score_detail, separators=(",", ":")),
        "exam_id": None,
        "homework_id": str(homework_id),
        "first_column_id": str(first_column_id),
        "question_type_score": str(question_type_score),
        "rate_scale": rate_scale,
        "graduation": graduation,
        "client_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mark_service": 1,
        "version": "2",
    }


def main():
    ap = argparse.ArgumentParser(description="练习写链路参考实现")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sts", help="获取 OSS STS")
    sp.add_argument("--apply", action="store_true", help="（sts 无需 apply）")

    up = sub.add_parser("upload", help="上传单个文件")
    up.add_argument("--file", required=True)
    up.add_argument("--kind", choices=["mp3", "speex", "xml"], required=True)
    up.add_argument("--key", help="自定义 OSS key")
    up.add_argument("--apply", action="store_true", help="真正执行上传")

    sy = sub.add_parser("sync", help="成绩回传 /m/audio/sync-v2")
    sy.add_argument("--params", required=True, help="完整参数 JSON 文件")
    sy.add_argument("--apply", action="store_true")

    cs = sub.add_parser("checkstart", help="g/homework/checkstart")
    cs.add_argument("--homework-id", required=True)
    cs.add_argument("--apply", action="store_true")

    ut = sub.add_parser("set-use-time", help="m/homework/set-use-time")
    ut.add_argument("--homework-id", required=True)
    ut.add_argument("--seconds", type=int, required=True)
    ut.add_argument("--resource-id", default="239")
    ut.add_argument("--correct", type=int, default=0)
    ut.add_argument("--apply", action="store_true")

    args = ap.parse_args()
    client = make_client()

    if args.cmd == "sts":
        sts = fetch_sts(client)
        safe = {k: ("***" if "secret" in k.lower() or "token" in k.lower() else v) for k, v in sts.items()}
        print(json.dumps(safe, ensure_ascii=False, indent=1))
        return 0

    if args.cmd == "checkstart":
        if not args.apply:
            print(f"[dry] g/homework/checkstart homework_id={args.homework_id}")
            return 0
        body = client.call("g/homework/checkstart", {"homework_id": str(args.homework_id)})
        print(json.dumps(body, ensure_ascii=False, indent=1))
        return 0

    if args.cmd == "set-use-time":
        params = {"version": 2, "correct": args.correct, "use_time": int(args.seconds),
                  "resource_id": str(args.resource_id), "homework_id": int(args.homework_id)}
        if not args.apply:
            print("[dry]", json.dumps(params, ensure_ascii=False))
            return 0
        print(json.dumps(client.call("m/homework/set-use-time", params), ensure_ascii=False, indent=1))
        return 0

    if args.cmd == "upload":
        if not args.apply:
            print(f"[dry] upload {args.file} kind={args.kind}")
            return 0
        sts = fetch_sts(client)
        url = oss_upload(args.file, args.kind, sts, key=args.key)
        print("OK", url)
        return 0

    if args.cmd == "sync":
        params = json.loads(Path(args.params).read_text(encoding="utf-8"))
        if not args.apply:
            print("[dry] sync params:", json.dumps(params, ensure_ascii=False)[:300])
            return 0
        body = client.call("m/audio/sync-v2", params)
        print(json.dumps(body, ensure_ascii=False, indent=1))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
