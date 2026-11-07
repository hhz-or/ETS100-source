// ETS frida agent v3 (Frida 17: use NativePointer read methods)
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
        var js = null;
        try { js = p3.readUtf16String(); } catch (e) {}
        if (!js) js = tryStr(p3);
        log('OnEncodeAPIBody sel=' + c.edx + ' json=' + String(js).slice(0, 700));
      } catch (e) { log('a410 err ' + e); }
    }
  });
  send('hooked a410');
  Interceptor.attach(m.base.add(0x14110), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp;
        var prefix = readSimple(c.edx);
        var timeP = sp.add(4).readPointer();
        var bodyP = sp.add(8).readPointer();
        log('sign_body sel=' + c.ecx + ' prefix=' + prefix + ' time=' + readSimple(timeP) + ' body=' + String(readSimple(bodyP)).slice(0, 400));
      } catch (e) { log('14110 err ' + e); }
    }
  });
  send('hooked 14110');
}

// generic plugin dispatch observer
Process.enumerateModules().filter(function (x) { return /\.pln$/i.test(x.name); }).forEach(function (mod) {
  try {
    var addr = Module.getExportByName(mod.name, 'PlnOnProcessMessage');
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
