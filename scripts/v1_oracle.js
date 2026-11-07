// call specific EtsHelper actions with fixed args; print results
const WebSocket = require('ETS/mq_server/node_modules/ws');
const http = require('http');
const fs = require('fs');
function getJson(u){return new Promise((res,rej)=>{http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})}).on('error',rej)})}
(async()=>{
  const l=await getJson('http://127.0.0.1:10086/json/list');
  const pg=l.find(t=>t.type==='page');
  const ws=new WebSocket(pg.webSocketDebuggerUrl,{perMessageDeflate:false,maxPayload:64*1024*1024});
  let id=0;const p=new Map();
  const send=(m,pr={})=>new Promise((res,rej)=>{const i=++id;p.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:pr}))});
  ws.on('message',raw=>{let m;try{m=JSON.parse(raw.toString())}catch{return}if(m.id&&p.has(m.id)){const q=p.get(m.id);p.delete(m.id);m.error?q.rej(new Error(JSON.stringify(m.error))):q.res(m.result)}});
  await new Promise(r=>ws.on('open',r)); await send('Runtime.enable');
  const b64='W3siciI6InN5c3RlbS90aW1lIiwicGFyYW1zIjp7InNuIjoidGVzdCJ9fV0=';
  const t='1794033000000';
  const probes=[
    ['EtsHelper','encode_api_body',JSON.stringify({body:b64,time:t})],
    ['EtsHelper','encode_api_resp',JSON.stringify({response:'W10=',time:t})],
    ['EtsHelper','encode_api_body_v2',JSON.stringify({body:b64,time:t})],
    ['EtsHelper','encode_api_resp_v2',JSON.stringify({response:'W10=',time:t})],
  ];
  const js='(async()=>{const out=[];const call=(pl,act,args)=>new Promise(res=>{let done=false;const uid=cef.message.createGuid()+"@x";const fin=v=>{if(done)return;done=true;try{cef.message.removeMessageCallback(uid)}catch(e){}res(typeof v==="string"?v:JSON.stringify(v))};const to=setTimeout(()=>fin("[TIMEOUT]"),2000);cef.message.setMessageCallback(uid,d=>{clearTimeout(to);fin(d)});try{cef.message.sendMessage(uid,pl,act,args)}catch(e){clearTimeout(to);fin("[THROW] "+e)}});for(const q of '+JSON.stringify(probes)+')out.push({p:q[0],a:q[1],args:q[2],r:await call(q[0],q[1],q[2])});return JSON.stringify(out)})()';
  const r=await send('Runtime.evaluate',{expression:js,awaitPromise:true,returnByValue:true});
  console.log(r.result.value);
  fs.writeFileSync('runtime/v1_oracle.json', r.result.value, 'utf8');
  ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
