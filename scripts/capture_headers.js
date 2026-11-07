// capture runtime request headers + mq_server websocket frames
const WebSocket = require('ETS/mq_server/node_modules/ws');
const http = require('http');
const fs = require('fs');
const OUT = 'runtime';
function getJson(u){return new Promise((res,rej)=>{http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})}).on('error',rej)})}
(async()=>{
  const l=await getJson('http://127.0.0.1:10086/json/list');
  const pg=l.find(t=>t.type==='page');
  const ws=new WebSocket(pg.webSocketDebuggerUrl,{perMessageDeflate:false,maxPayload:256*1024*1024});
  let id=0;const p=new Map();const events=[];
  const send=(m,pr={})=>new Promise((res,rej)=>{const i=++id;p.set(i,{res,rej});ws.send(JSON.stringify({id:i,method:m,params:pr}))});
  ws.on('message',raw=>{let m;try{m=JSON.parse(raw.toString())}catch{return}if(m.id&&p.has(m.id)){const q=p.get(m.id);p.delete(m.id);m.error?q.rej(new Error(JSON.stringify(m.error))):q.res(m.result)}else if(m.method){events.push(m)}});
  await new Promise(r=>ws.on('open',r));
  await send('Network.enable',{maxTotalBufferSize:100*1024*1024});
  await send('Page.enable'); await send('Runtime.enable');
  const start=events.length;
  await send('Page.reload',{ignoreCache:false});
  await new Promise(r=>setTimeout(r,12000));
  const ev=events.slice(start);
  const headers=[];const wsFrames=[];
  for(const e of ev){
    if(e.method==='Network.requestWillBeSent'&&/ets100|eduaiplat/.test(e.params.request.url)){
      headers.push({url:e.params.request.url.split('?')[0],method:e.params.request.method,headers:e.params.request.headers});
    }
    if(e.method==='Network.webSocketCreated'){wsFrames.push({event:'created',url:e.params.url})}
    if(e.method==='Network.webSocketFrameSent'){wsFrames.push({event:'sent',payload:(e.params.response.payloadData||'').slice(0,600)})}
    if(e.method==='Network.webSocketFrameReceived'){wsFrames.push({event:'recv',payload:(e.params.response.payloadData||'').slice(0,600)})}
  }
  const uniq={};for(const h of headers){const k=h.method+' '+h.url;if(!uniq[k])uniq[k]=h}
  fs.writeFileSync(OUT+'/request_headers.json',JSON.stringify({requests:Object.values(uniq)},null,1),'utf8');
  fs.writeFileSync(OUT+'/ws_frames.json',JSON.stringify(wsFrames.slice(0,200),null,1),'utf8');
  console.log('request header entries:',Object.keys(uniq).length,'ws events:',wsFrames.length);
  ws.close();
})().catch(e=>{console.error('FATAL',e);process.exit(1)});
