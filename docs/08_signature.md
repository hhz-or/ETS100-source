# 08 API 签名算法（head.sign）——已完整还原并验证

> 结论：**已还原，且用历史日志中 334 组真实请求验证：333/334 精确命中**（唯一不中的是 `/user/login`，原因是日志脱敏把 `password` 置空，签名原文不可见）。
> 可执行实现：[work/api/ets_sign.py](../work/api/ets_sign.py)；验证脚本：[work/scripts/sign_verify_all.py](../work/scripts/sign_verify_all.py)。

---

## 一、协议层：签名在哪、长什么样

前端（`work/frontend/bundles/` 主 bundle，`EtsSignatureAdapter` 类）流程：

```js
const s = [{ r: apiPath, params: Object.assign({}, COMMON, params) }];  // 业务数组
const l = JSON.stringify(s);                    // 紧凑 JSON
const c = base64(l);                            // ★ 注意：签名/传输的 body 是 base64 字符串
const u = String(Date.now());                   // 13 位毫秒字符串

// v2 优先；失败回退 v1
o = await etsSignatureAdapter.signBody({ body: c, time: u });   // 调原生
// 原生返回 { pid, sign, key_id, sign_version:"2" }
request.body = { body: c,
                 head: { version: "1.0", sign: o.sign, pid: o.pid,
                         time: u, time_second: Number(u) } };
```

- 原生 action：`encode_api_body_v2`（v2）/ `encode_api_body`（v1），实现位于 `plugins\etshelper\etshelper.pln`。
- 前端解析 v2 结果要求：`pid` 非空、`sign_version === "2"`、`key_id` 非空、`sign` 为 32 位十六进制（正则 `/^[a-f\d]{32}$/i`）。
- 前端日志里实测：`ets_sign_protocol_selected protocol=v2, pid=pcWin`。

---

## 二、原生实现（Ghidra 12.1.4 反编译，证据可复现）

反编译全文：`work/ghidra_out/etshelper.pln/decompiled.c`（89,518 行）。

| 地址 | 函数 | 作用 |
|---|---|---|
| `0x1000aa70` | `PlnOnProcessMessage` | 插件消息分发：按 action 字符串路由 |
| `0x1000a410` | `OnEncodeAPIBody` | 请求体签名（`etshelper.cpp:0x1d9`–`0x1ed`） |
| `0x10009e60` | `OnEncodeAPIResp` | 响应签名（`etshelper.cpp:0x1a9`） |
| `0x10014110` | `sign_body` | MD5 组装：`PID ‖ time ‖ body_b64 ‖ keystream` |
| `0x10014230` | `sign_resp` | 同上，参数顺序略不同 |
| `0x10013e00` | `feed_key` | 从内嵌表派生 32 字节"密钥流"，并做 FNV-1a 完整性校验 |
| `0x10013d30` | `key_byte(i)` | 单字节密钥流生成（查表 + 旋转/减/XOR） |
| `0x100050a0` / `0x100051c0` | `build_v1_result` / `build_v2_result` | 组装返回 JSON（v2 含 `key_id`/`sign_version`） |

### 2.1 调度关系（观察）

```
PlnOnProcessMessage:
  action == "encode_api_body"      → OnEncodeAPIBody(prefixPid="grlx", select=0)   // v1
  action == "encode_api_resp"      → OnEncodeAPIResp(prefixPid="grlx", select=0)   // v1
  action == "encode_api_body_v2"   → OnEncodeAPIBody(prefixPid="pcWin", select=1)  // v2
  action == "encode_api_resp_v2"   → OnEncodeAPIResp(prefixPid="pcWin", select=1)  // v2
```

`select` 决定使用哪一组内嵌密钥表（0=v1，1=v2）。

> 补充（来自 native-analyst 的独立反汇编交叉验证）：签名前还有一道**本地闸门** `FUN_10013fc0`（`0x13FC0`）——要求内部状态已初始化、参数长度上限（0x400 / 0x1000000）、并用 `GetTickCount` 做 1000 ms 窗口 + 计数器（上限 0x401）限流，失败即 `[etshelper::OnEncodeAPIBody] signature request rejected.`。这是**本地防刷/限流**，不是网络校验；正常业务不会触发。

### 2.2 密钥流（观察，含完整性校验）

`FUN_10013e00(select, md5ctx)`：

- `select==0`：数据表 `0x10069208`（0x32×4 字节）、索引表 `0x100691C8`（32×uint16），FNV-1a 期望值 `0x32A7B273`
- `select==1`：数据表 `0x10069310`（0x3D×4 字节）、索引表 `0x100692D0`（32×uint16），FNV-1a 期望值 `0xB9EF3CD1`

