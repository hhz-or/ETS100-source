// second runtime probe: arg-schema discovery (read-only actions only)
const WebSocket = require('D:/ets-rea/ETS/mq_server/node_modules/ws');
const http = require('http');
const fs = require('fs');

const OUT = 'D:/ets-rea/work/runtime';
const PORT = 10086;
function getJson(url) { return new Promise((res, rej) => { http.get(url, r => { let d=''; r.on('data',c=>d+=c); r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}}); }).on('error', rej); }); }

(async () => {
  const list = await getJson(`http://127.0.0.1:${PORT}/json/list`);
  const page = list.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false, maxPayload: 64*1024*1024 });
  let id = 0; const pending = new Map();
  const send = (m,p={}) => new Promise((res,rej)=>{const i=++id;pending.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:p}))});
  ws.on('message', raw => { let m; try{m=JSON.parse(raw.toString())}catch{return} if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result)}});
  await new Promise(r => ws.on('open', r));
  await send('Runtime.enable');

  const probes = [
    ["FileHelper", "existfileorfolder", JSON.stringify({ filePath: "C:\\Windows\\win.ini" })],
    ["FileHelper", "existfileorfolder", JSON.stringify({ path: "C:\\Windows\\win.ini" })],
    ["FileHelper", "getmd5", JSON.stringify({ filePath: "C:\\Windows\\win.ini" })],
    ["FileHelper", "getfoledersize", JSON.stringify({ filePath: "C:\\Windows\\System32" })],
    ["FileHelper", "getbase64", JSON.stringify({ filePath: "C:\\Windows\\win.ini" })],
    ["ShellHelper", "getsysytemlocalpath", "{}"],
    ["ShellHelper", "getuniqueid", "{}"],
    ["ShellHelper", "getvolume", "{}"],
    ["ShellHelper", "setvolume", JSON.stringify({ volume: 50 })],
    ["ShellHelper", "getroomid", "{}"],
    ["appcontroller", "get_win_pos", "{}"],
    ["HttpHelper", "monitornetspeed", JSON.stringify({ url: "http://file.fei.ets100.com/network_test" })],
    ["EtsHelper", "get_appdata_path", "{}"],
    ["EtsHelper", "check_update", "{}"],
  ];
  const js = `(async () => {
    const out = [];
    const call = (plugin, action, args) => new Promise(resolve => {
      let done = false;
      const uid = cef.message.createGuid() + "@p2_" + action;
      const finish = v => { if (done) return; done = true; try { cef.message.removeMessageCallback(uid); } catch(e){} resolve(v); };
      const t = setTimeout(() => finish("[TIMEOUT]"), 2500);
      cef.message.setMessageCallback(uid, d => { clearTimeout(t); finish(typeof d === "string" ? d : JSON.stringify(d)); });
      try { cef.message.sendMessage(uid, plugin, action, args || ""); } catch(e) { clearTimeout(t); finish("[THROW] " + e); }
    });
    for (const p of ${JSON.stringify(probes)}) { out.push({ plugin: p[0], action: p[1], args: p[2], result: await call(p[0], p[1], p[2]) }); }
    return JSON.stringify(out);
  })()`;
  const r = await send('Runtime.evaluate', { expression: js, awaitPromise: true, returnByValue: true });
  const val = (r.result && r.result.value) || JSON.stringify(r);
  fs.writeFileSync(OUT + '/native_probe2.json', val, 'utf8');
  console.log(val);
  ws.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
