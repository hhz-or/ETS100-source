/**
 * ETS HTTP API 封装（CONTRACT §7）
 *
 * 统一信封：
 *   params = { sign_response:1, sn:"test", system:4, global_client_version:"5.7.9", token?, ...业务参数 }
 *   body64 = base64(UTF-8(JSON.stringify([{ r, params }])))
 *   head   = { version:"1.0", sign, pid, time, time_second }
 *   HttpHelper.request POST https://api.ets100.com/<r>
 * 响应：[{ msg, code, body }]；code 20004/30001 视为登录失效。
 */
import { invokeJson, logToHost } from './bridge'

export const BASE_URL = 'https://api.ets100.com'
export const HEAD_VERSION = '1.0'
export const CLIENT_VERSION = '5.7.9'
export const TOKEN_KEY = 'ets_token'
export const AUTH_EXPIRED_EVENT = 'ets:auth-expired'
const DEVICE_CACHE_KEY = 'ets_device'

export class ApiError extends Error {
  constructor(code, msg, route) {
    super(msg || `接口错误 code=${code}`)
    this.name = 'ApiError'
    this.code = code
    this.route = route
  }
}

export class AuthExpiredError extends ApiError {
  constructor(code, route) {
    super(code, '登录状态已失效，请重新登录', route)
    this.name = 'AuthExpiredError'
  }
}

// ---------------------------------------------------------------------------
// token / 设备
// ---------------------------------------------------------------------------
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* ignore */ }
}

export function clearToken() {
  setToken('')
}

let devicePromise = null

/** 设备信息：ShellHelper.getpcinfo + getuniqueid，派生 device_name/device_code/local_ip */
export function getDeviceInfo() {
  if (devicePromise) return devicePromise
  devicePromise = (async () => {
    let info = {}
    try {
      const raw = await invokeJson('ShellHelper', 'getpcinfo', '', 8000)
      info = typeof raw === 'string' ? JSON.parse(raw) : (raw || {})
    } catch { info = {} }

    let unique = ''
    try {
      const u = await invokeJson('ShellHelper', 'getuniqueid', '', 5000)
      unique = typeof u === 'string' ? u : (u && (u.id || u.uniqueid)) || ''
    } catch { unique = '' }

    let cached = {}
    try { cached = JSON.parse(localStorage.getItem(DEVICE_CACHE_KEY) || '{}') } catch { cached = {} }

    let deviceCode = cached.device_code
    if (!deviceCode) {
      deviceCode = String(unique).replace(/[^0-9a-fA-F]/g, '').toUpperCase().slice(0, 16)
      if (deviceCode.length < 16) {
        let rnd = ''
        const bytes = new Uint8Array(8)
        if (typeof crypto !== 'undefined' && crypto.getRandomValues) crypto.getRandomValues(bytes)
        else for (let i = 0; i < 8; i++) bytes[i] = Math.floor(Math.random() * 256)
        for (const b of bytes) rnd += b.toString(16).padStart(2, '0')
        deviceCode = (deviceCode + rnd.toUpperCase()).slice(0, 16)
      }
    }

    const result = {
      device_name: info.computername || info.Name || cached.device_name || 'ETS-PC',
      device_code: deviceCode,
      local_ip: info.IP2 || info.ip || cached.local_ip || '127.0.0.1',
      raw: info
    }
    try { localStorage.setItem(DEVICE_CACHE_KEY, JSON.stringify({ device_name: result.device_name, device_code: result.device_code, local_ip: result.local_ip })) } catch { /* ignore */ }
    return result
  })()
  return devicePromise
}

// ---------------------------------------------------------------------------
// base64 / 签名
// ---------------------------------------------------------------------------
export function base64Utf8(str) {
  // 与原前端一致：先 UTF-8 转义，再 btoa
  return btoa(unescape(encodeURIComponent(String(str))))
}

function normalizeRoute(route) {
  return String(route || '').replace(/^\/+/, '')
}

async function aesEncrypt(plain) {
  const res = await invokeJson('EtsHelper', 'aes_ecb_encrypt', { plain: String(plain) }, 12000)
  const b64 = typeof res === 'string' ? res : (res && (res.b64 || res.base64))
  if (!b64) throw new Error('aes_ecb_encrypt 未返回密文')
  return b64
}

