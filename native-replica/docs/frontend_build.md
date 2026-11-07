# 前端构建与页面说明（native-replica/frontend + mq_server）

> 范围：`native-replica/frontend/`、`native-replica/mq_server/`、本文档。
> 未修改 `shell/`、`plugins/`、`shared/`、`CMakeLists.txt`。
> 对接契约：`native-replica/CONTRACT.md` §4（JS↔Host 桥）、§5（`__core`）、§6（插件 action）、§7（前端要求）、§8（mq_server）。

---

## 1. 验收摘要

| 项 | 结果 |
|---|---|
| 依赖安装 | `pnpm install --store-dir C:\rea_tools\pnpm-store` 成功（72 包，esbuild postinstall 已执行） |
| 前端构建 | `pnpm run build` 成功，生成 `frontend/dist/`（Vite 8.3.6，1621 modules，约 3–5s） |
| mq_server | `node main.js` 启动成功；40001；连接回 `hello mq_server!`；消息落盘并回显；40001 占用时自动 +1 到 40002 |
| Mock 预览 | 浏览器直接访问构建产物可完整预览；11 条路由巡检 0 异常/0 console error（最终 Vite 8 构建对首页/练习/设置复检 0 异常） |
| 截图 | 仅本机临时目录留证，未提交任何图片 |

构建产物（最后一次 `pnpm run build`）：

```text
dist/index.html                            1.26 kB
dist/assets/index-*.css                  ≈383 kB (gzip 52.7 kB)
dist/assets/index-*.js                   ≈882 kB (gzip 281.5 kB)
dist/assets/bridge-*.js                   91.32 kB (gzip 34.76 kB)   # mock 数据/桥
dist/assets/message-*.js                  85.20 kB (gzip 30.56 kB)   # Element Plus message 等
dist/assets/Home-*.js                      8.74 kB
dist/assets/Practice-*.js                 14.44 kB
...（Login / Homework / HomeworkDetail / Sets / Courses / Mistakes / Settings / About 各自独立 chunk）
```

Element Plus 采用全量引入（`element-plus/dist/index.css` + 全量组件），因此主 CSS/JS 体积偏大；这是为了保证壳内离线可用、不依赖外网 CDN。若后续要压缩体积，可改为按需自动导入。

---

## 2. 技术栈与版本

| 组件 | 版本（本次安装解析） |
|---|---|
| Node.js | 24.22.1 |
| pnpm | 12.16.1 |
| Vue | 3.5.45（`<script setup>`） |
| Vite | 8.3.6 |
| Pinia | 3.0.4 |
| Vue Router | 4.6.4（hash history） |
| Element Plus | 2.14.7 |

> Vite 版本由 pnpm 解析为 8.x（`package.json` 已记录 `^8.0.0`，`pnpm-lock.yaml` 固定 8.3.6）。Node 24 满足 Vite 8 要求。

---

## 3. 构建命令

```powershell
cd D:\ets-rea\native-replica\frontend

# D: 空间紧张，必须把 store 放到 C:
pnpm install --store-dir C:\rea_tools\pnpm-store

# 构建（输出 dist/）
pnpm run build
```

本地预览（Vite preview）：

```powershell
pnpm run preview
# Vite preview 绑定 localhost，请访问 http://localhost:4173/
# 首页自动演示登录：http://localhost:4173/#/login?autologin=1
```

开发模式：

```powershell
pnpm run dev
```

### 3.1 pnpm 12 的两个注意点

1. **构建脚本白名单**：pnpm 12 默认拦截依赖的 postinstall。`frontend/pnpm-workspace.yaml` 已声明：

   ```yaml
   onlyBuiltDependencies:
     - esbuild
   ```

   如果换机器/换 store 后仍报 `ERR_PNPM_IGNORED_BUILDS`，执行一次：

   ```powershell
   pnpm approve-builds --all
   pnpm install --store-dir C:\rea_tools\pnpm-store
   ```

