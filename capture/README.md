# ETS 练习抓包工具（capture/）

> 目的：抓一次**真实练习**的完整数据链，补全尚未实现的「录音 / 评测 / 提交 / 上传」等写接口与 WebSocket 协议。
> 输出目录默认在 `capture/runs/<时间戳>/`，**不会**提交到仓库（见 `.gitignore`）。

## 前置

1. 官方客户端已启动，且窗口可见（CDP 端口 10086 可用）。
2. `node` 可用；`ws` 模块用官方客户端自带的即可（脚本会回退到 `ETS/mq_server/node_modules/ws`）。
3. Frida（原生采集用）：`python -m pip install frida`。
   - 若之前装过，脚本会自动尝试 `C:\ets_park\work_pylibs` / `D:\ets-rea\work\pylibs` 等路径。

## 一键运行

```powershell
pwsh -File capture\run_capture.ps1
```

启动 4 个采集器：

| 采集器 | 抓什么 | 输出 |
|---|---|---|
| `cdp_capture.js` | 渲染进程网络、**WebSocket 帧**（ISE 评测）、console | `ws.jsonl`、`renderer_http.jsonl`、`console.jsonl` |
| `native_capture.py` | `HttpHelper` 的 **WinHTTP 明文请求/响应**（HTTPS 解密前） | `native_http.jsonl` |
| `log_tail.py` | 客户端 `logs/ets_*.log` 新增行 | `logs.jsonl` |
| `files_watch.py` | 录音/音频/评测 xml/题库包等新文件 | `files.jsonl`、`files/fs/…` |

看到提示后，**做一次完整练习**（建议 3-5 分钟）：

1. 我的作业 → 开始练习
2. 按提示录音（麦克风）→ 等即时评分/评测结果
3. 如果可能：再进一次套卷/模拟考试
4. 完成或提交作业（页面有提交按钮就点）

完成后回到终端按 **Enter** 停止。

## 汇总

```powershell
python capture\summarize.py capture\runs\<时间戳>
```

生成 `REPORT.md`、`api_calls.json`、`ws_samples.json`、`files_index.json`（已脱敏：token/手机号/密码/姓名），把整个 `runs/<时间戳>` 目录或 `REPORT.md` 给 Lead 分析即可。

## 注意

- 抓包内容含账号信息与录音，属于**本地敏感数据**：不要上传、不要提交 git（`capture/runs/` 已忽略）。
- Frida 只做只读 Hook（不改参数/返回值），退出时可正常 detach；若客户端正在使用中，采集器可在练习前后随时启动/停止。
- 如果 10086 端口不可用：官方客户端启动参数中没有 `--remote-debugging-port=10086` 时，CDP 采集器会报错；此时仍可用 native/logs/files 三个采集器（它们不依赖 CDP）。