const SIGN_PATTERN = /^[a-f\d]{32}$/i

/** v2 优先；失败回落 v1（与原前端 EtsSignatureAdapter 语义一致） */
export async function signBody(bodyB64, time) {
  try {
    const v2 = await invokeJson('EtsHelper', 'encode_api_body_v2', { body: bodyB64, time: String(time) }, 8000)
    const obj = typeof v2 === 'string' ? safeJson(v2) : v2
    if (obj && obj.sign && SIGN_PATTERN.test(String(obj.sign))) {
      return { sign: String(obj.sign), pid: obj.pid || 'pcWin', key_id: obj.key_id || '', sign_version: obj.sign_version || '2' }
    }
  } catch { /* fall through to v1 */ }

  const v1 = await invokeJson('EtsHelper', 'encode_api_body', { body: bodyB64, time: String(time) }, 8000)
  const sign = typeof v1 === 'string' ? v1 : (v1 && v1.sign)
  if (!sign || !SIGN_PATTERN.test(String(sign))) throw new Error('签名服务不可用（EtsHelper.encode_api_body_v2/v1）')
  return { sign: String(sign), pid: 'grlx', key_id: '', sign_version: '1' }
}

function safeJson(text) {
  try { return JSON.parse(text) } catch { return null }
}

/** 日志脱敏：token/password/secret/accessKey 等字段统一替换 */
function redactSensitive(value) {
  if (value === null || typeof value !== 'object') return value
  if (Array.isArray(value)) return value.map(redactSensitive)
  const out = {}
  for (const [k, v] of Object.entries(value)) {
    out[k] = /token|password|secret|accesskey|phone|mobile|email/i.test(k) ? '***' : redactSensitive(v)
  }
  return out
}

// ---------------------------------------------------------------------------
// 请求
// ---------------------------------------------------------------------------
function handleAuthExpired(code, route) {
  clearToken()
  try {
    window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail: { code, route } }))
  } catch { /* ignore */ }
  return new AuthExpiredError(code, route)
}

/**
 * 发送统一信封请求。
 * @param {string} route  例如 "user/info" / "/m/homework/info"
 * @param {object} params 业务参数
 * @param {object} [opts] { withToken=true, injectCommon=true, timeoutMs=30000 }
 * @returns {Promise<any>} 响应信封里的 body
 */
export async function sendRequest(route, params = {}, opts = {}) {
  const { withToken = true, injectCommon = true, timeoutMs = 30000 } = opts
  const started = Date.now()
  const token = getToken()
  const common = injectCommon
    ? { sign_response: 1, sn: 'test', system: 4, global_client_version: CLIENT_VERSION }
    : {}
  if (injectCommon && withToken && token) common.token = token

  const fullParams = { ...common, ...(params || {}) }
  const bodyArray = [{ r: normalizeRoute(route), params: fullParams }]
  const bodyB64 = base64Utf8(JSON.stringify(bodyArray))
  const time = String(Date.now())
  const signInfo = await signBody(bodyB64, time)

  const payload = {
    body: bodyB64,
    head: {
      version: HEAD_VERSION,
      sign: signInfo.sign,
      pid: signInfo.pid || 'pcWin',
      time,
      time_second: Number(time)
    }
  }

  const url = BASE_URL + '/' + normalizeRoute(route)
  const logParams = { ...fullParams }
  if (logParams.token) logParams.token = '***'
  logToHost(1, 'API_ETS', `ets request $api_name=${url} param=${JSON.stringify(logParams)}`)

  let res
  try {
    res = await invokeJson('HttpHelper', 'request', {
      url,
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json;charset=UTF-8' },
      timeoutMs
    }, timeoutMs + 5000)
  } catch (err) {
    logToHost(2, 'API_ETS', `ets request failed $api_name=${url} error=${err && err.message}`)
    throw new Error(`网络请求失败：${err && err.message ? err.message : err}`)
  }

  const status = res && typeof res === 'object' ? res.status : 0
  const rawText = res && typeof res === 'object' ? res.body : res
  if (status && status !== 200) {
    throw new Error(`HTTP ${status}: ${String(rawText || '').slice(0, 200)}`)
  }

  let envelope
  try {
    envelope = typeof rawText === 'string' ? JSON.parse(rawText) : rawText
  } catch {
    throw new Error(`响应不是合法 JSON：${String(rawText || '').slice(0, 120)}`)
  }

  const payloadItem = Array.isArray(envelope) ? (envelope[0] || {}) : (envelope || {})
  const code = Number(payloadItem.code)
  const elapsed = Date.now() - started
  logToHost(1, 'API_ETS', `${elapsed}ms ets response $api_name=${url} return=${JSON.stringify(redactSensitive(payloadItem)).slice(0, 500)}`)

  if (code === 20004 || code === 30001) throw handleAuthExpired(code, route)
  if (code !== 0) throw new ApiError(code, payloadItem.msg || `接口返回 code=${code}`, route)
  return payloadItem.body
}