`FUN_10013d30` 对 32 个索引逐字节生成：

```
idx  = u16le(index_table[i])  ; i = 0..31
b0,b1,b2,b3 = data_table[idx*4 + 0..3]
r = b3 & 7
if r: b0 = ror8(b0, r)
out[i] = ((b0 - b2) & 0xFF) ^ b1
```

32 个字节恰好组成 32 个 ASCII 十六进制字符。**用 PE 文件直接提取数据表并重算，FNV-1a 校验与代码期望值完全一致**（验证脚本 `work/scripts/keystream.py`），因此密钥流可靠：

| 协议 | 派生结果（32 字符 ASCII） |
|---|---|
| v1（select=0） | `355ffbe95ccf4e9535a110170b445ab8` |
| v2（select=1） | `94cfbda3fbfef02b93693f8bc153be82` |

> 这 32 字节本质是"密钥"，通过查表混淆 + FNV 自校验隐藏在 `.rdata`，不是明文常量，静态字符串搜不到（二进制里搜这两个 ASCII 串 = 0 次）。

### 2.3 最终公式（已实测验证）

```
sign = MD5( PID_PREFIX  +  time_ms_string  +  base64(JSON.stringify(body))  +  KEY )
```

- v2：`PID_PREFIX = "pcWin"`，`KEY = 94cfbda3fbfef02b93693f8bc153be82`，`time_ms_string = String(Date.now())`
- v1：`PID_PREFIX = "grlx"`，`KEY = 355ffbe95ccf4e9535a110170b445ab8`，`time` 为秒级或不带 `time_second`（本安装实测全部走 v2，v1 仅代码路径存在）

返回 JSON（v2）：

```json
{"pid":"pcWin","key_id":"202608","sign":"<32hex>","sign_version":"2"}
```

- `key_id = "202608"`（硬编码在 `FUN_100051c0` 中，字符串 `202608`）→ 密钥版本号/年月，服务端据此轮换。
- `sign_version = "2"`。

---

## 三、验证结果（真实数据）

样本：`work/api/sign_samples.json`（334 组，来自两份 `ets_*.log`，含 `body_json_exact` 与 `head.sign`）。

| 项 | 结果 |
|---|---|
| 命中 | **333 / 334** |
| 唯一不中 | `ets_2026-11-4.log:55` → `POST /user/login` |
| 原因 | 日志脱敏函数对 `user/login` 强制把 `params.password` 置空（`LoggerUtils.desensitization`），而**签名是对"含密文密码的真实 body"计算的**，故脱敏后的 body 无法复现签名。属预期差异，非算法错误。 |
| **运行时复核（2026-11-06 live）** | 新会话日志 68 条带 `head.sign` 的请求：**68 / 68 命中**（在线版本 core 代码与缓存一致，见 `11_runtime_live.md`） |

复现命令：

```bash
python D:\ets-rea\work\scripts\sign_verify_all.py
# v2 verify: 333/334 match
```

参考实现（`work/api/ets_sign.py`）：

```python
import hashlib, base64
KEY_V2, PID_V2 = "94cfbda3fbfef02b93693f8bc153be82", "pcWin"
def sign_v2(body_json_str: str, time_ms_str: str) -> str:
    b64 = base64.b64encode(body_json_str.encode("utf-8")).decode()
    return hashlib.md5((PID_V2 + time_ms_str + b64 + KEY_V2).encode()).hexdigest()
```

---

## 四、响应签名（encode_api_resp / _v2）

- `FUN_10014230` 与请求签名同构：`MD5( PID ‖ A ‖ B ‖ body_or_resp ‖ KEY)`，最后追加同一密钥流并做 FNV 校验。
- 前端只在需要校验服务端响应时调用 `signResponse(resp, protocol)`；本安装的 341 条响应日志中**未出现带 `sign` 的响应体**（`sign_response:1` 参数存在，但服务端未回签名），因此该路径**未取得运行时样本**。
- 结论：算法结构已确认，字段顺序由反编译确定；运行时未触发 → 标为"已还原但未实测"。

---

## 五、与更新器（EtsUpdate.exe）的关系 —— 也已还原并验证

- 更新请求同样是 `head{version,sign,pid:"grlx",time(秒)} + body(base64)`，**同一套 MD5 拼接结构**，但使用**独立的第三把密钥**：

```
sign = MD5( "grlx" + time_seconds + base64(JSON body) + "555ffbe95ccf4e9535a110170b445ab8" )
```

