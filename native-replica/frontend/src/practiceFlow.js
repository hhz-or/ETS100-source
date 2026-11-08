/**
 * 练习结果上传 + 成绩回传（真实协议，见 docs/15_practice_protocol.md §3/§4）
 *
 * 流程：
 *   16k PCM → soundhelper.encode_mp3（ffmpeg）→ mp3
 *   speex 编码（ise.encodeSpeex）→ spx
 *   ISE 结果 XML → xml
 *   STS 凭证（ossEvaluateUploadStsToken）→ mp3/spx/xml 表单上传 OSS（public-read）
 *   /m/audio/sync-v2 回传成绩（mark_trace_id / 三条 URL / score_detail）
 */
import { invokeJson } from './bridge'
import { sendRequest } from './api'

const encoder = new TextEncoder()

export function bytesToB64(bytes) {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
  let s = ''
  for (let i = 0; i < u8.length; i += 8192) s += String.fromCharCode.apply(null, u8.subarray(i, i + 8192))
  return btoa(s)
}

/** 获取 OSS STS（上传音频/结果的临时凭证 + 目录前缀） */
export async function fetchSts() {
  const body = await sendRequest('p1/student/config/config/ossEvaluateUploadStsToken', {})
  const upload = (body && (body.upload || body)) || {}
  if (!upload.accessKeyId || !upload.securityToken) {
    throw new Error('OSS STS 返回异常：' + JSON.stringify(body).slice(0, 200))
  }
  return body
}

/** 查找 ffmpeg（环境变量 ETS_FFMPEG / appDir\tools\ffmpeg.exe / PATH） */
export async function ensureFfmpeg() {
  const r = await invokeJson('__core', 'tool', { name: 'ffmpeg' }, 15000)
  if (!r || r.code !== 0 || !r.path) {
    throw new Error((r && r.msg) || '未找到 ffmpeg：请把 ffmpeg.exe 放到程序目录 tools\\ 下，或设置环境变量 ETS_FFMPEG')
  }
  return r.path
}

/** PCM16(16k mono) → mp3（上传/回放用，24kbps） */
export async function encodeMp3(pcmBytes, ffmpegPath, bitrate = '24k') {
  const r = await invokeJson('soundhelper', 'encode_mp3', {
    pcm: bytesToB64(pcmBytes),
    ffmpeg: ffmpegPath,
    bitrate
  }, 180000)
  if (!r || r.code !== 0 || !r.mp3) throw new Error('mp3 生成失败：' + JSON.stringify(r).slice(0, 200))
  return r.mp3 // base64
}

// ---------------- OSS 上传 ----------------
function randomHex(bytes) {
  const a = new Uint8Array(bytes)
  crypto.getRandomValues(a)
  return Array.from(a).map(x => x.toString(16).padStart(2, '0')).join('')
}

function abToB64(buf) {
  const bytes = new Uint8Array(buf)
  let s = ''
  for (let i = 0; i < bytes.length; i += 8192) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192))
  return btoa(s)
}

async function buildOssFields(sts, kind, key) {
  const upload = sts.upload || sts
  const bucket = upload.bucket || 'ets60'
  const expiration = upload.expiration || new Date(Date.now() + 3600_000).toISOString().replace(/\.\d+Z$/, 'Z')
  const policyDoc = {
    expiration,
    conditions: [
      ['content-length-range', 0, 524288000],
      ['eq', '$bucket', bucket],
      ['eq', '$key', key]
    ]
  }
  const policy = btoa(JSON.stringify(policyDoc))
  const keyObj = await crypto.subtle.importKey('raw', encoder.encode(upload.accessKeySecret), { name: 'HMAC', hash: 'SHA-1' }, false, ['sign'])
  const sig = await crypto.subtle.sign('HMAC', keyObj, encoder.encode(policy))
  return {
    OSSAccessKeyId: upload.accessKeyId,
    policy,
    Signature: abToB64(sig),
    'x-oss-security-token': upload.securityToken,
    'x-oss-object-acl': 'public-read',
    key,
    submit: 'Submit',
    success_action_status: '200'
  }
}

function ossPathFor(sts, kind) {
  return (kind === 'mp3' ? sts.mp3Path : kind === 'speex' ? sts.spxPath : sts.xmlPath) || ''
}

