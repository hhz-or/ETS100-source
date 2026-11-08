/**
 * ISE 口语评测客户端（前端参考实现）
 * ---------------------------------------------------------------------------
 * 协议来自真实抓包（docs/15_practice_protocol.md）：
 *   wss://oe-pub.eduaiplat.com/ws/v2/ise，binary protobuf：
 *   init(会话参数 + 第一块音频 + token + 16k/speex) → N 个音频块(212B) → 结束帧 → 结果帧(XML)
 *
 * 录音：浏览器 getUserMedia → 16k PCM → soundhelper.encode_speex（C++/speex CBR 84800）
 */
import { invokeJson } from './bridge'
import { sendRequest } from './api'

const ISE_URL = 'wss://oe-pub.eduaiplat.com/ws/v2/ise'
export const CHUNK_BYTES = 212

// ---------------- protobuf wire ----------------
function varint(n) {
  const out = []
  while (n > 127) { out.push((n & 0x7f) | 0x80); n >>>= 7 }
  out.push(n)
  return Uint8Array.from(out)
}
function concat(arrs) {
  const len = arrs.reduce((a, b) => a + b.length, 0)
  const out = new Uint8Array(len)
  let off = 0
  for (const a of arrs) { out.set(a, off); off += a.length }
  return out
}
function tag(f, wt) { return varint((f << 3) | wt) }
function bytesField(f, data) {
  const d = typeof data === 'string' ? new TextEncoder().encode(data) : data
  return concat([tag(f, 2), varint(d.length), d])
}
function varintField(f, v) { return concat([tag(f, 0), varint(v)]) }
function b64ToBytes(b64) {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}
function parseFields(buf) {
  const out = []
  let i = 0
  const rv = () => {
    let shift = 0, val = 0
    while (true) { const b = buf[i++]; val |= (b & 0x7f) << shift; if (!(b & 0x80)) return val; shift += 7 }
  }
  while (i < buf.length) {
    const key = rv()
    const f = key >> 3, wt = key & 7
    if (wt === 0) out.push({ f, wt, v: rv() })
    else if (wt === 2) { const ln = rv(); out.push({ f, wt, d: buf.slice(i, i + ln) }); i += ln }
    else if (wt === 5) { out.push({ f, wt, d: buf.slice(i, i + 4) }); i += 4 }
    else if (wt === 1) { out.push({ f, wt, d: buf.slice(i, i + 8) }); i += 8 }
    else break
  }
  return out
}
const dec = new TextDecoder()

// ---------------- messages ----------------
function buildInit(session, token, firstChunk) {
  const info = concat([
    bytesField(1, session.clientId || 'ksyyyxx-etszx'),
    bytesField(2, String(session.accountId || '')),
    bytesField(3, session.mac || '00-00-00-00-00-00'),
    bytesField(4, session.appId || 'ets_70'),
    bytesField(5, session.sdkKey || 'SDK_pY1wOPU8'),
    bytesField(6, session.requestId || randomHex(16)),
    bytesField(7, token),
    bytesField(8, ''),
    ...Object.entries(session.meta || {}).map(([k, v]) => bytesField(9, concat([bytesField(1, k), bytesField(2, String(v))])))
  ])
  const params = Object.entries(session.params || {}).map(([k, v]) =>
    bytesField(11, concat([bytesField(1, k), bytesField(2, String(v))])))
  return concat([
    bytesField(1, info),
    bytesField(2, 'en'),
    bytesField(3, ''),
    varintField(4, 1),
    bytesField(5, firstChunk),
    varintField(6, 16000),
    bytesField(7, 'speex'),
    varintField(8, 0),
    varintField(9, 0),
    varintField(10, 0),
    ...params,
    bytesField(12, ''),
    varintField(13, 3)
  ])
}
function audioFrame(chunk) {
  return concat([bytesField(5, chunk), bytesField(7, 'speex'), varintField(8, 0)])
}
function endFrame() {
  return concat([bytesField(5, new Uint8Array(10)), bytesField(7, 'speex'), varintField(8, 1)])
}
function randomHex(bytes) {
  const a = new Uint8Array(bytes)
  crypto.getRandomValues(a)
  return Array.from(a).map(x => x.toString(16).padStart(2, '0')).join('')
}

// ---------------- result ----------------
export function parseResult(data) {
  const out = { code: '', msg: '', traceId: '', xml: '' }
  const buf = new Uint8Array(data)
  for (const x of parseFields(buf)) {
    if (x.wt !== 2) continue
    if (x.f === 1) out.code = dec.decode(x.d)
    else if (x.f === 2) out.msg = dec.decode(x.d)
    else if (x.f === 3) out.traceId = dec.decode(x.d)
    else if (x.f === 4) {
      const inner = parseFields(x.d)
      if (inner.length >= 2 && inner[0].wt === 2 && dec.decode(inner[0].d) === 'result') out.xml = dec.decode(inner[1].d)
    }
  }
  if (!out.xml) {
    const s = dec.decode(buf)
    const m = s.match(/<xml_result[\s\S]*<\/xml_result>/)
    if (m) out.xml = m[0]
  }
  return out
}