2. **store 必须显式指定**：pnpm 12 不再读取 `package.json` 的 `pnpm` 字段；而跨盘（C: store → D: 工程）hardlink 会被拒绝。因此安装时务必带 `--store-dir C:\rea_tools\pnpm-store`。装好后 `pnpm run build` 不会再次联网安装（`node_modules` 与 lockfile 一致时）。

### 3.2 与 build.ps1 的衔接

`build.ps1` 的流程与本文一致：

- `node_modules` 不存在时执行 `pnpm install --store-dir C:\rea_tools\pnpm-store`；
- `pnpm run build`；
- 把 `frontend/dist/*` 复制到 `assets/web`；
- 把 `mq_server/*.js`、`package.json` 复制到 `bin/mq_server` 并在目标目录 `npm install`。

因此前端构建产物无需额外配置，`base: './'` 已保证相对路径资源可被 WebView2 虚拟主机加载。

### 3.3 浏览器直接打开 dist 的说明

- **推荐**：用任意静态 HTTP 服务（`pnpm run preview`、`python -m http.server`、壳内虚拟主机）访问 `dist/index.html`。
- 直接双击 `dist/index.html`（`file://`）时，浏览器会因 ES Module 的 CORS 限制拒绝加载 `assets/*.js`；这是浏览器安全策略，不是应用错误。
- 路由为 **hash 模式**（与原作一致），例如 `#/home`、`#/homework/111203417`、`#/practice?stid=...`。

---

## 4. 目录结构

```text
frontend/
├─ index.html                 # 启动占位屏 + Vite 入口
├─ vite.config.js             # base:'./'，outDir:'dist'
├─ package.json / pnpm-lock.yaml / pnpm-workspace.yaml
└─ src/
   ├─ main.js                 # createApp + Pinia + Router + Element Plus(zh-cn)
   ├─ App.vue                 # 全局路由出口 + 登录失效事件
   ├─ styles.css              # 全部自写样式（顶栏/侧栏/卡片/练习页/登录页）
   ├─ bridge.js               # window.cef.message 封装 + mock 分流
   ├─ api.js                  # 统一信封、签名、登录、业务接口
   ├─ content.js              # content 包下载/解压/读取/媒体 URL
   ├─ mock.js                 # 浏览器预览用的内置假数据与插件 mock
   ├─ utils.js                # 日期/状态/大小等展示工具
   ├─ router/index.js         # 路由表 + token 守卫
   ├─ stores/user.js          # Pinia：token/profile/ecards/systemConfig
   ├─ layout/MainLayout.vue   # 顶栏 + 左侧导航 + 内容区 + mock 横幅
   └─ views/
      ├─ Login.vue  Home.vue  Homework.vue  HomeworkDetail.vue
      ├─ Sets.vue   Courses.vue  Practice.vue  Mistakes.vue
      └─ Settings.vue  About.vue
```

---

## 5. 页面清单

| 页面 | 路由（hash） | 主要接口/数据 | 说明 |
|---|---|---|---|
| 登录 | `#/login` | `EtsHelper.aes_ecb_encrypt` ×2 → `EtsHelper.encode_api_body_v2` → `HttpHelper.request user/login` | 手机号/密码登录；token 存 localStorage；Mock 下支持“一键体验”与 `?autologin=1` |
| 首页 | `#/home` | `g/homework/list`、`m/mistake/summary`、`m/ecard/list`、`m/advertisement/list` | 渐变 Hero + 三张指标卡 + 学习模块卡 + 最近作业 + 学习卡/公告 |
| 作业列表 | `#/homework` | `g/homework/list` | `待完成/已完成/已过期` 三态；类型筛选；分页；点击进入详情 |
| 作业详情 | `#/homework/:id` | `m/homework/info` | 作业信息、得分/用时/题数、题目列表；逐题进入练习页 |
| 套卷 | `#/sets` | `g/set/column-v2`、`g/set/list` | 左侧栏目、右侧套卷卡片；搜索；开始练习 |
| 同步课程 | `#/courses` | `g/resource/grade-list`、`g/resource/book-list`、`g/set/unit-list`、`g/set/unit-info`、`g/set/module-list` | 年级 → 教材 → 单元 → 模块四级；模块进入练习 |
| 练习 | `#/practice?stid=` | `HttpHelper.download` → `SevenZip.unzip` → `FileHelper.readfile(content.json)` → `__core.media_url` | 渲染 `collector.read` / `collector.dialogue` / `collector.picture`；题干/答案/解析/音频/图片；加载步骤时间线 |
| 错题本 | `#/mistakes` | `m/mistake/summary`、`m/mistake/list` | 待订正/已订正；听说/读写筛选；去订正 |
| 设置 | `#/settings` | `user/info`、`m/ecard/list`、`ShellHelper.getpcinfo/getuniqueid/getvolume/setvolume/getconfig`、`__core.info` | 账号、学习卡切换、设备信息、音量、网络检测、本地目录 |
| 关于 | `#/about` | `__core.info` | 技术栈、页面/接口映射、桥说明、未实现项、免责声明 |