- 证据：`EtsUpdate.exe` 反编译 `FUN_0042f070`（`work/ghidra_out/EtsUpdate.exe/decompiled.c`）显式初始化签名上下文：
  - `pid = "grlx"`、`version = "1.0"`
  - `key = "555ffbe95ccf4e9535a110170b445ab8"`（注意与 API v1 的 `355ff…` 仅首字符不同 → 更新器专用变体）
  - MD5 实现位于 `0x00438b23`（init）与 `0x0043985e`（init，另一处），常量 `0x67452301/0xefcdab89/0x98badcfe/0x10325476`。
- **验证：3/3 精确命中**（三份 `temp\update\log\INFO_uLOG_*` 的真实请求）：
  `b5a4daff…`、`f39649aa…`、`94ddc31a…`。证明文件：`work/api/update_sign_proof.json`；脚本：`work/scripts/update_sign_verify.py`。
- 客户端版本号 `client_version=5079` 取自 `ETS.db.Update_Version`；`time` 为 Unix **秒**（与 API 的毫秒不同）。

---

## 六、字段级加密（登录手机号/密码）——已实测解密

签名之外，前端对**敏感字段**还会做一层对称加密（源码在主 bundle 的 `encrypt$1`）：

```js
const encrypt$1 = (plain, {isServes, secretKey, mode, padding} = {}) => {
  const key = secretKey ?? envConfig(isServes ? "k_serves" : "k");
  return CryptoJS.AES.encrypt(CryptoJS.enc.Utf8.parse(plain),
                              CryptoJS.enc.Utf8.parse(key),
                              { mode: ECB, padding: Pkcs7 }).toString();  // → Base64
};
```

密钥硬编码在 `envConfig()` 中（主 bundle 偏移 ≈0x78800）：

| 逻辑名 | 实际值 | 用途 |
|---|---|---|
| `k` | `ldlflfgirerjfkcf` | 本地/非服务端字段 |
| `k_serves` | `f05323cb91d422b2` | 上传服务端的敏感字段（`isServes:true`） |
| `RSA_PUBLIC_KEY` | **一段 `-----BEGIN RSA PRIVATE KEY-----` PEM** | `rsaEncrypt()`（JSEncrypt）使用；客户端内置私钥属安全问题 |

**实测验证**（`work/scripts/aes_check.py`）：日志中 `params.phone` / `params.password` 的 Base64 密文用 `k_serves` + AES-128-ECB + PKCS7 解密，得到明文手机号/密码（3/3 成功；明文不在此展示，已脱敏）。这解释了：

- 为什么 `user/login` 的签名样本无法复核（日志脱敏把 `password` 置空，而签名针对含密文的真实 body，见 §三）；
- 为什么协议里 `sn/phone/password` 等字段看似乱码。

**结论**：字段加密 + 签名都可在客户端完整复现；两者都只是"防篡改/防明文"级别的保护，不构成对本地攻击者的安全边界。

---

## 七、安全性评价

1. 算法本身是 **MD5(明文拼接)**，无 HMAC、无 nonce 参与服务端校验之外的变化；`time` 参与签名，具备基本重放窗口（服务端需自行校验时间窗）。
2. 密钥以"查表混淆 + FNV 自校验"方式内嵌客户端，**任何本地运行者都可提取**（本报告即证明），因此它只能防"随手改包"，不能防有动机的逆向者。
3. `key_id="202608"` 表明厂商有密钥轮换机制；v1/v2 并存允许灰度切换。
4. 对互操作性研究而言：**服务端鉴权完全依赖该 sign + token**；还原后可构造合法请求（仅限自有授权环境）。

---

## 八、证据索引

| 证据 | 位置 |
|---|---|
| 前端签名调用与信封构造 | `work/frontend/bundles/` 主 bundle（搜 `EtsSignatureAdapter` / `signBody` / `HEAD_VERSION`） |
| v2 结果校验 | 主 bundle：`parseV2SignResult`、`SIGN_PATTERN=/^[a-f\d]{32}$/i`、`V1_PID="grlx"` |
| 原生实现 | `work/ghidra_out/etshelper.pln/decompiled.c`：`FUN_1000a410`、`FUN_10014110`、`FUN_10013e00`、`FUN_10013d30`、`FUN_100051c0` |
| 密钥表提取与 FNV 校验 | `work/scripts/keystream.py`（输出 MATCH） |
| 334 组真实样本 | `work/api/sign_samples.json` |
| 批量验证 | `work/scripts/sign_verify_all.py`（333/334） |
| 参考实现 | `work/api/ets_sign.py` |
