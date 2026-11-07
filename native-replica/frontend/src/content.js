/**
 * content 包加载链路（CONTRACT §7）
 *   HttpHelper.download → SevenZip.unzip → FileHelper.readfile(content.json)
 *   → 解析 collector.read / collector.dialogue / collector.picture
 * 音频路径再经 __core.media_url 转成壳内 HTTP URL。
 */
import { invokeJson, mediaUrl, coreInfo, isMock } from './bridge'

export class ContentError extends Error {
  constructor(message, steps = []) {
    super(message)
    this.name = 'ContentError'
    this.steps = steps
  }
}

export function joinWin(...parts) {
  return parts
    .filter((p) => p !== undefined && p !== null && String(p) !== '')
    .map((p, i) => {
      let s = String(p)
      if (i > 0) s = s.replace(/^[\\/]+/, '')
      return s.replace(/[\\/]+$/, '')
    })
    .join('\\')
}

function parseMaybeJson(text) {
  if (text && typeof text === 'object') return text
  if (typeof text !== 'string' || !text.trim()) throw new Error('content.json 为空')
  return JSON.parse(text)
}

/**
 * 加载一份 content 包。
 * @param {object} opts
 * @param {string} opts.stid   题目/子题资源 id
 * @param {string} [opts.zipUrl] content 包下载地址（来自作业/套卷里的 url + base_url）
 * @returns {Promise<{content:object, dir:string, zipPath:string, steps:Array, cached:boolean}>}
 */
export async function loadContentPackage({ stid, zipUrl } = {}) {
  const steps = []
  const push = (name, status, detail = '') => steps.push({ name, status, detail })
  const safeStid = String(stid || 'demo').replace(/[^\w.-]/g, '_')

  let core = {}
  try { core = (await coreInfo()) || {} } catch { core = {} }
  const cacheDir = core.cacheDir || 'C:\\Users\\Demo\\AppData\\Roaming\\ETS-Replica\\cache'
  const baseDir = joinWin(cacheDir, 'practice')
  const dir = joinWin(baseDir, safeStid)
  const zipPath = joinWin(baseDir, safeStid + '.zip')
  const contentPath = joinWin(dir, 'content.json')

  const readContent = async () => {
    const rf = await invokeJson('FileHelper', 'readfile', { filePath: contentPath }, 15000)
    const text = rf && typeof rf === 'object' ? (rf.content ?? rf.data) : rf
    const content = parseMaybeJson(text)
    push('读取 content.json', 'ok', contentPath)
    return content
  }

  // 原生模式优先命中本地缓存；mock 模式强制走完整链路，便于演示三步流程
  if (!isMock) {
    let cached = false
    try {
      const r = await invokeJson('FileHelper', 'existfileorfolder', { filePath: contentPath }, 5000)
      cached = !!(r && (r.result === true || r.exists === true))
    } catch { cached = false }
    if (cached) {
      push('命中本地缓存', 'ok', dir)
      const content = await readContent()
      return { content, dir, zipPath, steps, cached: true }
    }
  }

  try {
    try {
      await invokeJson('FileHelper', 'createfolder', { filePath: dir }, 8000)
    } catch { /* 目录已存在时忽略 */ }
    push('创建缓存目录', 'ok', dir)

    const url = zipUrl || (isMock ? `https://cdnsubject.ets100.com/made/mock/content_${safeStid}.zip` : '')
    if (!url) throw new ContentError('缺少 content 包下载地址（zip url）', steps)

    const dl = await invokeJson('HttpHelper', 'download', { url, filePath: zipPath }, 180000)
    const dlCode = dl && typeof dl === 'object' ? Number(dl.code) : 0
    if (dl && typeof dl === 'object' && dl.code !== undefined && dlCode !== 0) {
      push('下载 content 包', 'fail', `code=${dl.code} ${dl.msg || ''}`)
      throw new ContentError(`下载失败（code=${dl.code}）`, steps)
    }
    push('下载 content 包', 'ok', `${url.slice(0, 96)} → ${zipPath}`)

    const un = await invokeJson('SevenZip', 'unzip', { zipPath, outDir: dir }, 180000)
    const unCode = un && typeof un === 'object' ? Number(un.code) : 0
    if (un && typeof un === 'object' && un.code !== undefined && unCode !== 0) {
      push('解压 content 包', 'fail', `code=${un.code} ${un.msg || ''}`)
      throw new ContentError(`解压失败（code=${un.code}）`, steps)
    }
    push('解压 content 包', 'ok', `${(un && un.files) || 0} 个文件`)

    const content = await readContent()
    return { content, dir, zipPath, steps, cached: false }
  } catch (err) {
    if (err instanceof ContentError) throw err
    push('加载失败', 'fail', err && err.message ? err.message : String(err))
    throw new ContentError(err && err.message ? err.message : String(err), steps)
  }
}

/** 解析 structure_type 与 info */
export function parseStructure(content) {
  if (!content || typeof content !== 'object') return { type: '', kind: '', info: {} }
  const type = String(content.structure_type || content.structureType || '')
  const kind = type.replace(/^collector\./, '')
  const info = content.info || content.data || {}
  return { type, kind, info }
}

/** 题目资源路径 → __core.media_url */
export async function resolveMedia(dir, name) {
  if (!name) return ''
  const raw = String(name)
  const full = /^[a-zA-Z]:[\\/]/.test(raw) || /^https?:\/\//i.test(raw)
    ? raw
    : joinWin(dir, raw)
  if (/^https?:\/\//i.test(full)) return full
  return mediaUrl(full)
}

/** 把 "a</br>b" 之类文本转成安全的 HTML（仅保留 br/b/strong/em） */
export function safeRichText(text) {
  if (!text) return ''
  return String(text)
    .replace(/<br\s*\/?>/gi, '<br>')
    .replace(/<\/?(?!br\b|b\b|strong\b|em\b)[a-zA-Z][^>]*>/g, '')
    .replace(/&(?!(amp|lt|gt|quot|#\d+);)/g, '&amp;')
}

export default { loadContentPackage, parseStructure, resolveMedia, safeRichText, joinWin, ContentError }
