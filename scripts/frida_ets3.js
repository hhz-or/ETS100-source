// ETS frida agent v4: + OnEncodeAPIResp / sign_resp, fixed module export hook
'use strict';
function log(s) { send(s); }
send('agent-start modules=' + Process.enumerateModules().length);

function readSimple(p) {
  try {
    if (!p || p.isNull()) return null;
    var size = p.add(16).readU32();
    var cap = p.add(20).readU32();
    var dp = cap > 0xF ? p.readPointer() : p;
    if (size > 20000) return '<big:' + size + '>';
    return dp.readUtf8String(size);
  } catch (e) { return '<errSimple:' + e + '>'; }
}
function tryStr(p) {
  try { if (!p || p.isNull()) return null; var s = p.readUtf8String(); if (s && s.length) return s; } catch (e) {}
  try { var w = p.readUtf16String(); if (w && w.length) return '[utf16]' + w; } catch (e) {}
  return null;
}

var m = Process.findModuleByName('etshelper.pln');
send('etshelper base=' + (m ? m.base : 'null'));
if (m) {
  Interceptor.attach(m.base.add(0xa410), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp;
        var p3 = sp.add(4).readPointer();
        var js = null; try { js = p3.readUtf16String(); } catch (e) {}
        if (!js) js = tryStr(p3);
        log('OnEncodeAPIBody sel=' + c.edx + ' json=' + String(js).slice(0, 700));
      } catch (e) { log('a410 err ' + e); }
    }
  });
  Interceptor.attach(m.base.add(0x9e60), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp;
        var p = sp.add(4).readPointer();
        var js = null; try { js = p.readUtf16String(); } catch (e) {}
        if (!js) js = tryStr(p);
        log('OnEncodeAPIResp ecx=' + c.ecx + ' edx=' + c.edx + ' json=' + String(js).slice(0, 700));
      } catch (e) { log('9e60 err ' + e); }
    }
  });
  Interceptor.attach(m.base.add(0x14110), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp;
        log('sign_body sel=' + c.ecx + ' prefix=' + readSimple(c.edx) + ' time=' + readSimple(sp.add(4).readPointer()) +
            ' body=' + String(readSimple(sp.add(8).readPointer())).slice(0, 300));
      } catch (e) { log('14110 err ' + e); }
    }
  });
  Interceptor.attach(m.base.add(0x14230), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp;
        log('sign_resp sel=' + c.ecx + ' A=' + readSimple(c.edx) + ' B=' + String(readSimple(sp.add(4).readPointer())).slice(0, 300) +
            ' C=' + String(readSimple(sp.add(8).readPointer())).slice(0, 300));
      } catch (e) { log('14230 err ' + e); }
    }
  });
  send('hooked etshelper');
}

// generic plugin dispatch observer (Frida 17: use module instance methods)
Process.enumerateModules().filter(function (x) { return /\.pln$/i.test(x.name); }).forEach(function (mod) {
  try {
    var addr = null;
    try { addr = mod.getExportByName('PlnOnProcessMessage'); } catch (e) {}
    if (!addr) { try { addr = mod.findExportByName('PlnOnProcessMessage'); } catch (e) {} }
    if (!addr) { send('no export in ' + mod.name); return; }
    Interceptor.attach(addr, {
      onEnter: function () {
        try {
          var c = this.context, sp = c.esp;
          var parts = [];
          var cands = [c.ecx, c.edx, sp.add(4).readPointer(), sp.add(8).readPointer()];
          for (var i = 0; i < cands.length; i++) {
            var s = tryStr(cands[i]);
            if (s && s.length < 2000) parts.push('arg' + i + '=' + s.slice(0, 300));
          }
          log('PLN ' + mod.name + ' ' + parts.join(' | '));
        } catch (e) { log('PLN ' + mod.name + ' err ' + e); }
      }
    });
    send('hooked ' + mod.name);
  } catch (e) { send('hook fail ' + mod.name + ': ' + e); }
});