公共交互：

- 顶栏：品牌、当前年级、Mock 标识、公告、学习卡、用户下拉（设置/关于/退出）。
- 左侧导航：首页 / 我的作业 / 套卷练习 / 同步课程 / 错题本 / 设置 / 关于；当前路由高亮。
- 登录失效：任一接口返回 `20004` / `30001` 时清除 token 并跳转登录页（`AUTH_EXPIRED_EVENT`）。
- 所有页面都有加载态、空态与接口错误提示，不白屏。

---

## 6. 桥封装（`src/bridge.js`）

### 6.1 模式判定

```js
isMock = !(window.chrome?.webview && window.cef?.message)
```

- 原生（WebView2 壳）：走 `window.cef.message.sendMessage / setMessageCallback / removeMessageCallback / createGuid`。
- Mock（普通浏览器）：走 `src/mock.js` 的 `mockInvoke()`，不访问真实网络。

### 6.2 调用 API

```js
invoke(plugin, action, argsObjOrString = '', timeoutMs = 30000) -> Promise<any>
invokeJson(plugin, action, argsObjOrString = '', timeoutMs = 30000) -> Promise<any>
```

实现要点：

- 每次调用生成唯一 `uid = createGuid() + '@' + action`；
- 先 `setMessageCallback(uid, cb)`，再 `sendMessage(uid, plugin, action, args)`；
- 回调到达后 `removeMessageCallback(uid)` 并 resolve 原始 `data`（通常是 JSON 字符串）；
- 超时（默认 30s）或 `sendMessage` 抛错时清理回调并 reject；
- `invokeJson` 对字符串尝试 `JSON.parse`，失败时原样返回（兼容 `get_appdata_path` 这类纯文本返回）。

### 6.3 便捷方法

| 方法 | 说明 |
|---|---|
| `mediaUrl(path)` | 调 `__core.media_url({path})`，返回 `url`；失败返回 `''` |
| `coreInfo()` | 调 `__core.info` 获取 appDir/dataDir/cacheDir/homeUrl/version |
| `openExternal(url)` | 仅允许 `http(s)`，调 `__core.open_external` |
| `logToHost(level, tag, msg)` | 调 `__core.log` 上报；失败静默 |
| `isMock` / `bridgeMode` | 当前模式（`'mock'` / `'native'`） |

---

## 7. API 层（`src/api.js`）

### 7.1 统一信封

请求按 CONTRACT §7：

```text
params = { sign_response:1, sn:"test", system:4, global_client_version:"5.7.9", token?, ...业务参数 }
bodyArray = [{ r: route, params }]
bodyB64 = btoa(unescape(encodeURIComponent(JSON.stringify(bodyArray))))
time = String(Date.now())
signInfo = EtsHelper.encode_api_body_v2({ body: bodyB64, time })
head = { version:"1.0", sign: signInfo.sign, pid: signInfo.pid || "pcWin",
         time, time_second: Number(time) }
HttpHelper.request({ url: "https://api.ets100.com/<r>", method:"POST",
                     body: JSON.stringify({ body: bodyB64, head }),
                     headers: { "Content-Type": "application/json;charset=UTF-8" } })
```

