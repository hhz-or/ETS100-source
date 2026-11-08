// ETS 练习抓包 · Frida 采集 agent
// 只读 Hook 7 个 .pln 的 PlnOnProcessMessage：记录 action 与参数 JSON（HttpHelper 的请求 URL/body 明文在此）。
// 注意：不要 attach 未知地址（例如猜测的回调指针），否则可能破坏目标进程内存。
'use strict';

const MAX_TEXT = 8 * 1024 * 1024;
let dbgCount = 0;
function emit(o) { try { send(o); } catch (e) {} }
function readA(p) { try { if (!p || p.isNull()) return ''; return p.readUtf8String(); } catch (e) { return ''; } }
function readW(p) { try { if (!p || p.isNull()) return ''; return p.readUtf16String(); } catch (e) { return ''; } }
function clip(s) { return s.length > MAX_TEXT ? s.slice(0, MAX_TEXT) + '…<truncated>' : s; }

// ---------------- 插件层（只读参数） ----------------
let pluginCount = 0;
Process.enumerateModules().filter(function (m) { return /\.pln$/i.test(m.name); }).forEach(function (mod) {
  try {
    var addr = null;
    try { addr = mod.getExportByName('PlnOnProcessMessage'); } catch (e) {}
    if (!addr) { try { addr = Module.getExportByName(mod.name, 'PlnOnProcessMessage'); } catch (e) {} }
    if (!addr) return;
    var pluginName = mod.name.replace(/\.pln$/i, '');
    Interceptor.attach(addr, {
      onEnter: function () {
        try {
          var sp = ptr(this.context.esp);
          var actionPtr = sp.add(4).readPointer();
          var argsPtr = sp.add(8).readPointer();
          var uidPtr = sp.add(16).readPointer();
          var action = readA(actionPtr) || readW(actionPtr);
          var uid = readA(uidPtr) || readW(uidPtr);
          var args = clip(readW(argsPtr) || readA(argsPtr));
          emit({ type: 'plugin', phase: 'call', plugin: pluginName, action: action, uid: uid, args: args });
          if (dbgCount < 3 && action === 'request') {
            dbgCount++;
            emit({ type: 'dbg', plugin: pluginName, action: action, argsLen: args.length, preview: args.slice(0, 300) });
          }
        } catch (e) {}
      }
    });
    pluginCount++;
  } catch (e) {}
});
send({ type: 'ready', msg: 'plugin hooks installed', plugins: pluginCount });

// ---------------- WinHTTP 兜底（只读） ----------------
const wmod = Process.findModuleByName('winhttp.dll');
if (!wmod) {
  send({ type: 'ready', msg: 'winhttp not present (plugin hooks only)' });
} else {
  const exp = n => { try { return wmod.getExportByName(n); } catch (e) { return null; } };
  const handles = new Map();
  let QueryHeaders = null;
  try {
    QueryHeaders = new NativeFunction(wmod.getExportByName('WinHttpQueryHeaders'),
      'int', ['pointer', 'uint32', 'pointer', 'pointer', 'pointer', 'pointer']);
  } catch (e) {}

  const Connect = exp('WinHttpConnect');
  if (Connect) Interceptor.attach(Connect, {
    onEnter: function (args) { try { this.host = readW(args[1]); } catch (e) { this.host = ''; } },
    onLeave: function (ret) { if (ret && !ret.isNull()) handles.set(ret.toString(), { host: this.host || '', verb: '', path: '', req: '', resp: '', status: 0 }); }
  });
  const OpenRequest = exp('WinHttpOpenRequest');
  if (OpenRequest) Interceptor.attach(OpenRequest, {
    onEnter: function (args) { this.hConnect = args[0]; this.verb = readW(args[1]) || 'GET'; this.path = readW(args[2]) || ''; },
    onLeave: function (ret) {
      if (!ret || ret.isNull()) return;
      const parent = this.hConnect ? handles.get(this.hConnect.toString()) : null;
      handles.set(ret.toString(), { host: parent ? parent.host : '', verb: this.verb, path: this.path, req: '', resp: '', status: 0 });
    }
  });
  const SendRequest = exp('WinHttpSendRequest');
  if (SendRequest) Interceptor.attach(SendRequest, {
    onEnter: function (args) {
      this.entry = args[0] ? handles.get(args[0].toString()) : null;
      try {
        const lp = args[3];
        let len = Number(args[4]);
        if (!len || len === 0xFFFFFFFF) len = Number(args[5]);
        if (lp && !lp.isNull() && len > 0 && len < MAX_TEXT) {
          const b = new Uint8Array(lp.readByteArray(len));
          let s = '';
          for (let i = 0; i < b.length; i += 8192) s += String.fromCharCode.apply(null, b.subarray(i, i + 8192));
          this.req = btoa(s);
        }
      } catch (e) {}
    },
    onLeave: function () { if (this.entry && this.req) this.entry.req = this.req; }
  });
  const RecvResponse = exp('WinHttpReceiveResponse');
  if (RecvResponse) Interceptor.attach(RecvResponse, {
    onEnter: function (args) { this.entry = args[0] ? handles.get(args[0].toString()) : null; this.h = args[0]; },
    onLeave: function (ret) {
      if (!this.entry || !ret || !ret.toInt32() || !QueryHeaders) return;
      try {
        const code = Memory.alloc(8), size = Memory.alloc(4);
        size.writeU32(4);
        if (QueryHeaders(this.h, 0x20000013, ptr(0), code, size, ptr(0))) this.entry.status = code.readU32();
      } catch (e) {}
    }
  });
  const CloseHandle = exp('WinHttpCloseHandle');
  if (CloseHandle) Interceptor.attach(CloseHandle, {
    onEnter: function (args) {
      if (!args[0]) return;
      const e = handles.get(args[0].toString());
      if (e) { handles.delete(args[0].toString()); emit({ type: 'http', host: e.host, verb: e.verb, path: e.path, status: e.status, reqB64: e.req || '' }); }
    }
  });
  send({ type: 'ready', msg: 'winhttp hooks installed' });
}