/** 上传单个文件（base64），返回公网 URL */
export async function ossUpload(base64, fileName, kind, sts) {
  const upload = sts.upload || sts
  const bucket = upload.bucket || 'ets60'
  const endpoint = upload.endpoint || 'oss-cn-hangzhou.aliyuncs.com'
  const cname = (upload.cname || `https://${bucket}.${endpoint}`).replace(/\/+$/, '')
  const prefix = ossPathFor(sts, kind)
  if (!prefix) throw new Error(`STS 缺少 ${kind} 上传目录`)
  const key = `${prefix}${fileName}`
  const fields = await buildOssFields(sts, kind, key)
  const mime = kind === 'mp3' ? 'audio/mpeg' : kind === 'xml' ? 'text/xml' : 'application/octet-stream'
  const r = await invokeJson('httphelper', 'upload', {
    url: `https://${bucket}.${endpoint}/`,
    fileName,
    mime,
    fileBase64: base64,
    fields,
    timeoutMs: 180000
  }, 200000)
  const status = r && r.status
  if (!r || (status !== 200 && status !== 201 && status !== 204)) {
    throw new Error(`上传 ${fileName} 失败：HTTP ${status || '?'} ${(r && r.body) || ''}`.slice(0, 300))
  }
  return `${cname}/${key}`
}

/** 一次上传 3 个评测产物，返回 {mp3, spx, xml} URL */
export async function uploadArtifacts({ pcm, spxBytes, xml, ffmpegPath, sts }) {
  const base = `public_${randomHex(16)}_${Date.now()}`
  const mp3B64 = await encodeMp3(pcm, ffmpegPath)
  const urls = {}
  urls.mp3 = await ossUpload(mp3B64, `${base}.mp3`, 'mp3', sts)
  urls.spx = await ossUpload(bytesToB64(spxBytes), `${base}.mp3.spx`, 'speex', sts)
  urls.xml = await ossUpload(bytesToB64(encoder.encode(xml || '')), `${base}.xml`, 'xml', sts)
  return urls
}

// ---------------- 成绩回传 ----------------
export function buildSyncParams({ scores, urls, traceId, homeworkId, setId, entityId, order = 1,
                                  resourceId = '239', firstColumnId = '1', questionTypeScore = '0.5',
                                  graduation = '0.125', rateScale = 1, category = 'read_sentence',
                                  markService = 1 }) {
  const num = v => Number(v) || 0
  const qts = Number(questionTypeScore) || 0.5
  const total = num(scores && scores.total)
  const real = Math.round(total * qts * 100) / 100
  const detail = {
    accuracy_score: num(scores && scores.accuracy),
    fluency_score: num(scores && scores.fluency),
    integrity_score: num(scores && scores.integrity),
    standard_score: num(scores && scores.standard),
    total_score: total,
    real_score: real,
    category,
    rate_scale: rateScale
  }
  return {
    resource_id: String(resourceId),
    real_score: real,
    score: real,
    set_id: String(setId),
    entity_id: String(entityId),
    order: String(order),
    mistake_id: '',
    upload_file_id: '',
    upload_file_url: urls.mp3,
    spx_file_url: urls.spx,
    mark_trace_id: traceId || '',
    detail_file_id: '',
    detail_file_url: urls.xml,
    score_detail: JSON.stringify(detail),
    exam_id: null,
    homework_id: String(homeworkId),
    first_column_id: String(firstColumnId),
    question_type_score: String(questionTypeScore),
    rate_scale: rateScale,
    graduation: String(graduation),
    client_time: formatTime(new Date()),
    mark_service: markService,
    version: '2'
  }
}

function formatTime(d) {
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

export async function syncAudio(params) {
  return await sendRequest('/m/audio/sync-v2', params, { timeoutMs: 60000 })
}

export async function homeworkInfo(homeworkId, resourceId = '239', setId = '') {
  const params = { resource_id: String(resourceId), homework_id: String(homeworkId), version: 2 }
  if (setId) params.set_id = String(setId)
  return await sendRequest('/m/homework/info', params)
}

export async function mistakeUpdate({ homeworkId, setId, resourceId = '239' }) {
  return await sendRequest('/m/mistake/update', {
    homework_id: String(homeworkId),
    set_id: String(setId || ''),
    exam_id: '',
    mistake_id: '',
    combination_id: '',
    composition_id: '',
    type: '1',
    resource_id: String(resourceId),
    sync: '0'
  })
}

export async function setUseTime({ homeworkId, resourceId = '239', useTime, correct = 0 }) {
  return await sendRequest('/m/homework/set-use-time', {
    version: 2,
    correct,
    use_time: Math.max(0, Math.round(useTime)),
    resource_id: String(resourceId),
    homework_id: Number(homeworkId)
  })
}

/** 全流程：mp3 + 上传 + sync-v2 -> 返回 {urls, sync} */
export async function uploadAndSync(opts) {
  const sts = opts.sts || await fetchSts()
  const ffmpegPath = opts.ffmpegPath || await ensureFfmpeg()
  const urls = await uploadArtifacts({ ...opts, ffmpegPath, sts })
  const params = buildSyncParams({ ...opts, urls })
  const sync = await syncAudio(params)
  return { urls, sync, params }
}

export default {
  fetchSts, ensureFfmpeg, encodeMp3, ossUpload, uploadArtifacts,
  buildSyncParams, syncAudio, homeworkInfo, mistakeUpdate, setUseTime, uploadAndSync, bytesToB64
}