- 指定 `HttpHelper.request` 的 `method` 为 POST；响应按 `[{ msg, code, body }]` 解包。
- `encode_api_body_v2` 失败/签名格式不合法时，回落到 `encode_api_body`（v1，`pid="grlx"`）。
- 响应 `code === 20004 || 30001` → 清除 token、派发 `ets:auth-expired`、抛 `AuthExpiredError`。
- 其他非 0 code → 抛 `ApiError(code, msg)`，页面显示中文错误。
- `sign_response:1`、`sn:"test"`、`system:4`、`global_client_version:"5.7.9"` 固定。
- 请求/响应日志经 `__core.log` 上报；**请求日志中的 token 替换为 `***`**，避免 JWT 明文落盘。
- `getDeviceInfo()`：`ShellHelper.getpcinfo` + `getuniqueid` 派生 `device_name`、`device_code`（16 位大写 hex）、`local_ip`，并缓存到 localStorage。

### 7.2 登录链（与 CONTRACT §7 一致）

```text
1) EtsHelper.aes_ecb_encrypt({plain: phone})    -> { b64 }
   EtsHelper.aes_ecb_encrypt({plain: password}) -> { b64 }
2) params = { sign_response:1, sn:"test", system:4,
              global_client_version:"5.7.9",
              phone:<enc>, password:<enc>,
              device_name, device_code, local_ip, version:4 }
3) bodyB64 = base64(UTF-8(JSON.stringify([{ r:"user/login", params }])))
4) EtsHelper.encode_api_body_v2({ body, time }) -> { sign, pid, key_id, sign_version:"2" }
5) HttpHelper.request POST https://api.ets100.com/user/login
   body = {"body":bodyB64,"head":{"version":"1.0","sign":...,"pid":"pcWin","time":"...","time_second":...}}
6) 响应 [{msg,code,body}]；body.token 存 localStorage("ets_token")
```

登录页也会缓存用户输入的手机号（`ets_login_phone`，仅“记住手机号”勾选时），不保存密码。

### 7.3 已封装的接口

| 方法 | 路由 |
|---|---|
| `getUserInfo` | `user/info` |
| `getSystemConfig` | `system/config`（`checkToken:false`） |
| `getAnnouncements` | `/announcement/list` |
| `getSystemTime` | `system/time` |
| `getHomeworkList` | `g/homework/list` |
| `getHomeworkInfo` | `m/homework/info` |
| `getMistakeSummary` / `getMistakeList` | `m/mistake/summary` / `m/mistake/list` |
| `getEcardList` | `m/ecard/list` |
| `getColumns` / `getSets` | `g/set/column-v2` / `g/set/list` |
| `getUnits` / `getUnitInfo` / `getModules` | `g/set/unit-list` / `g/set/unit-info` / `g/set/module-list` |
| `getBooks` / `getGrades` | `g/resource/book-list` / `g/resource/grade-list` |
| `getAdvertisements` | `m/advertisement/list` |
| `login` / `logout` | `user/login` / `user/logout` |

> 业务参数是根据 CONTRACT、`docs/03_api_protocol.md` 与 `work/reimpl_probe/*.json` 推断的最小集合；真实接口对分页/筛选字段的要求可能更严格，见 §12。

---

## 8. content 包与练习页

### 8.1 加载链路

`src/content.js → loadContentPackage({ stid, zipUrl })`：

```text
1) __core.info -> cacheDir
2) 原生模式：FileHelper.existfileorfolder(<cache>/practice/<stid>/content.json)
   命中则直接 readfile（缓存优先）
3) FileHelper.createfolder(<cache>/practice/<stid>)
4) HttpHelper.download({ url, filePath: <cache>/practice/<stid>.zip })
5) SevenZip.unzip({ zipPath, outDir: <cache>/practice/<stid> })
6) FileHelper.readfile({ filePath: <outDir>/content.json })
7) JSON.parse -> structure_type / info
```

