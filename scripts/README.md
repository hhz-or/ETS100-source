# scripts/ —— 分析脚本说明

这些脚本是逆向分析过程中使用的可复现工具，按用途分为两类：

## A. 仓库内可直接运行（无需目标安装）

| 脚本 | 作用 |
|---|---|
| `sign_verify_all.py` | 用 `data/api/sign_samples.json` 验证 API 签名公式（预期 333/334 命中） |
| `update_sign_verify.py` | 验证更新器签名（需要 `ETS/temp/update/log/INFO_uLOG_*`，见下） |
| `plugin_stubs.py` | 从 `runtime/plugin_js_stubs/` 提取插件 action 表 |
| `live_log.py` / `live_paths.py` / `version_diff.py` / `new_modules.py` | 运行时证据的二次分析（输入在 `runtime/`） |

运行方式：在仓库根目录执行

```bash
python scripts/sign_verify_all.py
```

## B. 需要目标程序/日志（会读取 `<ETS_INSTALL_DIR>`）

与签名、密钥流、AES、缓存、日志相关的大部分脚本需要一个 ETS 安装目录或分析工作区。
约定：**把 ETS 安装目录放置（或软链接）为仓库根目录下的 `ETS/`**，或把脚本中的 `ETS/...` 改为你的实际路径；需要 `work/...` 的脚本请先把原始日志/缓存放回对应位置（这些原始文件因含个人信息未随仓库发布）。

典型：

```bash
python scripts/keystream.py          # 读取 ETS/plugins/etshelper/etshelper.pln，重算密钥流并校验 FNV
python scripts/aes_check.py          # 读取 ETS/logs/ets_*.log，验证字段加密（只打印长度，不打印明文）
python scripts/update_sign_verify.py # 读取 ETS/temp/update/log/INFO_uLOG_*
python scripts/extract_sign.py       # 从 ETS/logs/ets_*.log 重建请求/响应样本
```

## C. 原生/Ghidra

`dump_signers.py`、`md5_refs.py`、`keystream.py` 等配合 Ghidra 反编译产物使用；反编译输出（约 41 MB）未随仓库发布，可按 `docs/09_decompiled.md` §7 用 Ghidra 12.1.4 + JDK 21 复跑。

## 说明

- 脚本原本在分析机上以绝对路径运行，仓库版本已将路径归一化为 `ETS/…`、`data/…`、`runtime/…`。
- 涉及日志/凭据的脚本只做本地计算，不会上传任何数据。
