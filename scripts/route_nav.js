// Navigate live ETS SPA through routes via CDP, dump newly loaded chunks
const WebSocket = require('ETS/mq_server/node_modules/ws');
const http = require('http');
const fs = require('fs');
const path = require('path');

const OUT = 'runtime';
const PORT = 10086;
const ROUTES = JSON.parse(fs.readFileSync('data/frontend/routes.json', 'utf8'));
const routes = [...new Set(ROUTES.routes.map(r => r.full_path).filter(p => p && p.startsWith('/')))]
  .filter(p => !p.includes(':'));   // skip dynamic params (would 404)
fs.mkdirSync(path.join(OUT, 'scripts_routes'), { recursive: true });

function getJson(url) { return new Promise((res, rej) => { http.get(url, r => { let d=''; r.on('data',c=>d+=c); r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}}); }).on('error', rej); }); }

(async () => {
  const list = await getJson(`http://127.0.0.1:${PORT}/json/list`);
  const page = list.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false, maxPayload: 512*1024*1024 });
  let id = 0; const pending = new Map(); const events = [];
  const send = (method, params={}) => new Promise((res, rej) => { const i=++id; pending.set(i,{res,rej}); ws.send(JSON.stringify({id:i,method,params})); });
  ws.on('message', raw => { let m; try{m=JSON.parse(raw.toString())}catch{return}
    if (m.id && pending.has(m.id)) { const p=pending.get(m.id); pending.delete(m.id); m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result); return; }
    if (m.method) events.push(m); });
  await new Promise(r => ws.on('open', r));
  await send('Debugger.enable'); await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');

  const seen = new Set();
  const manifest = [];
  const orig = (await send('Runtime.evaluate', { expression: 'location.hash', returnByValue: true })).result.value;
  console.error('orig hash:', orig, 'routes:', routes.length);

  let cursor = events.length;
  for (const rp of routes) {
    try {
      await send('Runtime.evaluate', { expression: `location.hash = ${JSON.stringify('#' + rp)}`, returnByValue: true });
    } catch (e) { continue; }
    await new Promise(r => setTimeout(r, 1400));
    const fresh = events.slice(cursor); cursor = events.length;
    const parsed = fresh.filter(e => e.method === 'Debugger.scriptParsed').map(e => e.params);
    // also pick up any scriptParsed events globally missed
    for (const sp of parsed) {
      const u = sp.url || '';
      if (!u || seen.has(u)) continue;
      seen.add(u);
      if (!/statics\.ets100\.com|\.js/i.test(u)) continue;
      try {
        const src = await send('Debugger.getScriptSource', { scriptId: sp.scriptId });
        const name = u.replace(/^https?:\/\//, '').replace(/[^\w.\-]+/g, '_').slice(0, 180) + '.js';
        fs.writeFileSync(path.join(OUT, 'scripts_routes', name), src.scriptSource || '', 'utf8');
        manifest.push({ route: rp, url: u, file: name, bytes: (src.scriptSource||'').length });
      } catch (e) { manifest.push({ route: rp, url: u, error: String(e).slice(0,120) }); }
    }
    if (parsed.length) console.error(rp, 'new scripts:', parsed.filter(p=>p.url&&!seen.has(p.url)).length);
  }
  // restore
  try { await send('Runtime.evaluate', { expression: `location.hash = ${JSON.stringify(orig)}` }); } catch (e) {}
  fs.writeFileSync(path.join(OUT, 'routes_manifest.json'), JSON.stringify(manifest, null, 1), 'utf8');
  console.error('DONE new chunks:', manifest.length);
  ws.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
