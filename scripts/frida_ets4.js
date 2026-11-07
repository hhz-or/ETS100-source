// ETS frida agent v5: etshelper sign hooks only (no plugin export hooks)
'use strict';
function log(s) { send(s); }
send('agent-start');
function readSimple(p) {
  try {
    if (!p || p.isNull()) return null;
    var size = p.add(16).readU32();
    var cap = p.add(20).readU32();
    var dp = cap > 0xF ? p.readPointer() : p;
    if (size > 20000) return '<big:' + size + '>';
    return dp.readUtf8String(size);
  } catch (e) { return '<err:' + e + '>'; }
}
var m = Process.findModuleByName('etshelper.pln');
send('etshelper base=' + (m ? m.base : 'null'));
if (m) {
  Interceptor.attach(m.base.add(0xa410), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp, p3 = sp.add(4).readPointer(), js = null;
        try { js = p3.readUtf16String(); } catch (e) {}
        log('OnEncodeAPIBody sel=' + c.edx + ' json=' + String(js).slice(0, 500));
      } catch (e) { log('a410 err ' + e); }
    }
  });
  Interceptor.attach(m.base.add(0x9e60), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp, p = sp.add(4).readPointer(), js = null;
        try { js = p.readUtf16String(); } catch (e) {}
        log('OnEncodeAPIResp sel=' + c.edx + ' json=' + String(js).slice(0, 500));
      } catch (e) { log('9e60 err ' + e); }
    }
  });
  Interceptor.attach(m.base.add(0x14110), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp;
        log('sign_body sel=' + c.ecx + ' A=' + readSimple(c.edx) + ' B=' + readSimple(sp.add(4).readPointer()) + ' C=' + readSimple(sp.add(8).readPointer()));
      } catch (e) { log('14110 err ' + e); }
    }
  });
  Interceptor.attach(m.base.add(0x14230), {
    onEnter: function () {
      try {
        var c = this.context, sp = c.esp;
        log('sign_resp sel=' + c.ecx + ' A=' + readSimple(c.edx) + ' B=' + readSimple(sp.add(4).readPointer()) + ' C=' + readSimple(sp.add(8).readPointer()));
      } catch (e) { log('14230 err ' + e); }
    }
  });
  send('hooked etshelper');
}
