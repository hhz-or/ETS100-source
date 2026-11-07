// restore system volume to 70 (undo side effect of probe)
const WebSocket = require('ETS/mq_server/node_modules/ws');
const http = require('http');
function getJson(u){return new Promise((res,rej)=>{http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})}).on('error',rej)})}
(async()=>{
  const l=await getJson('http://127.0.0.1:10086/json/list');
  const pg=l.find(t=>t.type==='page');
  const ws=new WebSocket(pg.webSocketDebuggerUrl,{perMessageDeflate:false});let id=0;const p=new Map();
  const send=(m,pr={})=>new Promise((res,rej)=>{const i=++id;p.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:pr}))});
  ws.on('message',raw=>{let m;try{m=JSON.parse(raw.toString())}catch{return}if(m.id&&p.has(m.id)){const q=p.get(m.id);p.delete(m.id);m.error?q.rej(new Error(JSON.stringify(m.error))):q.res(m.result)}});
  await new Promise(r=>ws.on('open',r));
  await send('Runtime.enable');
  const expr = [
    '(async()=>{',
    'const call=(a,args)=>new Promise(res=>{',
    'const uid=cef.message.createGuid()+"@r";let d=false;',
    'const t=setTimeout(()=>{if(!d){d=true;res("[T]")}},1500);',
    'cef.message.setMessageCallback(uid,x=>{if(!d){d=true;clearTimeout(t);cef.message.removeMessageCallback(uid);res(x)}});',
    'cef.message.sendMessage(uid,"ShellHelper",a,args)});',
    'return JSON.stringify({before:await call("getvolume","{}"),set:await call("setvolume",JSON.stringify({volume:70})),after:await call("getvolume","{}")})',
    '})()'
  ].join('');
  const r=await send('Runtime.evaluate',{expression:expr,awaitPromise:true,returnByValue:true});
  console.log(r.result.value);
  ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
