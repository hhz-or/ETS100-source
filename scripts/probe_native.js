// Runtime oracle: call native plugin actions from the live page via cef.message
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
  const send = (method, params={}) => new Promise((res, rej) => { const i=++id; pending.set(i,{res,rej}); ws.send(JSON.stringify({id:i,method,params})); });
  ws.on('message', raw => { let m; try{m=JSON.parse(raw.toString())}catch{return} if (m.id && pending.has(m.id)) { const p=pending.get(m.id); pending.delete(m.id); m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result); } });
  await new Promise(r => ws.on('open', r));
  await send('Runtime.enable');

  const bodyB64 = Buffer.from('[{"r":"system/time","params":{"sn":"test"}}]').toString('base64');
  const t = String(Date.now());
  const probes = [
    ["EtsHelper", "encode_api_body_v2", JSON.stringify({ body: bodyB64, time: t })],
    ["EtsHelper", "encode_api_body", JSON.stringify({ body: bodyB64, time: t })],
    ["EtsHelper", "encode_api_resp_v2", JSON.stringify({ response: "W10=", time: t })],
    ["EtsHelper", "encode_api_resp_v2", JSON.stringify({ body: "W10=", time: t })],
    ["EtsHelper", "encode_api_resp", JSON.stringify({ response: "W10=", time: t })],
    ["ShellHelper", "getpcinfo", ""],
    ["ShellHelper", "getvolume", ""],
    ["ShellHelper", "getconfig", ""],
    ["ShellHelper", "getuniqueid", ""],
    ["ShellHelper", "checkadapter", ""],
    ["ShellHelper", "gettoken", "{}"],
    ["EtsHelper", "get_appdata_path", ""],
    ["FileHelper", "existfileorfolder", JSON.stringify({ path: "C:\\Windows\\win.ini" })],
    ["FileHelper", "getmd5", JSON.stringify({ path: "C:\\Windows\\win.ini" })],
    ["HttpHelper", "isrpkexist", JSON.stringify({})],
    ["SysConfig", "init", JSON.stringify({})],
  ];
  const js = `(async () => {
    const out = [];
    const call = (plugin, action, args) => new Promise(resolve => {
      let done = false;
      const uid = cef.message.createGuid() + "@probe_" + action;
      const finish = (v) => { if (done) return; done = true; try { cef.message.removeMessageCallback(uid); } catch (e) {} resolve(v); };
      const t = setTimeout(() => finish("[TIMEOUT]"), 2000);
      cef.message.setMessageCallback(uid, function (d) { clearTimeout(t); finish(typeof d === "string" ? d : JSON.stringify(d)); });
      try { cef.message.sendMessage(uid, plugin, action, args || ""); } catch (e) { clearTimeout(t); finish("[THROW] " + e); }
    });
    for (const p of ${JSON.stringify(probes)}) {
      const v = await call(p[0], p[1], p[2]);
      out.push({ plugin: p[0], action: p[1], args: p[2], result: v });
    }
    return JSON.stringify(out);
  })()`;
  const r = await send('Runtime.evaluate', { expression: js, awaitPromise: true, returnByValue: true });
  const val = r.result && r.result.value;
  fs.writeFileSync(OUT + '/native_probe_' + t + '.json', val || JSON.stringify(r), 'utf8');
  console.log(val || JSON.stringify(r));
  ws.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