每一步都会写入练习页右侧的“加载过程”时间线（成功/失败/跳过 + 路径），失败时展示错误并支持“载入内置示例”。

Mock 模式会强制走完整 4 步（创建/下载/解压/读取），以便在浏览器里演示链路。

### 8.2 渲染的题型

| structure_type | 渲染内容 |
|---|---|
| `collector.read` | `info.value` 题干、`info.translate` 译文、`info.audio` 示范音频、`info.analyze` 解析、参考原文 |
| `collector.dialogue` | `info.question[]` 的 `ask` / `askaudio` / `std[].value` / `keywords`，`info.answer`、`info.analyze`、配图 |
| `collector.picture` | `info.value` 题干、`info.image` 配图、`info.std[].value` 参考范文、`info.keypoint`、`info.topic`、`info.analyze` |

- 音频：`__core.media_url({ path: <outDir>/<audio> })` → `<audio controls>`。
- 图片：原生模式同样经 `media_url`；Mock 模式生成内联 SVG 示意图，避免外网图片。
- 支持 `?stid=&setid=&homework_id=&name=&url=&module=` 查询参数；`url` 为 content 包下载地址（来自作业/套卷里的 `url` 与 `base_url` 拼接）。
- “显示答案”开关可隐藏参考答案/解析；未识别题型显示原始 JSON 并标注。

---

## 9. Mock 模式（浏览器预览）

### 9.1 打开方式

```powershell
pnpm run build
pnpm run preview
# 打开 http://localhost:4173/#/login?autologin=1
```

- 自动登录演示账号；也可在登录页输入**任意合法手机号 + ≥4 位密码**，或点“一键体验”。
- 登录页提示 `MOCK PREVIEW · 数据均为内置示例`；所有页面顶部有黄色 Mock 提示条。
- Mock 数据全部为虚构（演示同学、上海市演示中学、假学习卡/作业/错题），不含真实账号或凭据。

### 9.2 Mock 覆盖范围

| 插件/能力 | Mock 行为 |
|---|---|
| `EtsHelper.aes_ecb_encrypt/decrypt` | XOR + base64 的占位“加密”（仅保证链路形态） |
| `EtsHelper.encode_api_body_v2/_v1` | 返回 32 位确定性假签名（`pid=pcWin` / `grlx`） |
| `HttpHelper.request` | 按 URL 路由返回内置响应：登录、用户、作业、错题、学习卡、栏目、套卷、单元、模块、教材、年级、配置、公告、系统时间等 |
| `HttpHelper.download` | 返回成功与 cache 路径 |
| `SevenZip.unzip` | 返回成功与文件数 |
| `FileHelper.readfile` | 按 `<stid>` 返回内置 `content.json`（read/dialogue/picture 三类） |
| `FileHelper.*` 其他 | 存在/创建/删除/写/MD5 等成功桩 |
| `ShellHelper.getpcinfo/getuniqueid/getconfig` | 固定演示设备、设备码、`suspensionBallPort:40001` |
| `ShellHelper.getvolume/setvolume/checkadapter` | 80 / 成功 / 网卡正常 |
| `__core.info` | 演示目录与版本 |
| `__core.media_url` | 现场合成 1.2s 提示音 WAV（Blob URL），不依赖外网 |
| `__core.log/open_external` | 成功桩 |
| `SQLitePln` / `SysConfig` / `appcontroller` | 最小成功桩 |
| 未覆盖 action | `{"code":-2,"msg":"mock: not implemented (...)"}` |

### 9.3 演示数据量

- 3 张学习卡（六/七/八年级示例）、6 份作业（待完成 2 / 已完成 2 / 已过期 2）、8 套套卷、9 个单元 × 5 个模块、5 条错题、3 类 content 示例。
- 无广告、无公告（与真实接口空数据形态一致）。

---

## 10. mq_server（Node 24 + ws）

### 10.1 启动

