// Live CDP dump for ETS (CEF 91 / CDP 1.3)
// usage: node dump_cdp.js <outDir> [reload]
const WebSocket = require('ETS/mq_server/node_modules/ws');
const http = require('http');
const fs = require('fs');
const path = require('path');

const OUT = process.argv[2] || 'runtime';
const DO_RELOAD = process.argv[3] !== 'noreload';
const PORT = 10086;
fs.mkdirSync(OUT, { recursive: true });
fs.mkdirSync(path.join(OUT, 'scripts'), { recursive: true });
fs.mkdirSync(path.join(OUT, 'net'), { recursive: true });

function getJson(url) {
  return new Promise((res, rej) => {
    http.get(url, (r) => {
      let d = '';
      r.on('data', (c) => (d += c));
      r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } });
    }).on('error', rej);
  });
}

(async () => {
  const list = await getJson(`http://127.0.0.1:${PORT}/json/list`);
  const page = list.find((t) => t.type === 'page' && /ets-student-pc-web/.test(t.url)) || list.find((t) => t.type === 'page');
  if (!page) throw new Error('no page target');
  console.error('target:', page.url);
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false, maxPayload: 512 * 1024 * 1024 });
  let id = 0;
  const pending = new Map();
  const events = [];
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  ws.on('message', (raw) => {
    let m; try { m = JSON.parse(raw.toString()); } catch { return; }
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      if (m.error) p.rej(new Error(m.method + ' ' + JSON.stringify(m.error))); else p.res(m.result);
      return;
    }
    if (m.method) events.push(m);
  });
  await new Promise((r) => ws.on('open', r));

  await send('Network.enable', { maxTotalBufferSize: 200 * 1024 * 1024, maxResourceBufferSize: 50 * 1024 * 1024 });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Debugger.enable');

  const before = events.length;
  if (DO_RELOAD) {
    await send('Page.reload', { ignoreCache: false });
  }
  // wait for load + settle
  await new Promise((r) => setTimeout(r, DO_RELOAD ? 18000 : 4000));

  const evs = events.slice(before);
  const scriptParsed = evs.filter((e) => e.method === 'Debugger.scriptParsed').map((e) => e.params);
  const reqs = new Map();
  const responses = [];
  for (const e of evs) {
    if (e.method === 'Network.requestWillBeSent') reqs.set(e.params.requestId, e.params);
    else if (e.method === 'Network.responseReceived') {
      responses.push({ requestId: e.params.requestId, url: e.params.response.url, mime: e.params.response.mimeType, status: e.params.response.status, type: e.params.type });
    }
  }
  console.error('scripts:', scriptParsed.length, 'responses:', responses.length);

  // dump script sources
  const seen = new Set();
  const manifest = [];
  for (const sp of scriptParsed) {
    const u = sp.url || ('inline:' + sp.scriptId);
    if (seen.has(u) || !u) continue;
    seen.add(u);
    if (!/ets100|\.js|chunk|assets|\.css/i.test(u) && u.startsWith('inline:')) {
      // keep inline scripts too
    }
    try {
      const src = await send('Debugger.getScriptSource', { scriptId: sp.scriptId });
      const name = (u.replace(/^https?:\/\//, '').replace(/[^\w.\-]+/g, '_').slice(0, 180) || ('inline_' + sp.scriptId)) + '.js';
      fs.writeFileSync(path.join(OUT, 'scripts', name), src.scriptSource || '', 'utf8');
      manifest.push({ url: u, file: name, bytes: (src.scriptSource || '').length, length: sp.length || null });
    } catch (e) { manifest.push({ url: u, error: String(e).slice(0, 200) }); }
  }
  fs.writeFileSync(path.join(OUT, 'scripts_manifest.json'), JSON.stringify(manifest, null, 1), 'utf8');

  // dump network bodies (json/text/xhr/js/css)
  const netManifest = [];
  for (const r of responses) {
    if (!/json|javascript|css|text|plain|x-www-form-urlencoded/i.test(r.mime || '') && !['XHR', 'Fetch'].includes(r.type)) continue;
    try {
      const b = await send('Network.getResponseBody', { requestId: r.requestId });
      const ext = /json/i.test(r.mime) ? '.json' : /css/i.test(r.mime) ? '.css' : '.txt';
      const name = (r.url.replace(/^https?:\/\//, '').replace(/[^\w.\-]+/g, '_').slice(0, 170) || r.requestId) + ext;
      fs.writeFileSync(path.join(OUT, 'net', name), b.body, b.base64Encoded ? 'base64' : 'utf8');
      netManifest.push({ url: r.url, mime: r.mime, status: r.status, file: name, bytes: b.body.length, base64: b.base64Encoded });
    } catch (e) { netManifest.push({ url: r.url, error: String(e).slice(0, 160) }); }
  }
  fs.writeFileSync(path.join(OUT, 'net_manifest.json'), JSON.stringify(netManifest, null, 1), 'utf8');

  // evaluate page state
  const evals = {
    href: 'location.href',
    ua: 'navigator.userAgent',
    lsKeys: 'JSON.stringify(Object.keys(localStorage))',
    lsOrigin: 'JSON.stringify(localStorage)',
    ssKeys: 'JSON.stringify(Object.keys(sessionStorage))',
    ssOrigin: 'JSON.stringify(sessionStorage)',
    resources: 'JSON.stringify(performance.getEntriesByType("resource").map(e=>e.name))',
    cefBridge: 'typeof cef!=="undefined"?Object.keys(cef.message):"none"',
    scriptsInline: 'document.scripts.length',
  };
  const state = {};
  for (const [k, expr] of Object.entries(evals)) {
    try {
      const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: false });
      state[k] = r.result && r.result.value !== undefined ? r.result.value : r;
    } catch (e) { state[k] = 'ERR ' + String(e).slice(0, 120); }
  }
  fs.writeFileSync(path.join(OUT, 'page_state.json'), JSON.stringify(state, null, 1), 'utf8');

  // DOM + screenshot
  try { const d = await send('Runtime.evaluate', { expression: 'document.documentElement.outerHTML', returnByValue: true }); fs.writeFileSync(path.join(OUT, 'dom.html'), d.result.value || '', 'utf8'); } catch (e) {}
  try { const s = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(path.join(OUT, 'screenshot.png'), Buffer.from(s.data, 'base64')); } catch (e) {}

  console.error('DONE scripts=' + manifest.length + ' net=' + netManifest.length);
  ws.close();
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
