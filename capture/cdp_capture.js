#!/usr/bin/env node
/**
 * ETS 练习抓包 · CDP 采集器
 * ---------------------------------------------------------------------------
 * 连接官方客户端的 CEF 远程调试端口（默认 10086），采集：
 *   - 渲染进程发起的网络请求 / 响应体（静态资源、前端 fetch、WebSocket 握手）
 *   - WebSocket 帧（ISE 评测、长连接等）——payload 原样保存，二进制帧落盘
 *   - console / 异常
 *
 * 原生 HttpHelper（WinHTTP）发出的 API 请求不在渲染进程，由 native_capture.py 采集。
 *
 * 用法：node cdp_capture.js <输出目录> [cdp端点]
 *   cdp端点默认 http://127.0.0.1:10086
 */
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');

function requireWs() {
  const candidates = [
    'ws',
    'D:/ets-rea/ETS/mq_server/node_modules/ws',
    path.join(process.cwd(), 'node_modules', 'ws')
  ];
  for (const c of candidates) {
    try { return require(c); } catch (e) { /* next */ }
  }
  throw new Error('需要 ws 模块：npm i ws，或使用官方客户端自带的 ETS/mq_server/node_modules/ws');
}

const WebSocket = requireWs();
const OUT = process.argv[2] || path.join(__dirname, 'runs', String(Date.now()));
const CDP = (process.argv[3] || 'http://127.0.0.1:10086').replace(/\/$/, '');
fs.mkdirSync(OUT, { recursive: true });
const FILES = path.join(OUT, 'files');
fs.mkdirSync(FILES, { recursive: true });

