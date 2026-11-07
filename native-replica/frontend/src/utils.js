/** 通用展示工具 */

export function fmtDate(sec, withTime = false) {
  const n = Number(sec)
  if (!n) return '—'
  const d = new Date(n * 1000)
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (v) => String(v).padStart(2, '0')
  const base = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  return withTime ? `${base} ${pad(d.getHours())}:${pad(d.getMinutes())}` : base
}

export function daysLeft(sec) {
  const n = Number(sec)
  if (!n) return null
  return Math.ceil((n * 1000 - Date.now()) / 86400000)
}

export function homeworkState(hw) {
  if (!hw) return 'todo'
  if (Number(hw.overtime) === 1) return 'overdue'
  if (Number(hw.status) === 1 || Number(hw.complete) === 1) return 'done'
  const end = Number(hw.end)
  if (end && end * 1000 < Date.now()) return 'overdue'
  return 'todo'
}

export function stateText(state) {
  return { todo: '待完成', done: '已完成', overdue: '已过期' }[state] || '待完成'
}

export function fmtSize(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}

export function greeting(name) {
  const h = new Date().getHours()
  const word = h < 6 ? '夜深了' : h < 11 ? '早上好' : h < 14 ? '中午好' : h < 18 ? '下午好' : '晚上好'
  return `${word}，${name || '同学'}`
}

export function todayText() {
  const d = new Date()
  const week = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${week}`
}

/** 从任意结构里尽力取出列表 */
export function asList(value, ...keys) {
  if (Array.isArray(value)) return value
  if (!value || typeof value !== 'object') return []
  for (const k of keys) {
    if (Array.isArray(value[k])) return value[k]
  }
  return []
}
