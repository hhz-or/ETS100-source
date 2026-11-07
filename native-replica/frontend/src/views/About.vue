<template>
  <div class="page">
    <section class="about-hero">
      <div class="big-logo">E</div>
      <h2>E听说 · 原生复刻版</h2>
      <p>Vue3 + Vite + Pinia + Vue Router + Element Plus · WebView2 壳 · 7 插件 DLL · Node mq_server</p>
      <div style="margin-top: 14px; display: flex; gap: 8px; justify-content: center; flex-wrap: wrap">
        <el-tag effect="dark" style="background: rgba(255,255,255,.18); border-color: transparent">v5.7.9 对齐</el-tag>
        <el-tag effect="dark" style="background: rgba(255,255,255,.18); border-color: transparent">{{ isMock ? 'Mock 模式' : 'Native 模式' }}</el-tag>
      </div>
    </section>

    <div class="quick-grid">
      <div class="metric-card" style="cursor: default">
        <div class="metric-head"><div class="metric-icon">🧩</div></div>
        <div class="metric-value" style="font-size: 18px">10 个页面</div>
        <div class="metric-label">登录 / 首页 / 作业 / 详情 / 套卷 / 课程 / 练习 / 错题 / 设置 / 关于</div>
      </div>
      <div class="metric-card" style="cursor: default">
        <div class="metric-head"><div class="metric-icon teal">🔌</div></div>
        <div class="metric-value" style="font-size: 18px">8 个插件通道</div>
        <div class="metric-label">EtsHelper / FileHelper / HttpHelper / SevenZip / SQLitePln / ShellHelper / SysConfig / __core</div>
      </div>
      <div class="metric-card" style="cursor: default">
        <div class="metric-head"><div class="metric-icon orange">🧪</div></div>
        <div class="metric-value" style="font-size: 18px">{{ isMock ? '内置演示数据' : '真实桥调用' }}</div>
        <div class="metric-label">浏览器打开 dist 自动启用 mock，壳内运行自动切原生</div>
      </div>
    </div>

    <div class="settings-grid">
      <div style="display: flex; flex-direction: column; gap: 16px">
        <section class="panel">
          <div class="panel-title"><h3>技术栈</h3></div>
          <div class="tech-tags">
            <span v-for="t in tech" :key="t" class="tech-tag">{{ t }}</span>
          </div>
          <p class="small muted" style="margin: 14px 0 0; line-height: 1.8">
            构建命令：<code>pnpm install --store-dir C:\rea_tools\pnpm-store</code> 然后
            <code>pnpm run build</code>，产物在 <code>frontend/dist</code>，由 build.ps1 复制到
            <code>assets/web</code>。不依赖外网 CDN，Element Plus 样式随包打包。
          </p>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>页面与接口映射</h3></div>
          <el-table :data="pageRows" size="small" style="width: 100%">
            <el-table-column prop="page" label="页面" width="150" />
            <el-table-column prop="route" label="路由" width="190" />
            <el-table-column prop="api" label="主要接口" />
          </el-table>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>未实现 / 明确降级项</h3></div>
          <ul class="step-list">
            <li v-for="(item, i) in unimplemented" :key="i">
              <span class="step-dot skip">–</span>
              <div class="step-body"><strong>{{ item }}</strong></div>
            </li>
          </ul>
        </section>
      </div>

      <div style="display: flex; flex-direction: column; gap: 16px">
        <section class="panel">
          <div class="panel-title"><h3>桥接说明</h3></div>
          <div class="kv"><span>桥对象</span><b class="mono" style="font-size: 11px">window.cef.message</b></div>
          <div class="kv"><span>调用方式</span><b class="mono" style="font-size: 11px">sendMessage(uid, plugin, action, args)</b></div>
          <div class="kv"><span>回调</span><b class="mono" style="font-size: 11px">{type:"callback", uid, data}</b></div>
          <div class="kv"><span>当前通道</span><b>{{ isMock ? 'mockInvoke' : 'cef.message' }}</b></div>
          <p class="small muted" style="margin: 12px 0 0; line-height: 1.8">
            所有插件调用统一走 <code>src/bridge.js</code> 的 <code>invoke()</code> Promise 封装（默认 30s 超时），
            data 为 JSON 字符串，<code>invokeJson()</code> 负责解析。
          </p>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>目录与文档</h3></div>
          <div class="kv"><span>前端源码</span><b class="mono" style="font-size: 11px">native-replica/frontend</b></div>
          <div class="kv"><span>构建产物</span><b class="mono" style="font-size: 11px">frontend/dist</b></div>
          <div class="kv"><span>接口契约</span><b class="mono" style="font-size: 11px">native-replica/CONTRACT.md</b></div>
          <div class="kv"><span>构建说明</span><b class="mono" style="font-size: 11px">native-replica/docs/frontend_build.md</b></div>
          <div class="kv"><span>MQ 日志</span><b class="mono" style="font-size: 11px">logs/ets_YYYY-M-D.log</b></div>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>免责声明</h3></div>
          <p class="small muted" style="margin: 0; line-height: 1.9">
            本项目仅用于架构学习与前端技术复刻研究，与官方 E听说无任何关联。
            不包含真实账号凭据；登录凭据由用户输入，仅用于本地加密后提交。
            题目 / 音频均为内置示例或用户本地资源。
          </p>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { isMock } from '../bridge'

const tech = [
  'Vue 3 <script setup>',
  'Vite 7',
  'Pinia 3',
  'Vue Router 4',
  'Element Plus 2',
  'WebView2',
  'C++20',
  'Node 24 + ws'
]

const pageRows = [
  { page: '登录', route: '/login', api: 'EtsHelper.aes_ecb_encrypt → encode_api_body_v2 → HttpHelper.request user/login' },
  { page: '首页', route: '/home', api: 'g/homework/list、m/mistake/summary、m/ecard/list、m/advertisement/list' },
  { page: '作业', route: '/homework', api: 'g/homework/list' },
  { page: '作业详情', route: '/homework/:id', api: 'm/homework/info' },
  { page: '套卷', route: '/sets', api: 'g/set/column-v2、g/set/list' },
  { page: '同步课程', route: '/courses', api: 'g/resource/grade-list、g/resource/book-list、g/set/unit-list、g/set/unit-info、g/set/module-list' },
  { page: '练习', route: '/practice?stid=', api: 'HttpHelper.download → SevenZip.unzip → FileHelper.readfile(content.json) → __core.media_url' },
  { page: '错题本', route: '/mistakes', api: 'm/mistake/summary、m/mistake/list' },
  { page: '设置', route: '/settings', api: 'ShellHelper.getpcinfo/getuniqueid/getvolume/setvolume/getconfig、__core.info' },
  { page: '关于', route: '/about', api: '—' }
]

const unimplemented = [
  '录音 / 评测：soundhelper.record + 双通道 ISE WebSocket + OSS 上传 + /m/audio/sync-v2 未实现，练习页仅展示题干/答案/解析与示范音频。',
  '套卷 / 课程模块的“真实题目”依赖 content 包 URL；未从接口拿到 URL 时练习页会提示并支持载入内置示例。',
  '音标、单词 PK、推荐配音、学习计划、模考、E 卡商城等页面未实现，首页以“未实现”标签标注。',
  '登录验证码、极验、短信 code/send、注册/改密等账号生命周期接口未实现。',
  '日志上报仅经 __core.log 转给 mq_server；阿里云 SLS / TalkingData / log_collector 未接入。',
  '清理缓存、检查更新、麦克风检测、窗口控制（appcontroller）为桩或降级处理。'
]
</script>