```powershell
cd D:\ets-rea\native-replica\mq_server
npm install            # 安装 ws
node main.js           # 或 npm start
```

> `build.ps1` 会把 `main.js/package.json` 复制到 `bin/mq_server`，并在目标目录 `npm install`；壳从 exe 目录启动 `node mq_server/main.js` 即可。

### 10.2 行为（与 CONTRACT §8 / 原作一致）

| 项 | 实现 |
|---|---|
| 端口 | 从 `40001` 起监听 `127.0.0.1`；`EADDRINUSE` 时端口 +1 重试，直到成功（上限 65535） |
| 端口注册 | 最终端口写入 `mq_server/app.json`：`{"suspensionBallPort":40001}` |
| 日志 | `../logs/ets_<年>-<月>-<日>.log`（月/日不补零；按进程启动日命名）；格式 `[YYYY-MM-DD HH:mm:ss.SSS] [INFO] mq_server - <message>` |
| 连接 | `connection` 后立即下行 `hello mq_server!` |
| 消息 | 收到的文本原样写日志，并广播给所有客户端（含发送者）；`readyState` 非 OPEN 跳过 |
| 生命周期 | `SIGINT/SIGTERM` 优雅关闭；连接关闭/错误写日志 |
| 日志目录 | 与原生壳 `logs/` 同级（`mq_server/..`）；复制到 `bin/mq_server` 后即 `bin/logs` |

> 与原作差异：原作监听 `0.0.0.0`，本复刻绑定 `127.0.0.1`（仅本机壳访问，减少防火墙暴露）；消息/广播/落盘/端口语义保持一致。

### 10.3 验证记录

```text
mq_server running! port is 40001
update port to 40001
write_app_config_success {"suspensionBallPort":40001}

客户端连接 -> 收到 "hello mq_server!"
客户端发送 -> 收到广播回显
日志: [INFO] mq_server - received: [I] [MISC] mq_server self-test ...
端口占用测试: 第二个实例 -> port is 40002, app.json -> 40002
```

最终状态已恢复为 `app.json {"suspensionBallPort":40001}`；验证产生的日志已清理，测试脚本与截图均未提交。

---

## 11. 验证记录（本次实际执行）

| 验证 | 命令/方式 | 结果 |
|---|---|---|
| 依赖安装 | `pnpm install --store-dir C:\rea_tools\pnpm-store` | 成功；esbuild postinstall Done |
| 生产构建 | `pnpm run build` | 成功；生成 `dist/index.html` + `dist/assets/*`；无 CSS 警告（已移除全局 CSS 中的 `:deep()`） |
| Mock 首页 | Chrome headless CDP，`#/login?autologin=1` | 跳转 `#/home`，标题“首页 · E听说”，三卡/模块卡/学习卡均渲染 |
| 全路由巡检 | `#/home`、`#/homework`、`#/homework/111203417`、`#/sets`、`#/courses`、3 个 `#/practice`（read/dialogue/picture）、`#/mistakes`、`#/settings`、`#/about` | 11 条路由均渲染，0 异常、0 console error、无 `.el-alert--error` |
| 练习页音频 | `#/practice?stid=900101` / `900104` | `<audio>` 存在并可播放（Mock 提示音） |
| 练习页图片 | `#/practice?stid=900105` | 内联 SVG 示意图正常显示 |
| mq_server 启动 | `node main.js` | 40001，app.json/日志生成 |
| mq_server 回显 | ws 客户端连接/发送 | 收到 hello + 广播回显 |
| mq_server 端口回退 | 第二个实例 | 自动使用 40002 |

> 所有截图仅保存在本机临时目录用于验收，未写入仓库。

---

## 12. 未实现 / 明确降级项

以下能力**未实现或为桩**，已在 UI 中标注或返回 `{"code":-2,"msg":"not implemented"}`：

