/**
 * JS ↔ Host 桥客户端封装（CONTRACT §4）
 *
 * 原生：window.cef.message.sendMessage(uid, plugin, action, args)
 *       host 回调 {type:"callback", uid, data}，由壳注入的监听器路由到 CEF_CB[uid]
 * Mock：window.chrome.webview 不存在时启用内置假数据（src/mock.js），
 *       保证浏览器直接打开 dist/ 也能完整预览。
 */
import { mockInvoke } from './mock'

const cef = () => (typeof window !== 'undefined' && window.cef && window.cef.message) || null

export const isMock = !(
  typeof window !== 'undefined' &&
  window.chrome &&
  window.chrome.webview &&
  cef()
)

export const bridgeMode = isMock ? 'mock' : 'native'

function createGuid() {
  const c = cef()
  if (c && typeof c.createGuid === 'function') {
    try {
      const g = c.createGuid()
      if (g) return g
    } catch { /* fallthrough */ }
  }
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    const v = ch === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

function normalizeArgs(args) {
  if (args === undefined || args === null) return ''
  if (typeof args === 'string') return args
  return JSON.stringify(args)
}

/**
 * 调用原生插件 action。
 * @param {string} plugin  EtsHelper / HttpHelper / FileHelper / SevenZip / SQLitePln / ShellHelper / SysConfig / __core
 * @param {string} action  插件 action 名
 * @param {object|string} [args] 参数对象或 JSON 字符串
 * @param {number} [timeoutMs=30000] 超时（毫秒）
 * @returns {Promise<any>} 原生返回的原始数据（通常为 JSON 字符串）
 */
export function invoke(plugin, action, args = '', timeoutMs = 30000) {
  if (isMock) {
    if (import.meta.env?.DEV) {
      // eslint-disable-next-line no-console
      console.debug('[bridge:mock]', plugin + '.' + action, args)
    }
    return mockInvoke(plugin, action, normalizeArgs(args))
  }

  return new Promise((resolve, reject) => {
    const message = cef()
    if (!message) {
      reject(new Error('cef.message 不可用'))
      return
    }
    const uid = createGuid() + '@' + String(action || 'action')
    let settled = false
    let timer = null

    const cleanup = () => {
      try { message.removeMessageCallback(uid) } catch { /* ignore */ }
      if (timer) clearTimeout(timer)
      timer = null
    }

    message.setMessageCallback(uid, (data) => {
      if (settled) return
      settled = true
      cleanup()
      resolve(data)
    })

    timer = setTimeout(() => {
      if (settled) return
      settled = true
      cleanup()
      reject(new Error(`调用超时: ${plugin}.${action} (${timeoutMs}ms)`))
    }, Math.max(1000, Number(timeoutMs) || 30000))

    try {
      message.sendMessage(uid, plugin, action, normalizeArgs(args))
    } catch (err) {
      if (settled) return
      settled = true
      cleanup()
      reject(err instanceof Error ? err : new Error(String(err)))
    }
  })
}

/**
 * 调用并解析 JSON 返回；解析失败时原样返回。
 */
export async function invokeJson(plugin, action, args = '', timeoutMs = 30000) {
  const raw = await invoke(plugin, action, args, timeoutMs)
  if (raw === undefined || raw === null || raw === '') return raw
  if (typeof raw !== 'string') return raw
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

/** 读取内置 __core.info */
export function coreInfo() {
  return invokeJson('__core', 'info', {}, 10000)
}

/** 把本地媒体路径转为壳内置 HTTP 服务的 URL */
export async function mediaUrl(path) {
  if (!path) return ''
  try {
    const res = await invokeJson('__core', 'media_url', { path: String(path) }, 10000)
    return (res && res.url) || ''
  } catch {
    return ''
  }
}

/** 打开系统默认浏览器（仅 http/https） */
export function openExternal(url) {
  if (!/^https?:\/\//i.test(String(url || ''))) return Promise.resolve({ ok: false })
  return invokeJson('__core', 'open_external', { url: String(url) }, 10000).catch(() => ({ ok: false }))
}

/** 上报一条前端日志到 mq_server（失败静默） */
export function logToHost(level, tag, msg) {
  return invokeJson('__core', 'log', { level, tag, msg: String(msg) }, 5000).catch(() => null)
}

export default { invoke, invokeJson, mediaUrl, coreInfo, openExternal, logToHost, isMock, bridgeMode }