/** 登 录（严格按 CONTRACT §7 的字段与顺序） */
export async function login(phone, password) {
  if (!phone || !password) throw new Error('请输入手机号与密码')
  const [encPhone, encPassword, device] = await Promise.all([
    aesEncrypt(phone),
    aesEncrypt(password),
    getDeviceInfo()
  ])

  const params = {
    sign_response: 1,
    sn: 'test',
    system: 4,
    global_client_version: CLIENT_VERSION,
    phone: encPhone,
    password: encPassword,
    device_name: device.device_name,
    device_code: device.device_code,
    local_ip: device.local_ip,
    version: 4
  }

  const body = await sendRequest('user/login', params, {
    injectCommon: false,
    withToken: false,
    timeoutMs: 60000
  })

  if (!body || !body.token) throw new Error('登录响应缺少 token')
  setToken(body.token)
  try { localStorage.setItem('ets_user', JSON.stringify(body)) } catch { /* ignore */ }
  return body
}

export async function logout() {
  try {
    if (getToken()) await sendRequest('user/logout', {}, { timeoutMs: 8000 })
  } catch { /* 忽略登出接口失败 */ }
  clearToken()
  try { localStorage.removeItem('ets_user') } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// 业务接口（最小对等集）
// ---------------------------------------------------------------------------
export const api = {
  login,
  logout,
  getUserInfo: () => sendRequest('user/info'),
  getSystemConfig: (params = {}) => sendRequest('system/config', { checkToken: false, ...params }, { withToken: false }),
  getAnnouncements: () => sendRequest('/announcement/list', { checkToken: false }, { withToken: false }),
  getSystemTime: () => sendRequest('system/time', {}, { withToken: false }),
  getHomeworkList: (params = {}) => {
    const parent = params.parent_account_id || params.parentAccountId || ''
    return sendRequest('g/homework/list', {
      version: 11,
      parent_account_id: String(parent || ''),
      offset: Number(params.offset || 0),
      status: Number(params.status ?? 0),
      get_all_count: 1,
      limit: Number(params.limit || 10),
      get_to_do_count: 1,
      get_to_overtime_count: 1,
      check_pass: 1,
      show_old_homework: 1,
      get_audio_task: 1,
      use_https: 1,
      use_homework_privilege: 1
    })
  },
  getHomeworkInfo: (homeworkId) => sendRequest('m/homework/info', { homework_id: String(homeworkId) }),
  getMistakeSummary: (params = {}) => {
    const parent = params.parent_account_id || params.parentAccountId || ''
    return sendRequest('m/mistake/summary', { parent_account_id: String(parent || '') })
  },
  getMistakeList: (params = {}) => sendRequest('m/mistake/list', { page: 1, limit: 20, ...params }),
  getEcardList: () => sendRequest('m/ecard/list'),
  getColumns: (params = {}) => sendRequest('g/set/column-v2', { ...params }),
  getSets: (params = {}) => sendRequest('g/set/list', { page: 1, limit: 20, ...params }),
  getUnits: (params = {}) => sendRequest('g/set/unit-list', { ...params }),
  getUnitInfo: (unitId) => sendRequest('g/set/unit-info', { unit_id: unitId }),
  getModules: (unitId) => sendRequest('g/set/module-list', { unit_id: unitId }),
  getBooks: (params = {}) => sendRequest('g/resource/book-list', { ...params }),
  getGrades: () => sendRequest('g/resource/grade-list'),
  getAdvertisements: (params = {}) => sendRequest('m/advertisement/list', { ...params })
}

export default api