1. **录音与评测**：`soundhelper.record`、波形/录音回调、双通道 ISE WebSocket、AI 评测、OSS/SLS 上传、`/m/audio/sync-v2` 评分回写均未实现。练习页只展示题干/答案/解析与示范音频。
2. **真实 content 包 URL**：`g/homework/list` / `g/set/list` 的真实响应中 `url` 与 `base_url` 的拼装规则未完全验证；拿不到 URL 时练习页会提示错误并支持载入内置示例。
3. **账号生命周期**：短信验证码 `code/send`、注册、改密、绑定手机、极验验证码、教育系统单点登录未实现。
4. **页面**：音标、单词 PK、推荐配音、学习计划、模考、E 卡商城、成长路径、消息中心等未实现；首页以“未实现”标签展示部分入口。
5. **日志/埋点**：仅通过 `__core.log` 交给壳/mq_server；阿里云 SLS、TalkingData、`log_collector` 未接入。
6. **窗口/系统能力**：`appcontroller` 窗口控制、`FileHelper` 对话框/遍历/重命名、`HttpHelper.upload/downloadresource/downloadsdk`、`SevenZip.zip/test`、`SQLitePln` 业务表、`ShellHelper` 进程/授权码/剪贴板等为桩或未接线。
7. **清理缓存 / 检查更新 / 麦克风检测**：设置页按钮为禁用或提示未实现。
8. **分页/筛选**：作业与套卷按“一次拉取 100/50 条 + 前端筛选/分页”实现，未做服务端分页联动；真实接口的分页字段可能不同。
9. **响应签名**：`sign_response:1` 已发送，但未校验/解析响应签名（`encode_api_resp_v2` 未接入）。

---

## 13. 已知限制与安全说明

- **接口参数为最小对等集**：部分业务参数（`class_id`、`book_id`、`parent_account_id`、`keywork` 等）未逐一验证；若真实接口返回参数错误，需按抓包补齐。
- **token 存 localStorage**：与前端原作一致；退出登录会清除。请求日志中 token 已脱敏为 `***`。
- **不硬编码凭据**：仓库中无真实账号/密码/密钥；登录凭据只来自用户输入，经 `EtsHelper` 加密后提交。
- **Mock 数据为虚构**：姓名、学校、手机号、学习卡、成绩均为演示数据，不对应真实用户。
- **Element Plus 全量引入**：包体偏大，但离线可用；如需优化可改为 unplugin 自动导入。
- **hash 路由**：URL 形如 `#/home`；与壳内虚拟主机/静态服务的兼容性最好。
- **Vite 8 + Rolldown**：构建产物 chunk 划分与 Vite 7 不同（`bridge`/`message` 独立 chunk），已做运行验证。
- **`file://` 限制**：请通过 HTTP 静态服务或壳内虚拟主机打开 dist；`file://` 下 ES Module 会被浏览器拦截。

---

## 14. 快速排错

| 现象 | 处理 |
|---|---|
| `vite: not recognized` / node_modules 不完整 | 删掉 `frontend/node_modules`，重新 `pnpm install --store-dir C:\rea_tools\pnpm-store` |
| `ERR_PNPM_IGNORED_BUILDS` | `pnpm approve-builds --all` 后重新 install（`pnpm-workspace.yaml` 已声明 esbuild） |
| `pnpm run build` 触发重装并报 `.pnpm` 拒绝访问 | 关闭占用 `node_modules` 的进程（vite preview / 浏览器 / 杀软扫描），再删除并重装 |
| 浏览器打开空白 | 确认通过 http（`pnpm run preview` / 静态服务）访问；直接双击 `index.html` 会因 module CORS 失败 |
| 页面显示 Mock 横幅 | 说明当前不在 WebView2 壳内；壳内运行会自动走原生桥 |
| mq_server 端口不是 40001 | 检查 `mq_server/app.json`；40001 被占用时会自动 +1，属预期 |
| 练习页报“缺少 content 包下载地址” | 从作业/套卷进入时会带 `url`；直接访问 `#/practice?stid=` 仅 Mock 下可用，可点“载入内置示例” |

---

*文档生成：2026-11-07；对应前端构建 Vite 8.3.6 + mq_server Node 24。*