const httpFd = fs.openSync(path.join(OUT, 'renderer_http.jsonl'), 'a');
const wsFd = fs.openSync(path.join(OUT, 'ws.jsonl'), 'a');
const consoleFd = fs.openSync(path.join(OUT, 'console.jsonl'), 'a');
let seq = 0;
const blob = (kind, b64, ext) => {
  const name = `files/cdp_${String(++seq).padStart(5, '0')}_${kind}${ext || '.bin'}`;
  fs.writeFileSync(path.join(OUT, name), Buffer.from(b64, 'base64'));
  return name;
};
function line(fd, obj) {
  fs.writeSync(fd, JSON.stringify({ t: new Date().toISOString(), ...obj }) + '\n');
}
function safeJson(s, n) {
  try { return JSON.stringify(JSON.parse(s)).slice(0, n || 2000); } catch (e) { return String(s).slice(0, n || 2000); }
}

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, r => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}
async function waitForPage(timeoutMs = 30000) {
  const t0 = Date.now();
  let lastErr = '';
  while (Date.now() - t0 < timeoutMs) {
    try {
      const list = await getJson(CDP + '/json/list');
      const pages = list.filter(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (pages.length) {
        // 优先 SPA 页面
        return pages.find(p => /statics\.ets100\.com|ets100|index\.html/.test(p.url || '')) || pages[0];
      }
    } catch (e) { lastErr = e.message; }
    await new Promise(r => setTimeout(r, 500));
  }
  throw new Error('找不到可调试页面（CDP ' + CDP + '）：' + lastErr + '\n请确认官方客户端已启动且 --remote-debugging-port=10086 生效');
}

(async () => {
  const page = await waitForPage();
  console.log('[cdp] 目标页面:', page.url);
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false, maxPayload: 128 * 1024 * 1024 });
  let id = 0;
  const pending = new Map();
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const i = ++id;
    pending.set(i, { resolve, reject });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  const requests = new Map();
  ws.on('message', raw => {
    let m;
    try { m = JSON.parse(raw.toString()); } catch (e) { return; }
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
      return;
    }
    handleEvent(m).catch(() => {});
  });

  async function handleEvent(m) {
    const p = m.params || {};
    switch (m.method) {
      case 'Network.requestWillBeSent': {
        requests.set(p.requestId, { url: p.request.url, method: p.request.method });
        line(httpFd, {
          kind: 'request', id: p.requestId,
          url: p.request.url, method: p.request.method,
          headers: p.request.headers, postData: p.request.postData || ''
        });
        break;
      }
      case 'Network.responseReceived': {
        const req = requests.get(p.requestId) || {};
        line(httpFd, {
          kind: 'response_meta', id: p.requestId, url: (p.response && p.response.url) || req.url,
          status: p.response && p.response.status, mime: p.response && p.response.mimeType
        });
        break;
      }
      case 'Network.loadingFailed': {
        line(httpFd, { kind: 'failed', id: p.requestId, error: p.errorText, blocked: p.blockedReason });
        break;
      }
      case 'Network.loadingFinished': {
        const req = requests.get(p.requestId) || {};
        if (!req.url || !/^(http|https):/.test(req.url)) break;
        // 只取文本类且不太大的响应体
        try {
          const body = await send('Network.getResponseBody', { requestId: p.requestId });
          if (body && body.body) {
            const isB64 = !!body.base64Encoded;
            let saved = '';
            if (isB64) saved = blob('resp', body.body, '.bin');
            line(httpFd, {
              kind: 'response_body', id: p.requestId, url: req.url, status: req.status,
              base64: isB64, body: isB64 ? undefined : String(body.body).slice(0, 200000), file: saved || undefined
            });
          }
        } catch (e) { /* body 不可用（预检/缓存等） */ }
        break;
      }
      case 'Network.webSocketCreated':
        line(wsFd, { kind: 'created', id: p.requestId, url: p.url, initiator: p.initiator && p.initiator.type });
        break;
      case 'Network.webSocketHandshakeResponseReceived':
        line(wsFd, { kind: 'handshake', id: p.requestId, status: p.response && p.response.status, headers: p.response && p.response.headers });
        break;
      case 'Network.webSocketFrameSent':
      case 'Network.webSocketFrameReceived': {
        const f = p.response || {};
        const rec = { kind: m.method.endsWith('Sent') ? 'send' : 'recv', id: p.requestId, opcode: f.opcode, size: (f.payloadData || '').length };
        if (f.opcode === 1) { rec.text = String(f.payloadData || '').slice(0, 5000); rec.textLen = (f.payloadData || '').length; }
        else if (f.opcode === 2) rec.file = blob('ws', Buffer.from(f.payloadData || '', 'base64').toString('base64'), '.bin');
        line(wsFd, rec);
        break;
      }
      case 'Network.webSocketClosed':
        line(wsFd, { kind: 'closed', id: p.requestId });
        break;
      case 'Runtime.consoleAPICalled': {
        const args = (p.args || []).map(a => a.value !== undefined ? a.value : (a.description || a.type));
        line(consoleFd, { kind: 'console', type: p.type, args });
        break;
      }
      case 'Runtime.exceptionThrown':
        line(consoleFd, { kind: 'exception', detail: p.exceptionDetails && p.exceptionDetails.text, url: p.exceptionDetails && p.exceptionDetails.url });
        break;
      default:
        break;
    }
  }

  await new Promise((resolve, reject) => { ws.on('open', resolve); ws.on('error', reject); });
  await send('Network.enable', { maxTotalBufferSize: 512 * 1024 * 1024, maxResourceBufferSize: 64 * 1024 * 1024, maxPostDataSize: 8 * 1024 * 1024 });
  await send('Runtime.enable');
  console.log('[cdp] 采集已开始（Ctrl+C 停止）');

  const stop = () => {
    try { ws.close(); } catch (e) {}
    for (const fd of [httpFd, wsFd, consoleFd]) { try { fs.closeSync(fd); } catch (e) {} }
    fs.writeFileSync(path.join(OUT, 'cdp_done.txt'), new Date().toISOString());
    console.log('[cdp] 已停止，输出:', OUT);
    process.exit(0);
  };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
})().catch(e => { console.error('[cdp] 失败:', e.message); process.exit(1); });