export function parseScores(xml) {
  if (!xml) return null
  try {
    const doc = new DOMParser().parseFromString(xml, 'text/xml')
    const chapter = doc.querySelector('read_chapter') || doc.querySelector('[accuracy_score]')
    const words = [...doc.querySelectorAll('word')].map(w => ({
      content: w.getAttribute('content'),
      score: Number(w.getAttribute('total_score') || 0),
      beg: Number(w.getAttribute('beg_pos') || 0),
      end: Number(w.getAttribute('end_pos') || 0)
    }))
    return {
      accuracy: Number(chapter?.getAttribute('accuracy_score') || 0),
      fluency: Number(chapter?.getAttribute('fluency_score') || 0),
      integrity: Number(chapter?.getAttribute('integrity_score') || 0),
      standard: Number(chapter?.getAttribute('standard_score') || 0),
      total: Number(chapter?.getAttribute('total_score') || 0),
      isRejected: chapter?.getAttribute('is_rejected') === 'true',
      exceptInfo: chapter?.getAttribute('except_info') || '',
      content: chapter?.getAttribute('content') || '',
      words
    }
  } catch (e) {
    return null
  }
}

// ---------------- evaluate ----------------
async function fetchAccessToken() {
  const body = await sendRequest('ai/aiplat/getaitoken', {}, { withToken: true })
  return (body && body.accessToken) || ''
}

export function buildSession(store, opts = {}) {
  const profile = (store && store.profile) || {}
  const ecard = (store && store.activeEcard) || {}
  const meta = {
    uid: String(profile.id || profile.uid || profile.recent_account_id || ''),
    regionId: String(profile.province_id || ecard.region_id || '5269'),
    schoolId: String(ecard.school_area_id || ecard.school_id || ''),
    classId: String(ecard.class_id || ''),
    gradeId: String(profile.grade_id || ecard.grade_id || ''),
    stageId: String(profile.school_year_id || ecard.stage_id || ''),
    tpl_region: String(opts.region || 'shanghai'),
    scene_type: String(opts.sceneType || 'homework'),
    scene_id: String(opts.sceneId || ''),
    module: '1',
    plat_type: 'Web',
    plat_ver: '5.7.9'
  }
  return {
    clientId: 'ksyyyxx-etszx', accountId: meta.uid, mac: '00-00-00-00-00-00',
    appId: 'ets_70', sdkKey: 'SDK_pY1wOPU8', meta,
    params: {
      category: opts.category || 'read_sentence',
      paperId: String(opts.paperId || ''),
      region: String(opts.region || 'shanghai'),
      group: '',
      parsePaper: 'false',
      audioStorage: 'true',
      resultStorage: 'true'
    }
  }
}

/** 用 16k mono PCM（Int16Array/Uint8Array）做一次 ISE 评测 */
export async function evaluatePcm(pcmBytes, session, opts = {}) {
  const pcmB64 = bytesToB64(pcmBytes)
  const enc = await invokeJson('soundhelper', 'encode_speex', { pcm: pcmB64, quality: 10, bitrate: 84800 }, 180000)
  if (!enc || !enc.spx) throw new Error('speex 编码失败：' + JSON.stringify(enc).slice(0, 200))
  const spx = b64ToBytes(enc.spx)
  const chunks = []
  for (let off = 0; off < spx.length; off += CHUNK_BYTES) chunks.push(spx.slice(off, off + CHUNK_BYTES))
  if (!chunks.length) throw new Error('没有音频数据')
  const token = opts.token || await fetchAccessToken()
  if (!token) throw new Error('获取 ISE token 失败')
  return await evaluateChunks(chunks, session, token, opts)
}

function bytesToB64(bytes) {
  let s = ''
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes.buffer || bytes)
  for (let i = 0; i < u8.length; i += 8192) s += String.fromCharCode.apply(null, u8.subarray(i, i + 8192))
  return btoa(s)
}

export function evaluateChunks(chunks, session, token, opts = {}) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(ISE_URL)
    ws.binaryType = 'arraybuffer'
    const timeoutMs = opts.timeoutMs || 120000
    const timer = setTimeout(() => { try { ws.close() } catch (e) {} reject(new Error('ISE 超时')) }, timeoutMs)
    ws.onopen = () => {
      ws.send(buildInit(session, token, chunks[0]))
      let i = 1
      const step = () => {
        if (i >= chunks.length) { ws.send(endFrame()); return }
        ws.send(audioFrame(chunks[i])); i++
        setTimeout(step, 10)
      }
      setTimeout(step, 10)
    }
    ws.onmessage = (ev) => {
      clearTimeout(timer)
      try {
        const result = parseResult(ev.data)
        result.scores = parseScores(result.xml)
        result.chunks = chunks.length
        ws.close()
        resolve(result)
      } catch (e) { reject(e) }
    }
    ws.onerror = () => { clearTimeout(timer); reject(new Error('ISE WebSocket 连接失败（可能被 Origin 校验拦截）')) }
    ws.onclose = (ev) => { if (ev.code !== 1000 && ev.code !== 1005) { /* 服务端关闭 */ } }
  })
}

/** 调试：从 URL 取 PCM（16k s16le）评测，便于自动化验证 */
export async function evaluatePcmUrl(url, session, opts = {}) {
  const resp = await fetch(url)
  const buf = new Uint8Array(await resp.arrayBuffer())
  return evaluatePcm(buf, session, opts)
}

export default { evaluatePcm, evaluatePcmUrl, evaluateChunks, buildSession, parseScores, CHUNK_BYTES }
