// ETS frida agent v6: hook MD5 update wrapper 0x23870 to capture exact hashed chunks
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
function readSimple2(p) {
  // variant: second field is size at +4 (SimpleString with ptr,size inline)
  try {
    var size = p.add(4).readU32();
    if (size > 20000) return null;
    var dp = p.readPointer();
    return dp.readUtf8String(size);
  } catch (e) { return null; }
}
var m = Process.findModuleByName('etshelper.pln');
send('etshelper base=' + (m ? m.base : 'null'));
if (m) {
  Interceptor.attach(m.base.add(0x23870), {
    onEnter: function () {
      try {
        var c = this.context;
        var s1 = readSimple(c.edx);
        var s2 = (s1 === null || s1.indexOf('<err') === 0) ? readSimple2(c.edx) : null;
        log('MD5UPDATE ecx=' + c.ecx + ' edx=' + c.edx + ' s1=' + JSON.stringify(s1) + ' s2=' + JSON.stringify(s2));
      } catch (e) { log('23870 err ' + e); }
    }
  });
  // also finalize 0x14050 and key feeder 0x13e00
  Interceptor.attach(m.base.add(0x13e00), {
    onEnter: function () {
      try { log('KEYFEED sel=' + this.context.ecx); } catch (e) {}
    }
  });
  send('hooked md5update/keyfeed');
}
