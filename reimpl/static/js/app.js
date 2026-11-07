/* E听说 · 参考客户端 —— 原生 JS 单页应用（无构建、无外部依赖） */
'use strict';

/* ------------------------------------------------------------------ *
 * 全局状态
 * ------------------------------------------------------------------ */
const S = {
  status: null,
  statusError: null,
  home: null,
  modules: null,
  courses: null,
  currentRoute: 'home',
  detailCache: {},        // key -> detail
  practice: null,         // 当前练习状态
  pendingQuestion: 0,     // 详情页点击题目时传给练习页
  mistakes: null,
  mistakeDetail: null,
  ecards: null,
  config: null,
  configPage: 1,
  configQuery: '',
  clockOffset: 0,
  toastTimer: null,
  loginError: null,
  busy: false,
};

const COLUMN_NAMES = {
  1: '听说模拟', 12: '读写模拟', 88: '听力模拟',
  2: '听说专项', 3: '读写专项', 5: '听力专项',
  5: '听力专项', 108: '听说课堂',
};
const PHASE_LABEL = { todo: '待完成', done: '已完成', overtime: '已逾期', set: '套卷' };
const TYPE_LABEL = { read: '朗读', dialogue: '交际应答', picture: '复述/表达', choose: '选择/听力', unknown: '未支持题型' };
const FEATURE_NAMES = {
  fun_dub: '趣味配音', level_read: '分级阅读', instruction: '指导书', current_text: '同步课文',
  step_dub: '阶梯配音', xunting: '讯飞听听', concept: '概念讲解', audio_special: '听说专项',
  writing_special: '写作专项', grammar_special: '语法专项', study_plan: '学习计划',
  phonetic_study: '音标学习', pk: '单词 PK', word_translate: '单词翻译', mock_hs: '听说模拟',
  mock_rw: '读写模拟', special_hs: '听说专项', special_rw: '读写专项', famous_course: '名校课程',
  picture_book_reading: '绘本阅读', phonics: '自然拼读', common_competition: '通用竞赛',
  ket: 'KET', pet: 'PET', ai_talk: 'AI 对话', pay: '付费内容', ai_guidance: 'AI 导学',
  sync_picture_book_reading: '同步绘本', super_word: '超级单词', ai_diagnosis: 'AI 诊断',
  ai_correct: 'AI 批改', pronunciation_skills: '发音技巧', homework_privilege: '作业特权',
  micro_skill: '微技能', extract: '拓展',
};

/* ------------------------------------------------------------------ *
 * 小工具
 * ------------------------------------------------------------------ */
const $ = (sel) => document.querySelector(sel);
const view = () => document.getElementById('view');
const esc = (value) => String(value == null ? '' : value)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

/** 允许 ETS 题库内容里的 <p>、<br>、</br>，其余 HTML 全部转义。 */
function rich(value) {
  let text = esc(value);
  text = text.replace(/&lt;br\s*\/?&gt;/gi, '<br>')
    .replace(/&lt;\/br&gt;/gi, '<br>')
    .replace(/&lt;p(?:\s[^&]*)?&gt;/gi, '<p>')
    .replace(/&lt;\/p&gt;/gi, '</p>');
  return text.replace(/\r?\n/g, '<br>');
}
function cleanText(value) {
  return String(value == null ? '' : value)
    .replace(/<br\s*\/?>/gi, '\n').replace(/<\/br>/gi, '\n')
    .replace(/<[^>]+>/g, '').replace(/\r/g, '').trim();
}
function lines(value) {
  return cleanText(value).split('\n').map((x) => x.trim()).filter(Boolean);
}
function htmlOrDash(value) {
  const t = cleanText(value);
  return t ? rich(value) : '<span class="muted">—</span>';
}
function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function fmtNum(value, digits = 1) {
  const n = num(value);
  if (n == null) return '—';
  return Number.isInteger(n) ? String(n) : n.toFixed(digits);
}
function fmtDate(ts) {
  const n = num(ts);
  if (!n) return '—';
  const d = new Date(n > 1e12 ? n : n * 1000);
  if (Number.isNaN(d.getTime())) return '—';
  const p = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function fmtDuration(seconds) {
  const n = num(seconds);
  if (!n) return '—';
  if (n < 60) return `${Math.round(n)} 秒`;
  return `${Math.floor(n / 60)} 分 ${Math.round(n % 60)} 秒`;
}
function pct(value) {
  const n = num(value);
  return n == null ? '—' : `${Math.round(n)}%`;
}
function phaseBadge(phase) {
  const cls = phase === 'done' ? 'badge-green' : phase === 'overtime' ? 'badge-orange' : phase === 'set' ? 'badge-blue' : 'badge-blue';
  return `<span class="badge ${cls}">${PHASE_LABEL[phase] || esc(phase || '')}</span>`;
}
function typeBadge(type) {
  return `<span class="q-type-badge">${esc(TYPE_LABEL[type] || type || '未知')}</span>`;
}
function svgIcon(name) {
  const icons = {
    home: '<path d="M3 10.5 12 3l9 7.5V21H3V10.5Z"/>',
    expand: '<path d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z"/>',
    homework: '<path d="M5 3h14v18H5V3Zm3 4h8v2H8V7Zm0 4h8v2H8v-2Zm0 4h5v2H8v-2Z"/>',
    mistake: '<path d="M12 2 1 21h22L12 2Zm-1 7h2v6h-2V9Zm0 8h2v2h-2v-2Z"/>',
    book: '<path d="M4 4h9a3 3 0 0 1 3 3v13H7a3 3 0 0 0-3 3V4Zm16 0h-2v16h2V4Z"/>',
    course: '<path d="M4 5h16v14H4V5Zm2 2v10h12V7H6Zm2 2h8v2H8V9Zm0 4h8v2H8v-2Z"/>',
    card: '<path d="M3 6h18v12H3V6Zm2 2v8h14V8H5Zm1 5h5v2H6v-2Z"/>',
    score: '<path d="M12 2 1 21h22L12 2Z"/>',
    clock: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5h-2v6l5 3 1-1.7-4-2.3V7Z"/>',
    audio: '<path d="M4 9v6h4l5 4V5L8 9H4Zm12.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4Z"/>',
    read: '<path d="M4 4h16v16H4V4Zm2 2v12h12V6H6Zm2 2h8v2H8V8Zm0 4h8v2H8v-2Z"/>',
    chat: '<path d="M4 4h16v12H8l-4 4V4Zm3 3v2h10V7H7Zm0 4v2h7v-2H7Z"/>',
    pic: '<path d="M4 4h16v16H4V4Zm2 2v9l3.5-3.5 2.5 2.5 3-3 3 3V6H6Zm9 3a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/>',
    warning: '<path d="M12 2 1 21h22L12 2Zm-1 7h2v6h-2V9Zm0 8h2v2h-2v-2Z"/>',
    info: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15h-2v-6h2v6Zm0-8h-2V7h2v2Z"/>',
    refresh: '<path d="M17.6 6.4A8 8 0 1 0 20 12h-2a6 6 0 1 1-1.8-4.3L13 11h7V4l-2.4 2.4Z"/>',
    play: '<path d="M8 5v14l11-7L8 5Z"/>',
    lock: '<path d="M6 10V7a6 6 0 1 1 12 0v3h1v11H5V10h1Zm2 0h8V7a4 4 0 0 0-8 0v3Z"/>',
  };
  return `<svg viewBox="0 0 24 24">${icons[name] || icons.info}</svg>`;
}
function toast(message, timeout = 2600) {
  const node = document.getElementById('toast');
  node.textContent = message;
  node.classList.remove('hidden');
  clearTimeout(S.toastTimer);
  S.toastTimer = setTimeout(() => node.classList.add('hidden'), timeout);
}
function openModal(title, bodyHtml, footHtml = '') {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = bodyHtml;
  document.getElementById('modalFoot').innerHTML = footHtml || '<button class="btn" data-action="modal-close">知道了</button>';
  document.getElementById('modal').classList.remove('hidden');
}
function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}
function loadingHtml(text = '正在加载…') {
  return `<div class="boot-loading"><div class="spinner"></div><div>${esc(text)}</div></div>`;
}
function errorBanner(message, detail) {
  const hint = detail && detail.hint ? `<div class="small" style="margin-top:6px">${esc(detail.hint)}</div>` : '';
  const code = detail && detail.code ? ` <span class="tiny muted">（code ${esc(detail.code)}）</span>` : '';
  return `<div class="notice notice-danger error-banner">${svgIcon('warning')}<div><b>请求失败：</b>${esc(message)}${code}${hint}</div></div>`;
}
function notice(kind, html) {
  const icons = { info: 'info', warn: 'warning', danger: 'warning', ok: 'info' };
  return `<div class="notice notice-${kind}">${svgIcon(icons[kind] || 'info')}<div>${html}</div></div>`;
}

/* ------------------------------------------------------------------ *
 * API
 * ------------------------------------------------------------------ */
class ApiError extends Error {
  constructor(message, detail, status) {
    super(message);
    this.detail = detail || {};
    this.status = status;
  }
}
async function api(path, options = {}) {
  const opts = Object.assign({ headers: {} }, options);
  if (opts.body && !opts.headers['Content-Type']) opts.headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(path, opts);
  } catch (err) {
    throw new ApiError('无法连接本地后端（server.py 是否在运行？）', { message: String(err) }, 0);
  }
  let payload = null;
  const text = await response.text();
  try { payload = text ? JSON.parse(text) : {}; } catch (err) {
    throw new ApiError(`后端返回了非 JSON 响应（HTTP ${response.status}）`, { message: text.slice(0, 300) }, response.status);
  }
  if (!response.ok || payload.ok === false) {
    const detail = payload.error || { message: `HTTP ${response.status}` };
    throw new ApiError(detail.message || `HTTP ${response.status}`, detail, response.status);
  }
  return payload.data !== undefined ? payload.data : payload;
}

/* ------------------------------------------------------------------ *
 * 外壳：状态、时钟、导航
 * ------------------------------------------------------------------ */
function applyStatus(status) {
  S.status = status;
  const chip = document.getElementById('userChip');
  const avatar = document.getElementById('userAvatar');
  const name = document.getElementById('userName');
  const sub = document.getElementById('userSub');
  if (status && status.loggedIn && status.user) {
    const user = status.user;
    name.textContent = user.name || '已登录';
    sub.textContent = [user.grade_name, user.class_name].filter(Boolean).join(' · ') || (user.phone || '已登录');
    if (user.cover) {
      avatar.innerHTML = `<img src="${esc(user.cover)}" alt="" onerror="this.remove()">`;
    } else {
      avatar.textContent = (user.name || 'E').slice(0, 1);
    }
    chip.title = `${user.name || ''} · 点击查看账号信息`;
  } else {
    name.textContent = '未登录';
    sub.textContent = '请先登录';
    avatar.textContent = '?';
    chip.title = '未登录';
  }
  const server = status && status.serverTime;
  if (server && num(server.time_stamp)) {
    S.clockOffset = num(server.time_stamp) * 1000 - Date.now();
  }
  tickClock();
}
function tickClock() {
  const node = document.getElementById('serverClock');
  if (!node) return;
  const d = new Date(Date.now() + S.clockOffset);
  const p = (x) => String(x).padStart(2, '0');
  node.textContent = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  node.title = `服务端时间 ${d.toLocaleString('zh-CN')}（来自 /api/status）`;
}
setInterval(tickClock, 1000);

function markNav(routeName) {
  S.currentRoute = routeName;
  document.querySelectorAll('.nav-item[data-route]').forEach((node) => {
    node.classList.toggle('active', node.dataset.route === routeName);
  });
}
function setView(html) {
  const node = view();
  node.innerHTML = html;
  node.scrollTop = 0;
}
function beginRender() {
  S.renderToken = (S.renderToken || 0) + 1;
  return S.renderToken;
}
function isStale(token) {
  return token !== S.renderToken;
}
function authLost(err) {
  S.status = Object.assign({}, S.status, { loggedIn: false });
  S.loginError = err.message;
  renderLogin(S.status, err.message);
}

/* ------------------------------------------------------------------ *
 * 路由
 * ------------------------------------------------------------------ */
function parseHash() {
  const raw = location.hash || '#/home';
  const [pathPart, queryPart] = raw.replace(/^#/, '').split('?');
  const segments = pathPart.split('/').filter(Boolean).map(decodeURIComponent);
  const params = new URLSearchParams(queryPart || '');
  return { segments, params, raw };
}
function navigate(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}
async function route() {
  if (!S.status || !S.status.loggedIn) {
    renderLogin(S.status, S.loginError);
    return;
  }
  const { segments, params } = parseHash();
  const name = segments[0] || 'home';
  markNav(name === 'homework' || name === 'practice' || name === 'sets' ? (segments[0] === 'sets' ? 'expand' : 'homework') : name);
  try {
    if (name === 'home' || segments.length === 0) return renderHome();
    if (name === 'expand') return renderExpand();
    if (name === 'homework') return renderHomework(params.get('tab') || 'todo');
    if (name === 'homeworkDetail') return renderHomeworkDetail(segments[1]);
    if (name === 'setDetail') return renderSetDetail(segments[1], segments[2]);
    if (name === 'practice') return renderPractice(segments[1], segments[2], segments[3]);
    if (name === 'sets') return renderSets(segments[1] || '1', params.get('q') || '', Number(params.get('offset') || 0));
    if (name === 'courses') return renderCourses(params.get('book') || '', params.get('unit') || '');
    if (name === 'mistakes') return renderMistakes();
    if (name === 'mistake') return renderMistakeDetail(segments[1]);
    if (name === 'words') return renderWords();
    if (name === 'ecards') return renderEcards();
    if (name === 'config') return renderConfig();
    if (name === 'about') return renderAbout();
    if (name === 'login') return renderLogin(S.status, null);
    setView(`<div class="empty"><div class="empty-ico">🧭</div><p>未知页面：${esc(location.hash)}</p><p><a class="btn" href="#/home">返回首页</a></p></div>`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      S.status.loggedIn = false;
      S.loginError = err.message;
      renderLogin(S.status, err.message);
      return;
    }
    setView(errorBanner(err.message || '页面渲染失败', err.detail) + `<button class="btn" data-action="refresh">重试</button>`);
  }
}
window.addEventListener('hashchange', route);

/* ------------------------------------------------------------------ *
 * 登录页
 * ------------------------------------------------------------------ */
function renderLogin(status, message) {
  markNav('');
  const secrets = (status && status.secrets) || {};
  const user = status && status.user;
  const authError = message || (status && status.authError && status.authError.message) || '';
  const hint = status && status.authError && status.authError.hint;
  setView(`
    <div class="login-wrap">
      <div class="login-hero">
        <h1>${user ? '重新登录 E 听说参考客户端' : '登录 E 听说参考客户端'}</h1>
        <p>本客户端只调用真实只读接口，凭据从本机 <span class="mono">secrets/</span> 读取，不会写入代码目录。<br>
           当前官方客户端版本 V5.7.9 · 参考实现 ${esc((status && status.version) || '')}</p>
      </div>
      ${authError ? `<div class="notice notice-danger login-error">${svgIcon('warning')}<div><b>${esc(authError)}</b>${hint ? `<div class="small" style="margin-top:5px">${esc(hint)}</div>` : ''}</div></div>` : ''}
      <div class="login-grid">
        <div class="card login-card">
          <h3>${svgIcon('lock')} 本机账号登录</h3>
          <p>读取 <span class="mono">secrets/account.json</span> 的 phone / password，按原作登录接口
             <span class="mono">user/login</span> 现场 AES 加密并签名。</p>
          <div class="file-state">
            <span class="badge ${secrets.accountFileExists ? 'badge-green' : 'badge-red'}">${secrets.accountFileExists ? '账号文件已检测到' : '未检测到账号文件'}</span>
          </div>
          <button class="btn btn-primary" data-action="login" data-mode="account" ${secrets.accountFileExists ? '' : 'disabled'}>使用本机账号登录</button>
          <div class="tiny muted">密码只在本机后端内存中使用，不返回浏览器。</div>
        </div>
        <div class="card login-card">
          <h3>${svgIcon('refresh')} 官方客户端 token</h3>
          <p>读取 <span class="mono">secrets/app_token.txt</span> 中官方客户端当前 token，直接复用现有登录态，
             不触发新登录，最不容易互踢。</p>
          <div class="file-state">
            <span class="badge ${secrets.appTokenFileExists ? 'badge-green' : 'badge-red'}">${secrets.appTokenFileExists ? 'token 文件已检测到' : '未检测到 token 文件'}</span>
          </div>
          <button class="btn btn-primary" data-action="login" data-mode="token-file" ${secrets.appTokenFileExists ? '' : 'disabled'}>使用官方 token</button>
          <div class="tiny muted">官方客户端运行时单会话会互踢，建议先退出官方客户端。</div>
        </div>
        <div class="card login-card">
          <h3>${svgIcon('score')} 粘贴 token</h3>
          <p>如果已有其它有效 token，可粘贴到下方。token 只保存到 <span class="mono">reimpl/.state/token.json</span>（已 gitignore）。</p>
          <textarea class="login-input" id="pasteToken" placeholder="eyJ0eXAiOiJKV1Q...（160 字符 JWT）" spellcheck="false"></textarea>
          <button class="btn" data-action="login" data-mode="token-paste">校验并使用该 token</button>
        </div>
      </div>
      <div class="login-note">
        ${notice('warn', `<b>单会话限制：</b>官方客户端在运行时，新的 <span class="mono">user/login</span> 可能返回 <span class="mono">code 20004</span>（账号已在别处登录），或把官方客户端顶下线。验收测试建议先退出官方客户端；否则优先使用 <span class="mono">app_token.txt</span> 复用现有会话。`)}
      </div>
      <div class="login-note">
        ${notice('info', `<b>未实现能力：</b>录音、ISE 评测、考试提交、OSS 上传、自动更新器均未实现；页面会明确标注，不伪造分数。`)}
      </div>
    </div>
  `);
  if (status && status.secrets) {
    setTimeout(() => {
      S.status = status;
      applyStatus(Object.assign({}, status, { loggedIn: !!(status && status.loggedIn) }));
    }, 0);
  }
}

async function doLogin(mode, button) {
  if (S.busy) return;
  const payload = { mode: mode === 'account' ? 'account' : 'token' };
  if (mode === 'token-paste') {
    const node = document.getElementById('pasteToken');
    const token = (node && node.value || '').trim();
    if (!token) { toast('请先粘贴 token'); return; }
    payload.token = token;
  }
  S.busy = true;
  if (button) { button.disabled = true; button.dataset.oldText = button.textContent; button.textContent = '登录中…'; }
  try {
    const status = await api('/api/login', { method: 'POST', body: JSON.stringify(payload) });
    S.loginError = null;
    S.status = status;
    S.home = null; S.modules = null; S.mistakes = null; S.ecards = null; S.config = null;
    S.detailCache = {};
    applyStatus(status);
    toast('登录成功');
    if ((location.hash || '') === '' || location.hash === '#/login') location.hash = '#/home';
    route();
  } catch (err) {
    S.loginError = err.message;
    const detail = err.detail || {};
    openModal('登录失败', `
      <p><b>${esc(err.message)}</b></p>
      ${detail.code ? `<p class="small muted">接口 code：${esc(detail.code)}</p>` : ''}
      ${detail.hint ? `<div class="notice notice-warn">${svgIcon('warning')}<div>${esc(detail.hint)}</div></div>` : ''}
      ${detail.route ? `<p class="tiny muted">route: ${esc(detail.route)}</p>` : ''}
    `);
    if (S.status) renderLogin(S.status, err.message);
  } finally {
    S.busy = false;
    if (button) {
      button.disabled = false;
      if (button.dataset.oldText) button.textContent = button.dataset.oldText;
    }
  }
}

/* ------------------------------------------------------------------ *
 * 首页
 * ------------------------------------------------------------------ */
async function renderHome() {
  markNav('home');
  const token = beginRender();
  if (!S.home) setView(loadingHtml('正在聚合首页数据（user/info · homework/list · mistake/summary …）'));
  try {
    const data = await api('/api/home');
    if (isStale(token)) return;
    S.home = data;
    S.modules = data.modules || null;
    paintHome(data);
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail) + `<button class="btn" data-action="refresh">重试</button>`);
  }
}
function statsCard(opts) {
  return `
    <div class="card stat-card ${opts.cls || ''}" ${opts.href ? `data-href="${esc(opts.href)}"` : ''}>
      <div class="stat-ico">${svgIcon(opts.icon)}</div>
      <div class="stat-label">${esc(opts.label)}</div>
      <div class="stat-value">${opts.value}${opts.unit ? `<small>${esc(opts.unit)}</small>` : ''}</div>
      <div class="stat-sub">${opts.sub || ''}</div>
    </div>`;
}
function paintHome(data) {
  const user = data.user || {};
  const hw = data.homework || { counts: {}, todo: [], done: [] };
  const modules = (data.modules && data.modules.columns) || [];
  const mistakes = (data.mistakes && data.mistakes.summary) || {};
  const audioMistakes = (mistakes.to_correct_count || {}).audio || 0;
  const rwMistakes = (mistakes.to_correct_count || {}).read_write || 0;
  const hour = new Date(Date.now() + S.clockOffset).getHours();
  const greeting = hour < 6 ? '夜深了' : hour < 12 ? '上午好' : hour < 18 ? '下午好' : '晚上好';
  const moduleClass = { 1: '', 12: 'm-green', 88: 'm-orange' };
  const moduleIcon = { 1: 'audio', 12: 'read', 88: 'play' };
  const errorList = (data.errors || []).map((e) => `<li>${esc(e.scope)}：${esc(e.message)}</li>`).join('');
  setView(`
    <div class="hero-card">
      <h1>${greeting}，${esc(user.name || '同学')}</h1>
      <p>${esc([user.grade_name, user.school_year_name, user.city_name].filter(Boolean).join(' · ') || '欢迎使用 E 听说参考客户端')}</p>
      <div class="hero-meta">
        <span>E 卡：${esc((data.ecard && data.ecard.number) || '未绑定')}</span>
        <span>有效期至 ${esc((data.ecard && data.ecard.expire_time) || '—')}</span>
        <span>服务端时间 ${esc((data.serverTime && data.serverTime.date) || '—')}</span>
      </div>
      <div class="hero-actions">
        <a class="btn" href="#/homework">查看班级练习 →</a>
      </div>
    </div>

    ${errorList ? notice('warn', `<b>部分接口未返回：</b><ul class="small" style="margin:6px 0 0 18px">${errorList}</ul>`) : ''}

    <div class="grid grid-3">
      ${statsCard({
        icon: 'score', label: '预测分', cls: 'c-violet',
        value: '—', sub: '原作成长/预测分接口未开放，<br>参考客户端不伪造分数',
      })}
      ${statsCard({
        icon: 'homework', label: '待完成练习', cls: 'c-orange',
        value: String((hw.counts || {}).todo || 0), unit: '份',
        sub: `已完成 ${(hw.counts || {}).done || 0} · 已逾期 ${(hw.counts || {}).overtime || 0}`,
        href: '#/homework?tab=todo',
      })}
      ${statsCard({
        icon: 'mistake', label: '错题本', cls: 'c-green',
        value: String(audioMistakes + rwMistakes), unit: '题',
        sub: `听说 ${audioMistakes} · 读写 ${rwMistakes}`,
        href: '#/mistakes',
      })}
    </div>

    <div class="section">
      <div class="section-head">
        <div class="section-title"><span class="bar"></span>专项模拟</div>
        <a class="card-more" href="#/expand">能力拓展 →</a>
      </div>
      <div class="grid grid-3">
        ${(modules.length ? modules : [
          { id: 1, name: '听说模拟', count: '—' },
          { id: 12, name: '读写模拟', count: '—' },
          { id: 88, name: '听力模拟', count: '—' },
        ]).map((m) => `
          <div class="card module-card ${moduleClass[m.id] || ''}" data-href="#/sets/${m.id}">
            <div class="module-top">
              <div class="module-ico">${svgIcon(moduleIcon[m.id] || 'audio')}</div>
              <div>
                <div class="module-name">${esc(m.name)}</div>
                <div class="module-sub">点击浏览套卷目录</div>
              </div>
            </div>
            <div class="module-count">${fmtNum(m.count, 0)}<small>套试卷</small></div>
            <div class="module-bar"><i style="width:${Math.min(100, Number(m.count) > 0 ? Math.max(6, Number(m.complete_count || 0) / Number(m.count) * 100) : 0)}%"></i></div>
            <div class="tiny muted">已完成 ${fmtNum(m.complete_count, 0)} 套 · 均为真实接口计数</div>
          </div>`).join('')}
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <div class="section-title"><span class="bar"></span>同步课程</div>
        <a class="card-more" href="#/courses">教材 / 单元 / 模块 →</a>
      </div>
      <div class="card card-pad">
        <div class="row-between wrap" style="gap:12px">
          <div>
            <div style="font-weight:700">教材同步练习</div>
            <div class="small muted" style="margin-top:4px">按教材 → 单元 → 模块浏览同步课程目录（真实 g/resource、g/set 接口）</div>
          </div>
          <a class="btn" href="#/courses">选择教材</a>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-head">
        <div class="section-title"><span class="bar"></span>班级练习</div>
        <a class="card-more" href="#/homework">全部练习 →</a>
      </div>
      <div id="homeHomework">
        ${(hw.todo && hw.todo.length) ? hw.todo.slice(0, 3).map(homeworkCardHtml).join('') : '<div class="empty"><div class="empty-ico">🎉</div><p>暂无待完成练习</p><p class="small">已完成的历史练习可在「班级练习 → 已完成」查看</p></div>'}
      </div>
    </div>

    ${(data.advertisements && data.advertisements.length) ? `
      <div class="section">
        <div class="section-head"><div class="section-title"><span class="bar"></span>推荐</div></div>
        <div class="grid grid-auto">${data.advertisements.map((ad) => `
          <div class="card card-pad">
            ${ad.image ? `<img src="${esc(ad.image)}" alt="" style="max-width:100%;border-radius:10px;margin-bottom:8px">` : ''}
            <div style="font-weight:600">${esc(ad.title || ad.name || '推荐内容')}</div>
            <div class="small muted" style="margin-top:4px">${esc(ad.desc || '')}</div>
          </div>`).join('')}</div>
      </div>` : ''}

    ${(data.announcement && (data.announcement.title || data.announcement.detail)) ? notice('info', `<b>公告：</b>${esc(data.announcement.title || '')}<div class="small">${rich(data.announcement.detail || '')}</div>`) : ''}

    <div class="section">${notImplementedNotice()}</div>
  `);
}
function notImplementedNotice() {
  return notice('warn', `<b>参考客户端未实现：</b>录音、ISE/AI 评测、考试提交、OSS 上传、自动更新器。所有页面只展示真实只读数据，不伪造分数与完成状态。`);
}
function homeworkCardHtml(item) {
  const phase = item.phase || 'todo';
  const structure = item.structure || [];
  const totalQuestions = structure.reduce((sum, st) => sum + (st.contents || []).length, 0);
  const point = num(item.point);
  const total = num(item.total_point);
  const complete = num(item.complete) || 0;
  const href = `#/homeworkDetail/${encodeURIComponent(item.id)}`;
  return `
    <div class="card hw-card ${phase === 'done' ? 'is-done' : phase === 'overtime' ? 'is-overtime' : ''}" data-href="${href}">
      <div class="hw-icon">${svgIcon('homework')}</div>
      <div class="hw-main">
        <div class="hw-name">${esc(item.name || item.set_name || '未命名练习')}</div>
        <div class="hw-sub">${esc(item.set_name || '')}</div>
        <div class="hw-meta">
          <span class="chip">${esc(item.first_column_name || '练习')}</span>
          <span class="chip">${totalQuestions} 道子题</span>
          ${item.set_module_name ? `<span class="chip">${esc(item.set_module_name)}</span>` : ''}
          ${item.difficulty_rate ? `<span class="chip">难度 <b>${fmtNum(item.difficulty_rate)}</b></span>` : ''}
          <span class="chip">截止 <b>${esc(fmtDate(item.end))}</b></span>
        </div>
      </div>
      <div class="hw-right">
        ${phaseBadge(phase)}
        <div class="hw-score">${point != null ? fmtNum(point) : '—'}<small> / ${total != null ? fmtNum(total) : '—'} 分</small></div>
        <div class="hw-progress" title="完成度"><i style="width:${Math.max(0, Math.min(100, complete))}%"></i></div>
        <div class="hw-deadline">完成度 ${pct(complete)}</div>
      </div>
    </div>`;
}

/* ------------------------------------------------------------------ *
 * 作业列表
 * ------------------------------------------------------------------ */
async function renderHomework(tab) {
  markNav('homework');
  const token = beginRender();
  setView(`
    <div class="page-head">
      <div>
        <div class="page-title">班级练习</div>
        <div class="page-sub">真实接口：g/homework/list（status=0/2/3）· 点击作业查看套卷与题目结构</div>
      </div>
      <div class="page-actions"><a class="btn" href="#/home">返回首页</a><button class="btn" data-action="refresh">刷新</button></div>
    </div>
    <div id="hwTabs"></div>
    <div id="hwList">${loadingHtml('正在读取作业列表…')}</div>
  `);
  try {
    const data = await api('/api/homework?tab=' + encodeURIComponent(tab) + '&limit=50');
    if (isStale(token)) return;
    const counts = data.counts || {};
    const tabs = [
      ['todo', '待完成', counts.todo || 0],
      ['done', '已完成', counts.done || 0],
      ['overtime', '已逾期', counts.overtime || 0],
      ['all', '全部', counts.all || 0],
    ];
    document.getElementById('hwTabs').innerHTML = `
      <div class="tabs">
        ${tabs.map(([key, label, count]) => `<button class="tab ${key === tab ? 'active' : ''}" data-action="hw-tab" data-tab="${key}">${label}<span class="cnt">${count}</span></button>`).join('')}
      </div>`;
    document.getElementById('hwList').innerHTML = data.items.length
      ? data.items.map((item) => homeworkCardHtml(Object.assign({ phase: tab }, item))).join('')
      : `<div class="empty"><div class="empty-ico">📭</div><p>${tab === 'done' ? '暂无已完成练习' : tab === 'overtime' ? '暂无逾期练习' : '暂无待完成练习'}</p></div>`;
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    const listNode = document.getElementById('hwList');
    if (listNode) listNode.innerHTML = errorBanner(err.message, err.detail) + `<button class="btn" data-action="refresh">重试</button>`;
  }
}

/* ------------------------------------------------------------------ *
 * 详情页
 * ------------------------------------------------------------------ */
async function loadDetail(cacheKey, url) {
  if (S.detailCache[cacheKey]) return S.detailCache[cacheKey];
  const data = await api(url);
  S.detailCache[cacheKey] = data;
  return data;
}
async function renderHomeworkDetail(id) {
  markNav('homework');
  const token = beginRender();
  setView(loadingHtml('正在读取作业详情与模板包…'));
  try {
    const detail = await loadDetail('hw:' + id, `/api/homework/${encodeURIComponent(id)}`);
    if (isStale(token)) return;
    paintDetail(detail, { kind: 'homework', cacheKey: 'hw:' + id });
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail) + `<a class="btn" href="#/homework">返回作业列表</a>`);
  }
}
async function renderSetDetail(column, id) {
  markNav('expand');
  const token = beginRender();
  setView(loadingHtml('正在读取套卷详情与模板包…'));
  try {
    const detail = await loadDetail(`set:${column}:${id}`, `/api/sets/detail?column_id=${encodeURIComponent(column)}&set_id=${encodeURIComponent(id)}`);
    if (isStale(token)) return;
    paintDetail(detail, { kind: 'set', column, cacheKey: `set:${column}:${id}` });
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail) + `<a class="btn" href="#/sets/${encodeURIComponent(column)}">返回套卷列表</a>`);
  }
}
function practiceRoute(detail, opts) {
  if (opts.kind === 'homework') return `#/practice/homework/${encodeURIComponent(detail.id)}`;
  return `#/practice/set/${encodeURIComponent(opts.column)}/${encodeURIComponent(detail.id)}`;
}
function paintDetail(detail, opts) {
  const totalQuestions = (detail.structure || []).reduce((sum, st) => sum + (st.contents || []).length, 0);
  const tpl = detail.template || {};
  const sections = tpl.sections || [];
  const back = opts.kind === 'homework' ? '#/homework' : `#/sets/${encodeURIComponent(opts.column)}`;
  const route = practiceRoute(detail, opts);
  const top = `
    <div class="crumb"><a href="${back}">${opts.kind === 'homework' ? '班级练习' : '套卷目录'}</a> / 详情</div>
    <div class="card detail-head">
      <div class="row-between wrap" style="align-items:flex-start">
        <div style="min-width:0">
          <h1 class="detail-title">${esc(detail.name || detail.set_name || '未命名')}</h1>
          <div class="detail-meta">
            ${phaseBadge(detail.phase || 'set')}
            <span class="badge badge-blue">${esc(detail.first_column_name || '练习')}</span>
            ${detail.set_module_name ? `<span class="badge badge-gray">${esc(detail.set_module_name)}</span>` : ''}
            ${detail.engine_area ? `<span class="badge badge-gray">考区 ${esc(detail.engine_area)}</span>` : ''}
            <span class="badge badge-gray">${totalQuestions} 道子题</span>
          </div>
          ${detail.set_name && detail.set_name !== detail.name ? `<div class="small muted" style="margin-top:9px;white-space:pre-line">${esc(detail.set_name)}</div>` : ''}
        </div>
        <div class="page-actions">
          ${totalQuestions ? `<a class="btn btn-primary" href="${route}">开始练习（只读）</a>` : ''}
          <button class="btn" data-action="refresh">刷新</button>
        </div>
      </div>
      <div class="detail-grid">
        <div class="detail-stat"><div class="k">总分</div><div class="v">${fmtNum(detail.total_point)}</div></div>
        <div class="detail-stat"><div class="k">当前得分</div><div class="v">${fmtNum(detail.point)}</div></div>
        <div class="detail-stat"><div class="k">完成度</div><div class="v">${pct(detail.complete)}</div></div>
        <div class="detail-stat"><div class="k">练习用时</div><div class="v">${esc(fmtDuration(detail.use_time))}</div></div>
        <div class="detail-stat"><div class="k">开始时间</div><div class="v" style="font-size:13px">${esc(fmtDate(detail.begin))}</div></div>
        <div class="detail-stat"><div class="k">截止时间</div><div class="v" style="font-size:13px">${esc(fmtDate(detail.end))}</div></div>
        <div class="detail-stat"><div class="k">练习次数</div><div class="v">${fmtNum(detail.practise_count, 0)}</div></div>
        <div class="detail-stat"><div class="k">难度</div><div class="v">${fmtNum(detail.difficulty_rate)}</div></div>
      </div>
    </div>`;
  const templateHtml = sections.length ? `
    <div class="card card-pad" style="margin-bottom:16px">
      <div class="card-head"><div class="card-title"><span class="dot"></span>试卷结构（template ${esc(tpl.template_id || '')}）</div><span class="tiny muted">来自 template_*.zip / res.json</span></div>
      <div class="timeline">
        ${sections.map((sec, i) => `
          <div class="tl-item">
            <div class="tl-order">${i + 1}</div>
            <div class="tl-name">${esc(sec.name)}</div>
            <div class="tl-sub">${esc(sec.count)} 题 · ${esc(sec.score)} 分<br>${esc(sec.collect)}</div>
          </div>`).join('')}
      </div>
      ${tpl.set_intro ? `<div class="small muted" style="margin-top:8px">${rich(tpl.set_intro)}</div>` : ''}
    </div>` : (tpl.error ? notice('warn', `模板包读取失败：${esc(tpl.error.message || '')}`) : '');
  const structHtml = (detail.structure || []).length ? detail.structure.map((st, si) => {
    const contents = st.contents || [];
    return `
      <div class="card struct-card">
        <div class="struct-head">
          <div class="struct-title">${esc(st.set_name || '套卷')} <span class="tiny muted">set_id ${esc(st.set_id || '')}</span></div>
          <div class="row">
            <span class="chip">模板 ${esc(st.template.id || '—')}</span>
            <span class="chip">${contents.length} 题</span>
          </div>
        </div>
        ${contents.length ? contents.map((c, ci) => `
          <div class="question-row" data-action="open-question" data-kind="${opts.kind}" data-column="${esc(opts.column || '')}" data-id="${esc(detail.id)}" data-index="${si}:${ci}">
            <div class="q-index">${esc(c.code_id || ci + 1)}</div>
            <div style="min-width:0">
              <div class="q-name">${esc(c.group_name || c.first_type_name || '题目')}</div>
              <div class="q-sub">stid ${esc(c.stid)} · ${fmtNum(c.size / 1024, 0)} KB · 资源包 ${esc((c.zip_name || '').slice(0, 10))}…</div>
            </div>
            <div class="q-right">
              <span class="badge badge-blue">打开练习</span>
            </div>
          </div>`).join('') : `<div class="empty" style="margin:16px"><p>该套卷没有可渲染的 content 包结构</p>${notice('warn', '读写模拟的 rw_data 只包含目录信息，不含 content 包，参考客户端未实现读写题型渲染。')}</div>`}
      </div>`;
  }).join('') : `<div class="empty"><p>没有题目结构数据</p></div>`;
  setView(top + templateHtml + `
    <div class="section-head"><div class="section-title"><span class="bar"></span>题目列表</div><span class="tiny muted">点击任一题进入练习页；资源包首次打开时从 cdnsubject 下载并本地 ZipCrypto 解密</span></div>
    ${structHtml}
    <div class="section">${notImplementedNotice()}</div>
  `);
}

/* ------------------------------------------------------------------ *
 * 套卷目录 / 能力拓展
 * ------------------------------------------------------------------ */
async function renderExpand() {
  markNav('expand');
  const token = beginRender();
  setView(loadingHtml('正在读取能力拓展配置…'));
  try {
    const modules = await api('/api/modules');
    if (isStale(token)) return;
    S.modules = modules;
    const expand = modules.expand || {};
    const entries = Object.keys(expand).filter((k) => typeof expand[k] !== 'object');
    const enabled = entries.filter((k) => Number(expand[k]) === 1);
    const disabled = entries.filter((k) => Number(expand[k]) !== 1);
    setView(`
      <div class="page-head">
        <div><div class="page-title">能力拓展</div><div class="page-sub">真实接口：g/set/column-v2（模拟类目计数）· g/resource/expand-module（功能开关）</div></div>
        <div class="page-actions"><a class="btn" href="#/home">返回首页</a></div>
      </div>
      <div class="grid grid-3" style="margin-bottom:20px">
        ${(modules.columns || []).map((m) => `
          <div class="card module-card" data-href="#/sets/${m.id}">
            <div class="module-top">
              <div class="module-ico">${svgIcon(m.id === 12 ? 'read' : m.id === 88 ? 'play' : 'audio')}</div>
              <div><div class="module-name">${esc(m.name)}</div><div class="module-sub">浏览套卷目录</div></div>
            </div>
            <div class="module-count">${fmtNum(m.count, 0)}<small>套试卷</small></div>
            <div class="tiny muted">已完成 ${fmtNum(m.complete_count, 0)} 套</div>
          </div>`).join('')}
      </div>
      <div class="card card-pad" style="margin-bottom:16px">
        <div class="card-head"><div class="card-title"><span class="dot"></span>功能开关（expand-module）</div><span class="tiny muted">共 ${entries.length} 项，开启 ${enabled.length} 项</span></div>
        <div class="module-chips">
          ${entries.map((key) => `
            <div class="module-chip">
              <div><div class="name">${esc(FEATURE_NAMES[key] || key)}</div><div class="cnt mono">${esc(key)}</div></div>
              <span class="badge ${Number(expand[key]) === 1 ? 'badge-green' : 'badge-gray'}">${Number(expand[key]) === 1 ? '开启' : '关闭'}</span>
            </div>`).join('')}
        </div>
      </div>
      ${notice('info', `专项练习（tag_id=2）的类目计数：${esc((modules.expand && modules.expand.__special) || '见首页/套卷目录')}。参考客户端只实现「模拟」套卷目录浏览，专项/同步课程的试卷列表需要额外接口，未实现跳转。`)}
    `);
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail));
  }
}

async function renderSets(column, query, offset) {
  markNav('expand');
  const token = beginRender();
  const name = COLUMN_NAMES[column] || `栏目 ${column}`;
  setView(`
    <div class="crumb"><a href="#/expand">能力拓展</a> / ${esc(name)}</div>
    <div class="page-head">
      <div><div class="page-title">${esc(name)}</div><div class="page-sub">真实接口：g/set/list（first_column_id=[${esc(column)}]）· 点击套卷查看题目结构</div></div>
      <div class="page-actions"><a class="btn" href="#/expand">返回</a><button class="btn" data-action="refresh">刷新</button></div>
    </div>
    <div class="config-toolbar">
      <input class="search-input" id="setSearch" placeholder="搜索套卷名称…" value="${esc(query)}">
      <button class="btn" data-action="sets-search" data-column="${esc(column)}">搜索</button>
      <span class="chip">共 <b id="setTotal">—</b> 套</span>
    </div>
    <div id="setList">${loadingHtml('正在读取套卷目录…')}</div>
    <div id="setPager"></div>
  `);
  try {
    const data = await api(`/api/sets?column_id=${encodeURIComponent(column)}&offset=${offset}&limit=24&q=${encodeURIComponent(query)}`);
    if (isStale(token)) return;
    document.getElementById('setTotal').textContent = data.total;
    const list = document.getElementById('setList');
    if (!data.items.length) {
      list.innerHTML = `<div class="empty"><div class="empty-ico">📚</div><p>没有找到套卷</p></div>`;
    } else {
      list.innerHTML = data.items.map((item) => {
        const href = item.structure && item.structure.length
          ? `#/setDetail/${encodeURIComponent(column)}/${encodeURIComponent(item.id)}`
          : null;
        return `
          <div class="card hw-card" ${href ? `data-href="${href}"` : `data-action="set-no-struct"`}>
            <div class="hw-icon">${svgIcon('book')}</div>
            <div class="hw-main">
              <div class="hw-name">${esc(item.name || item.set_name)}</div>
              <div class="hw-sub">${esc(item.column || item.first_column_name || '')}</div>
              <div class="hw-meta">
                ${item.create ? `<span class="chip">${esc(item.create)}</span>` : ''}
                ${item.difficulty_rate != null ? `<span class="chip">难度 <b>${fmtNum(item.difficulty_rate)}</b></span>` : ''}
                ${item.structure && item.structure.length ? `<span class="chip">${item.structure.reduce((s, x) => s + (x.contents || []).length, 0)} 道子题</span>` : '<span class="chip">目录信息</span>'}
                ${item.rw ? '<span class="badge badge-orange">读写结构未实现</span>' : ''}
              </div>
            </div>
            <div class="hw-right"><span class="badge badge-blue">${item.structure && item.structure.length ? '查看详情' : '仅目录'}</span></div>
          </div>`;
      }).join('');
    }
    const totalPages = Math.max(1, Math.ceil(data.total / 24));
    const current = Math.floor(offset / 24) + 1;
    document.getElementById('setPager').innerHTML = totalPages > 1 ? `
      <div class="pager">
        <span class="tiny muted">第 ${current} / ${totalPages} 页</span>
        <div class="pages">
          <button data-action="sets-page" data-column="${esc(column)}" data-offset="${Math.max(0, offset - 24)}" data-q="${esc(query)}" ${offset <= 0 ? 'disabled' : ''}>上一页</button>
          <button data-action="sets-page" data-column="${esc(column)}" data-offset="${offset + 24}" data-q="${esc(query)}" ${offset + 24 >= data.total ? 'disabled' : ''}>下一页</button>
        </div>
      </div>` : '';
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    const listNode = document.getElementById('setList');
    if (listNode) listNode.innerHTML = errorBanner(err.message, err.detail);
  }
}

/* ------------------------------------------------------------------ *
 * 同步课程
 * ------------------------------------------------------------------ */
async function renderCourses(bookId, unitId) {
  markNav('courses');
  const token = beginRender();
  setView(loadingHtml('正在读取教材 / 单元 / 模块…'));
  try {
    let url = '/api/courses';
    const params = new URLSearchParams();
    if (bookId) params.set('book_id', bookId);
    if (unitId) params.set('unit_id', unitId);
    if ([...params].length) url += '?' + params.toString();
    const data = await api(url);
    if (isStale(token)) return;
    S.courses = data;
    const books = data.grade_books || data.books || [];
    const units = data.units || [];
    const modules = data.modules || [];
    setView(`
      <div class="page-head">
        <div><div class="page-title">同步课程</div><div class="page-sub">真实接口：g/resource/grade-list、book-list、g/set/unit-list、g/set/module-list</div></div>
        <div class="page-actions"><a class="btn" href="#/home">返回首页</a><button class="btn" data-action="refresh">刷新</button></div>
      </div>
      <div class="card card-pad course-box">
        <div class="course-selects">
          <select class="select" id="bookSelect">
            ${books.map((b) => `<option value="${esc(b.id)}" ${String(b.id) === String(data.selected && data.selected.book_id) ? 'selected' : ''}>${esc(b.display_name || b.name)} · ${esc(b.grade_name || '')} · ${esc(b.term_name || '')}</option>`).join('')}
          </select>
          <span class="chip">资源版本 <b>${esc((data.selected && data.selected.resource_id) || '—')}</b></span>
          <span class="chip">共 <b>${books.length}</b> 本教材</span>
        </div>
        <div class="course-units">
          ${units.map((u) => `<button class="unit-chip ${String(u.unit_id) === String(data.selected_unit_id) ? 'active' : ''}" data-action="course-unit" data-book="${esc((data.selected && data.selected.book_id) || '')}" data-unit="${esc(u.unit_id)}">${esc(u.unit_name)}</button>`).join('') || '<span class="muted small">该教材暂无单元数据</span>'}
        </div>
        <div class="module-chips">
          ${modules.map((m) => `
            <div class="module-chip">
              <div>
                <div class="name">${esc(m.module_name)}</div>
                <div class="cnt">${fmtNum(m.module_set_count, 0)} 套 · 已完成 ${fmtNum(m.module_set_complete_count, 0)} 套 ${m.module_is_lock ? '· 🔒' : ''}</div>
              </div>
              <span class="badge ${m.module_is_lock ? 'badge-orange' : 'badge-green'}">${m.module_is_lock ? '未解锁' : '可练习'}</span>
            </div>`).join('') || '<span class="muted small">该单元暂无模块数据</span>'}
        </div>
        ${notice('info', '同步课程模块的套卷列表需要单元/模块级套卷接口（本次只读接口清单未覆盖），参考客户端只展示教材/单元/模块目录，不伪造套卷。')}
      </div>
      <div class="section">${notImplementedNotice()}</div>
    `);
    const bookSelect = document.getElementById('bookSelect');
    if (bookSelect) {
      bookSelect.addEventListener('change', () => {
        navigate(`#/courses?book=${encodeURIComponent(bookSelect.value)}`);
      });
    }
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail));
  }
}

/* ------------------------------------------------------------------ *
 * 练习页
 * ------------------------------------------------------------------ */
function practiceKey(kind, second, third) {
  return kind === 'homework' ? `hw:${second}` : `set:${second}:${third}`;
}
async function renderPractice(kind, second, third) {
  markNav('homework');
  const token = beginRender();
  const cacheKey = practiceKey(kind, second, third);
  setView(loadingHtml('正在准备练习页…'));
  try {
    let detail;
    if (S.detailCache[cacheKey]) detail = S.detailCache[cacheKey];
    else if (kind === 'homework') detail = await loadDetail(cacheKey, `/api/homework/${encodeURIComponent(second)}`);
    else detail = await loadDetail(cacheKey, `/api/sets/detail?column_id=${encodeURIComponent(second)}&set_id=${encodeURIComponent(third)}`);
    if (isStale(token)) return;
    const items = [];
    (detail.structure || []).forEach((st, si) => {
      (st.contents || []).forEach((c, ci) => {
        items.push({
          key: `${si}:${ci}`,
          structIndex: si,
          contentIndex: ci,
          stid: c.stid,
          zip: c.zip_name,
          group: c.group_name || c.first_type_name || '题目',
          codeId: c.code_id,
          setIndex: si,
        });
      });
    });
    if (!items.length) {
      setView(`<div class="empty"><p>该套卷没有可渲染的 content 包题目</p><p><a class="btn" href="#/homework">返回</a></p></div>`);
      return;
    }
    const startIndex = Math.max(0, Math.min(items.length - 1, S.pendingQuestion || Number(parseHash().params.get('q') || 0) || 0));
    S.pendingQuestion = 0;
    S.practice = {
      kind, second, third, cacheKey, detail, items,
      active: startIndex,
      loaded: {},
      loading: {},
      errors: {},
      answers: {},
    };
    paintPracticeShell();
    await loadPracticeQuestion(startIndex);
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail) + `<a class="btn" href="#/homework">返回</a>`);
  }
}
function paintPracticeShell() {
  const p = S.practice;
  const detail = p.detail;
  const back = p.kind === 'homework' ? `#/homeworkDetail/${encodeURIComponent(p.second)}` : `#/setDetail/${encodeURIComponent(p.second)}/${encodeURIComponent(p.third)}`;
  const totalQ = p.items.length;
  const groups = [];
  p.items.forEach((item, index) => {
    const label = item.group;
    if (!groups.length || groups[groups.length - 1].label !== label) groups.push({ label, start: index, count: 1 });
    else groups[groups.length - 1].count += 1;
  });
  setView(`
    <div class="crumb"><a href="${back}">${esc(detail.name || '')}</a> / 练习</div>
    <div class="page-head">
      <div>
        <div class="page-title">${esc(detail.name || '练习')}</div>
        <div class="page-sub">${esc(groups.map((g) => `${g.label} ×${g.count}`).join(' · '))}</div>
      </div>
      <div class="page-actions">
        <span class="badge badge-orange">只读参考模式</span>
        <a class="btn" href="${back}">返回详情</a>
      </div>
    </div>
    ${notice('warn', `<b>参考客户端未实现：</b>录音采集、ISE/AI 评测、作答提交、分数回写。这里只渲染从 content 包解密出的题干、示范音频、参考答案与解析；不会产生或伪造分数。`)}
    <div class="practice-layout" style="margin-top:14px">
      <div class="card q-rail">
        <div class="rail-head"><span>题目列表</span><span class="tiny muted">${totalQ} 题</span></div>
        <div class="rail-list">
          ${p.items.map((item, index) => `
            <div class="rail-item ${index === p.active ? 'active' : ''} ${p.loaded[item.stid] ? 'loaded' : ''}" data-action="practice-open" data-index="${index}">
              <span class="rail-dot"></span>
              <span class="ellipsis" style="min-width:0">${esc(item.codeId || '')} ${esc(item.group)}</span>
            </div>`).join('')}
        </div>
      </div>
      <div class="practice-main" id="practiceMain">${loadingHtml('正在读取题目资源包…')}</div>
    </div>
  `);
}
function updatePracticeRail() {
  const p = S.practice;
  if (!p) return;
  document.querySelectorAll('.rail-item').forEach((node, index) => {
    node.classList.toggle('active', index === p.active);
    node.classList.toggle('loaded', !!p.loaded[p.items[index].stid]);
  });
}
async function loadPracticeQuestion(index) {
  const p = S.practice;
  if (!p) return;
  p.active = Math.max(0, Math.min(p.items.length - 1, index));
  updatePracticeRail();
  const item = p.items[p.active];
  const main = document.getElementById('practiceMain');
  if (!main) return;
  if (p.loaded[item.stid]) { paintQuestion(); return; }
  if (p.loading[item.stid]) { main.innerHTML = loadingHtml('该题正在加载…'); return; }
  p.loading[item.stid] = true;
  main.innerHTML = loadingHtml(`正在下载并解密 content_${item.stid}.zip（首次较慢，之后走本地缓存）…`);
  try {
    const data = await api(`/api/content?stid=${encodeURIComponent(item.stid)}&zip=${encodeURIComponent(item.zip)}`);
    p.loaded[item.stid] = data;
    p.errors[item.stid] = null;
  } catch (err) {
    p.errors[item.stid] = err;
  } finally {
    p.loading[item.stid] = false;
  }
  if (p.loaded[item.stid]) {
    if (p.active === index) paintQuestion();
    else if (p.loaded[p.items[p.active].stid]) paintQuestion();
    else updatePracticeRail();
    // 预取下一题（不改变当前题），避免首次翻页等待
    const next = p.active + 1;
    if (next < p.items.length && !p.loaded[p.items[next].stid] && !p.loading[p.items[next].stid]) {
      setTimeout(() => { if (S.practice === p) prefetchPracticeQuestion(next); }, 400);
    }
  } else if (p.active === index) {
    main.innerHTML = errorBanner(p.errors[item.stid].message, p.errors[item.stid].detail)
      + `<button class="btn" data-action="practice-retry" data-index="${p.active}">重试</button>`;
  }
}
async function prefetchPracticeQuestion(index) {
  const p = S.practice;
  if (!p || index < 0 || index >= p.items.length) return;
  const item = p.items[index];
  if (p.loaded[item.stid] || p.loading[item.stid]) return;
  p.loading[item.stid] = true;
  try {
    p.loaded[item.stid] = await api(`/api/content?stid=${encodeURIComponent(item.stid)}&zip=${encodeURIComponent(item.zip)}`);
    p.errors[item.stid] = null;
    updatePracticeRail();
    if (p.active === index) paintQuestion();
  } catch (err) {
    p.errors[item.stid] = err;
  } finally {
    p.loading[item.stid] = false;
  }
}
function paintQuestion() {
  const p = S.practice;
  const main = document.getElementById('practiceMain');
  if (!p || !main) return;
  const item = p.items[p.active];
  const data = p.loaded[item.stid];
  if (!data) {
    main.innerHTML = loadingHtml('正在读取题目资源包…');
    return;
  }
  const type = (data.structure_type || '').split('.').pop() || 'unknown';
  main.innerHTML = `
    <div class="card q-card">
      <div class="q-card-head">
        <div class="q-card-title">${esc(item.codeId || '')} ${esc(item.group)} ${typeBadge(type)}</div>
        <div class="row">
          <span class="tiny muted">${p.active + 1} / ${p.items.length}</span>
        </div>
      </div>
      <div class="q-card-body">
        ${renderQuestionBody(data, type, p.active)}
        <div class="pkg-meta">
          资源包 content_${esc(item.stid)}.zip · ${esc(data.package && data.package.zip_name || '')}<br>
          大小 ${fmtNum((data.package && data.package.size || 0) / 1024, 0)} KB ·
          ZipCrypto ${data.package && data.package.encrypted ? '已加密（本地按包尾 336B 口令块解密）' : '未加密'} ·
          SHA-256 ${esc((data.package && data.package.sha256 || '').slice(0, 24))}…<br>
          来源 ${esc((data.package && data.package.url) || '')}
        </div>
      </div>
    </div>
    <div class="q-nav">
      <button class="btn" data-action="practice-prev" ${p.active <= 0 ? 'disabled' : ''}>← 上一题</button>
      <button class="btn btn-primary" data-action="practice-next" ${p.active >= p.items.length - 1 ? 'disabled' : ''}>下一题 →</button>
    </div>
  `;
}
function mediaUrl(data, filename) {
  if (!filename) return '';
  if (/^https?:\/\//i.test(filename)) return filename;
  const target = String(filename).replace(/\\/g, '/');
  const material = data.material || [];
  const found = material.find((m) => m.path === target)
    || material.find((m) => m.path.endsWith('/' + target))
    || material.find((m) => m.path.split('/').pop() === target.split('/').pop());
  return found && found.url ? found.url : '';
}
function audioBlock(src, label) {
  if (!src) return '';
  return `<div class="audio-row"><span class="audio-label">${esc(label || '音频')}</span><audio controls preload="none" src="${esc(src)}"></audio></div>`;
}
function answerToggle(uid, label = '显示答案与解析') {
  return `<button class="btn btn-sm" data-action="toggle-answer" data-target="ans-${esc(uid)}" style="margin-top:10px">${esc(label)}</button>`;
}
function stripPrefix(text) {
  return cleanText(text).replace(/^ets_th\d+\s*/i, '').replace(/^\d+\.\s*/, '');
}
function renderRead(data) {
  const info = (data.content2 && data.content2.info) || data.content.info || {};
  const audio = mediaUrl(data, info.audio);
  const analyze = lines(info.analyze);
  const translate = cleanText(info.translate);
  return `
    <div class="q-block"><div class="q-label">朗读原文</div><div class="q-text">${htmlOrDash(info.value)}</div></div>
    ${audio ? `<div class="q-block"><div class="q-label">示范音频</div>${audioBlock(audio, '示范')}</div>` : ''}
    ${translate ? `<div class="q-block"><div class="q-label">译文</div><div class="q-small">${rich(translate)}</div></div>` : ''}
    ${answerToggle('read-' + esc(data.stid))}
    <div class="answer-panel hidden" id="ans-read-${esc(data.stid)}">
      ${analyze.length ? `<div class="q-label">解析</div><ul class="answer-list">${analyze.map((x) => `<li>${rich(x)}</li>`).join('')}</ul>` : '<div class="muted small">该题没有解析文本。</div>'}
      ${notice('info', '朗读题在官方客户端由 ISE 引擎评分；参考客户端未实现录音与评测，不展示分数。')}
    </div>`;
}
function renderDialogue(data) {
  const info = (data.content2 && data.content2.info) || data.content.info || {};
  const questions = info.question || [];
  return questions.map((q, index) => {
    const ask = stripPrefix(q.ask);
    const audio = mediaUrl(data, q.askaudio || q.sucai || '');
    const stds = (q.std || []).map((x) => cleanText(x.value)).filter(Boolean);
    const keywords = String(q.keywords || '').split('|').map((x) => x.trim()).filter(Boolean);
    const uid = `dlg-${esc(data.stid)}-${index}`;
    return `
      <div class="q-block" style="border-bottom:1px dashed var(--line);padding-bottom:14px">
        <div class="q-label">第 ${index + 1} 题 · 听问句选答语</div>
        <div class="q-text">${ask ? rich(ask) : '<span class="muted">（题干在 info.json / ctrl.json 中）</span>'}</div>
        ${audio ? audioBlock(audio, '问句音频') : ''}
        ${answerToggle(uid, '显示参考答案 / 关键词')}
        <div class="answer-panel hidden" id="ans-${uid}">
          ${stds.length ? `<div class="q-label">参考答案（${stds.length} 条）</div><ul class="answer-list">${stds.slice(0, 12).map((x) => `<li>${rich(x)}</li>`).join('')}${stds.length > 12 ? `<li class="muted">…共 ${stds.length} 条</li>` : ''}</ul>` : '<div class="muted small">无参考答案文本。</div>'}
          ${keywords.length ? `<div class="q-label" style="margin-top:10px">评分关键词</div><div class="keyword-wrap">${keywords.slice(0, 26).map((k) => `<span class="keyword">${esc(k)}</span>`).join('')}</div>` : ''}
          ${q.analyze ? `<div class="q-label" style="margin-top:10px">解析</div><div class="q-answer-text">${rich(q.analyze)}</div>` : ''}
        </div>
      </div>`;
  }).join('') || '<div class="muted">该对话题没有 question 数据。</div>';
}
function renderPicture(data) {
  const info = (data.content2 && data.content2.info) || data.content.info || {};
  const audio = mediaUrl(data, info.audio);
  const image = mediaUrl(data, info.image);
  const stds = (info.std || []).map((x) => cleanText(x.value)).filter(Boolean);
  const keypoints = lines(info.keypoint);
  const uid = 'pic-' + esc(data.stid);
  return `
    ${info.value ? `<div class="q-block"><div class="q-label">题干 / 情景</div><div class="q-text">${rich(info.value)}</div></div>` : ''}
    ${info.topic ? `<div class="q-block"><span class="chip">话题 <b>${esc(info.topic)}</b></span></div>` : ''}
    ${image ? `<div class="q-block"><div class="q-label">图片</div><div class="img-box"><img src="${esc(image)}" alt="题目图片" loading="lazy"></div></div>` : ''}
    ${audio ? `<div class="q-block"><div class="q-label">示范音频</div>${audioBlock(audio, '示范')}</div>` : ''}
    ${answerToggle(uid, '显示范文 / 要点')}
    <div class="answer-panel hidden" id="ans-${uid}">
      ${stds.length ? `<div class="q-label">参考范文（${stds.length} 篇，展示前 3 篇）</div>${stds.slice(0, 3).map((x, i) => `<div class="ref-passage"><span class="num">${i + 1}.</span>${rich(x)}</div>`).join('')}` : ''}
      ${keypoints.length ? `<div class="q-label" style="margin-top:10px">要点</div><ul class="answer-list">${keypoints.map((x) => `<li>${rich(x)}</li>`).join('')}</ul>` : ''}
      ${info.analyze ? `<div class="q-label" style="margin-top:10px">解析</div><div class="q-answer-text">${rich(info.analyze)}</div>` : ''}
    </div>`;
}
function renderChoose(data) {
  const info = (data.content2 && data.content2.info) || data.content.info || {};
  const image = mediaUrl(data, info.st_pic || info.image);
  const xtlist = info.xtlist || [];
  return `
    ${info.st_nr ? `<div class="q-block"><div class="q-label">题目说明</div><div class="q-text">${rich(info.st_nr)}</div></div>` : ''}
    ${image ? `<div class="img-box"><img src="${esc(image)}" alt="题目图片" loading="lazy"></div>` : ''}
    ${xtlist.map((xt, index) => {
      const uid = `choose-${esc(data.stid)}-${index}`;
      const audio = mediaUrl(data, xt.xt_wj);
      const options = xt.xxlist || [];
      return `
        <div class="choose-q">
          <div class="stem">${esc(xt.xt_xh || index + 1)}. ${rich(stripPrefix(xt.xt_value))}</div>
          ${audio ? audioBlock(audio, '听力音频') : ''}
          <div class="choose-options">${options.map((opt) => `<span class="choose-opt" data-opt="${esc(opt.xx_mc)}">${esc(opt.xx_mc)}. ${esc(cleanText(opt.xx_nr) || cleanText(opt.xx_mc))}</span>`).join('')}</div>
          ${answerToggle(uid, '显示答案')}
          <div class="answer-panel hidden" id="ans-${uid}">
            <div class="q-answer-text"><b>答案：</b>${esc(stripPrefix(xt.answer) || '—')}${xt.xt_analy ? `<div style="margin-top:6px"><b>解析：</b>${rich(xt.xt_analy)}</div>` : ''}</div>
          </div>
        </div>`;
    }).join('') || '<div class="muted">该选择题没有 xtlist 数据。</div>'}
    ${notice('info', '听力/选择题为 bonus 渲染；官方客户端在此处会播放音频并记录作答，参考客户端不实现作答提交。')}`;
}
function renderQuestionBody(data, type, index) {
  if (type === 'read') return renderRead(data);
  if (type === 'dialogue') return renderDialogue(data);
  if (type === 'picture') return renderPicture(data);
  if (type === 'choose') return renderChoose(data);
  return `
    ${notice('warn', `未实现渲染的题型：<span class="mono">${esc(data.structure_type || 'unknown')}</span>。下面是 content.json 原始数据。`)}
    <pre class="code-block" style="max-height:420px;overflow:auto">${esc(JSON.stringify(data.content, null, 2))}</pre>`;
}

/* ------------------------------------------------------------------ *
 * 错题本
 * ------------------------------------------------------------------ */
async function renderMistakes() {
  markNav('mistakes');
  const token = beginRender();
  setView(loadingHtml('正在读取错题统计与列表…'));
  try {
    const data = await api('/api/mistakes');
    if (isStale(token)) return;
    S.mistakes = data;
    const summary = data.summary || {};
    const toCorrect = summary.to_correct_count || {};
    const corrected = summary.corrected_count || {};
    const rows = data.items || [];
    setView(`
      <div class="page-head">
        <div><div class="page-title">错题本</div><div class="page-sub">真实接口：m/mistake/summary · m/mistake/list（status=0）· 分数来自真实评测记录</div></div>
        <div class="page-actions"><a class="btn" href="#/home">返回首页</a><button class="btn" data-action="refresh">刷新</button></div>
      </div>
      <div class="grid grid-3" style="margin-bottom:18px">
        ${statsCard({ icon: 'mistake', label: '待订正 · 听说', cls: 'c-orange', value: String(num(toCorrect.audio) || 0), unit: '题' })}
        ${statsCard({ icon: 'read', label: '待订正 · 读写', cls: 'c-violet', value: String(num(toCorrect.read_write) || 0), unit: '题' })}
        ${statsCard({ icon: 'info', label: '已订正', cls: 'c-green', value: String((num(corrected.audio) || 0) + (num(corrected.read_write) || 0)), unit: '题' })}
      </div>
      ${data.listError ? notice('warn', `错题明细接口返回异常：${esc(data.listError.message || '')}`) : ''}
      <div class="card">
        <div class="card-head" style="padding:16px 18px 0"><div class="card-title"><span class="dot"></span>待订正明细</div><span class="tiny muted">共 ${rows.length} 条</span></div>
        <div style="margin-top:10px">
          ${rows.length ? rows.map((row) => `
            <div class="mistake-row" data-action="mistake-detail" data-id="${esc(row.id)}">
              <div class="hw-icon">${svgIcon('mistake')}</div>
              <div style="flex:1;min-width:0">
                <div class="q-name">${esc(row.question_type || '错题')} <span class="badge badge-gray">${row.mistake_type === 2 ? '读写' : '听说'}</span></div>
                <div class="q-sub">更新时间 ${esc(row.update_time || '—')} · ${esc(row.structure && row.structure[0] && row.structure[0].set_name || '')}</div>
              </div>
              <div style="text-align:right">
                <div class="score-pill ${num(row.score_rate) >= 60 ? 'good' : ''}">${pct(row.score_rate)}</div>
                <div class="tiny muted">得分率</div>
              </div>
              <span class="badge badge-blue" style="margin-left:10px">查看</span>
            </div>`).join('') : `<div class="empty"><div class="empty-ico">✅</div><p>暂无待订正错题</p></div>`}
        </div>
      </div>
      <div class="section">${notice('info', '错题明细包含官方评测 XML 与录音文件 URL；参考客户端通过本地代理缓存后播放/展示，详见每道错题详情。')}</div>
    `);
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail) + `<button class="btn" data-action="refresh">重试</button>`);
  }
}
async function renderMistakeDetail(id) {
  markNav('mistakes');
  const token = beginRender();
  setView(loadingHtml('正在读取错题详情与评测记录…'));
  try {
    const data = await api(`/api/mistake/${encodeURIComponent(id)}`);
    if (isStale(token)) return;
    S.mistakeDetail = data;
    const content = data.content;
    const type = content ? (content.structure_type || '').split('.').pop() : null;
    const scores = data.scoreDetail || [];
    setView(`
      <div class="crumb"><a href="#/mistakes">错题本</a> / 详情</div>
      <div class="page-head">
        <div><div class="page-title">${esc(data.question_type || '错题')}</div><div class="page-sub">错题 id ${esc(data.id)} · 更新于 ${esc(data.update_time || '')} · 得分率 ${pct(data.score_rate)}</div></div>
        <div class="page-actions"><a class="btn" href="#/mistakes">返回</a></div>
      </div>
      ${data.contentError ? notice('warn', `题目资源包加载失败：${esc(data.contentError.message || '')}`) : ''}
      ${content ? `
        <div class="card q-card" style="margin-bottom:16px">
          <div class="q-card-head"><div class="q-card-title">题目还原 ${typeBadge(type)}</div><span class="tiny muted">content_${esc(content.stid)}.zip</span></div>
          <div class="q-card-body">${renderQuestionBody(content, type, 0)}</div>
        </div>` : ''}
      <div class="card card-pad">
        <div class="card-head"><div class="card-title"><span class="dot"></span>我的评测记录</div><span class="tiny muted">来自 /m/mistake/list 的真实分数与录音</span></div>
        ${scores.length ? scores.map((sc, i) => {
          const detail = sc.detail && typeof sc.detail === 'object' ? sc.detail : {};
          const items = [
            ['得分率', pct(sc.score_rate)],
            ['标准分', fmtNum(sc.standard_score)],
            ['总分', fmtNum(detail.total_score)],
            ['准确度', fmtNum(detail.accuracy_score)],
            ['流利度', fmtNum(detail.fluency_score)],
            ['完整度', fmtNum(detail.integrity_score)],
            ['类别', detail.category || '—'],
          ];
          return `
            <div style="border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:12px">
              <div class="row-between wrap" style="margin-bottom:8px">
                <b>记录 ${i + 1}</b>
                <span class="chip">entity ${esc(sc.entity_id || '—')}</span>
              </div>
              <div class="grid grid-4" style="grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin-bottom:10px">
                ${items.map(([k, v]) => `<div class="detail-stat"><div class="k">${esc(k)}</div><div class="v" style="font-size:15px">${esc(v)}</div></div>`).join('')}
              </div>
              ${sc.audioUrl ? audioBlock(sc.audioUrl, '我的录音') : '<div class="tiny muted">该记录没有录音 URL。</div>'}
              ${sc.detailFileUrl ? `<a class="btn btn-sm" href="${esc(sc.detailFileUrl)}" target="_blank" rel="noopener">查看评测 XML 原始结果 →</a>` : ''}
            </div>`;
        }).join('') : `<div class="empty"><p>没有评测明细记录</p></div>`}
      </div>
      <div class="section">${notice('info', '以上分数与录音是官方服务端返回的历史评测结果，不是参考客户端生成的分数。')}</div>
    `);
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail) + `<a class="btn" href="#/mistakes">返回错题本</a>`);
  }
}

/* ------------------------------------------------------------------ *
 * 生词本（未实现）
 * ------------------------------------------------------------------ */
function renderWords() {
  markNav('words');
  setView(`
    <div class="page-head">
      <div><div class="page-title">生词本</div><div class="page-sub">原作：PC 词典包 pc_xst_dict（28,322 词）+ IndexedDB wordDict</div></div>
      <div class="page-actions"><a class="btn" href="#/home">返回首页</a></div>
    </div>
    <div class="empty">
      <div class="empty-ico">📖</div>
      <p><b>参考客户端未实现生词本</b></p>
      <p class="small">逆向资料中已确认词典包格式（docs/06_data.md §4.1：<span class="mono">pc_xst_dict.json</span>，28,323 条），<br>
         但本次只读 API 清单未包含用户生词本读写接口；为避免伪造数据，本页不展示词表。</p>
    </div>
    <div class="section">${notImplementedNotice()}</div>
  `);
}

/* ------------------------------------------------------------------ *
 * E 卡
 * ------------------------------------------------------------------ */
async function renderEcards() {
  markNav('ecards');
  const token = beginRender();
  setView(loadingHtml('正在读取 E 卡列表…'));
  try {
    const data = await api('/api/ecards');
    if (isStale(token)) return;
    S.ecards = data;
    const items = data.items || [];
    setView(`
      <div class="page-head">
        <div><div class="page-title">我的 E 卡</div><div class="page-sub">真实接口：m/ecard/list · 敏感字段（密码/手机号/机器码）已在服务端遮蔽</div></div>
        <div class="page-actions"><a class="btn" href="#/home">返回首页</a><button class="btn" data-action="refresh">刷新</button></div>
      </div>
      <div class="grid grid-3">
        ${items.map((card) => `
          <div class="card ecard-card">
            <div class="row-between">
              <span class="badge ${card.out_of_date ? 'badge-red' : 'badge-green'}">${card.out_of_date ? '已过期' : '有效'}</span>
              <span class="badge badge-blue">${esc(card.grade || '')}</span>
            </div>
            <div class="ecard-number" style="margin-top:12px">${esc(card.number || '—')}</div>
            <div class="ecard-name">${esc(card.name || '')} · ${esc(card.class_name || '')}</div>
            <div class="kv">
              <div class="k">学校</div><div class="v">${esc(card.school_name || '—')}</div>
              <div class="k">班级</div><div class="v">${esc(card.class_name || '—')} ${esc(card.class_number || '')}</div>
              <div class="k">有效期至</div><div class="v">${esc(card.expire_time || '—')}</div>
              <div class="k">绑定时间</div><div class="v">${esc(card.bind_time || '—')}</div>
              <div class="k">考区</div><div class="v">${esc(card.area || card.province_name || '—')}</div>
              <div class="k">引擎</div><div class="v mono tiny">${esc(card.engine_config || '—')}</div>
              <div class="k">E 卡密码</div><div class="v">${esc(card.password || '—')} <span class="tiny muted">（服务端遮蔽）</span></div>
            </div>
          </div>`).join('') || `<div class="empty"><p>未查到 E 卡</p></div>`}
      </div>
      <div class="section">${notice('info', 'E 卡列表包含大量账号/学校字段；本参考客户端在返回浏览器前统一遮蔽 password、手机号、机器码、教师电话等敏感字段。')}</div>
    `);
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail));
  }
}

/* ------------------------------------------------------------------ *
 * 系统配置
 * ------------------------------------------------------------------ */
async function renderConfig() {
  markNav('config');
  const token = beginRender();
  setView(loadingHtml('正在读取 system/config（约 180 KB）…'));
  try {
    const data = await api('/api/config');
    if (isStale(token)) return;
    S.config = data;
    S.configPage = 1;
    S.configQuery = '';
    paintConfig();
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail));
  }
}
function paintConfig() {
  const data = S.config;
  const entries = Object.entries((data && data.config) || {}).sort((a, b) => a[0].localeCompare(b[0]));
  const query = S.configQuery.trim().toLowerCase();
  const filtered = query ? entries.filter(([k, v]) => k.toLowerCase().includes(query) || String(v).toLowerCase().includes(query)) : entries;
  const pageSize = 20;
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  S.configPage = Math.max(1, Math.min(totalPages, S.configPage));
  const pageEntries = filtered.slice((S.configPage - 1) * pageSize, S.configPage * pageSize);
  setView(`
    <div class="page-head">
      <div><div class="page-title">系统配置查看</div><div class="page-sub">真实接口：system/config（${fmtNum(data.count, 0)} 个键）· system/time · 只读展示，便于验证逆向结论</div></div>
      <div class="page-actions"><a class="btn" href="#/home">返回首页</a><button class="btn" data-action="refresh">刷新</button></div>
    </div>
    <div class="config-toolbar">
      <input class="search-input" id="configSearch" placeholder="搜索 key 或 value（如 engine_sdk_config、homework_rank_rate…）" value="${esc(S.configQuery)}">
      <button class="btn" data-action="config-search">搜索</button>
      <span class="chip">服务端时间 <b>${esc((data.serverTime && data.serverTime.date) || '—')}</b></span>
      <span class="chip">抓取于 <b>${esc(fmtDate(data.fetchedAt))}</b></span>
    </div>
    <div class="card" style="overflow:hidden">
      <div style="max-height:58vh;overflow:auto">
        <table class="config-table">
          <thead><tr><th style="width:240px">Key</th><th>Value</th></tr></thead>
          <tbody>
            ${pageEntries.map(([key, value], index) => `
              <tr>
                <td class="key">${esc(key)}</td>
                <td class="val clamp" data-action="config-expand" data-key="${esc(key)}" title="点击查看完整值">${esc(String(value))}</td>
              </tr>`).join('') || '<tr><td colspan="2" class="center muted" style="padding:34px">没有匹配项</td></tr>'}
          </tbody>
        </table>
      </div>
      <div class="pager" style="padding:10px 14px">
        <span class="tiny muted">共 ${filtered.length} 项 · 第 ${S.configPage} / ${totalPages} 页</span>
        <div class="pages">
          <button data-action="config-page" data-page="${S.configPage - 1}" ${S.configPage <= 1 ? 'disabled' : ''}>上一页</button>
          <button data-action="config-page" data-page="${S.configPage + 1}" ${S.configPage >= totalPages ? 'disabled' : ''}>下一页</button>
        </div>
      </div>
    </div>
    <div class="section">${notice('info', 'system/config 返回扁平 key→string 字典，很多 value 本身是 JSON 字符串；点击 value 可查看完整内容。参考客户端不修改任何配置。')}</div>
  `);
}

/* ------------------------------------------------------------------ *
 * 关于 / 实现矩阵
 * ------------------------------------------------------------------ */
async function renderAbout() {
  markNav('about');
  const token = beginRender();
  setView(loadingHtml('正在读取实现信息…'));
  try {
    const data = await api('/api/about');
    if (isStale(token)) return;
    const rows = [
      ['签名 / 信封', 'MD5(pcWin+time+b64(body)+KEY_V2) · head{version,sign,pid,time,time_second}', true],
      ['字段加密', 'AES-128-ECB / k_serves（登录 phone/password）', true],
      ['登录 / token', 'user/login · token 持久化 .state/token.json · 支持 app_token', true],
      ['只读接口', `${data.endpoints.length} 个封装并返回真实数据`, true],
      ['题库资源包', 'cdnsubject 下载 · 包尾 336B 口令块 · ZipCrypto 解密 · 本地缓存', true],
      ['首页 / 作业 / 套卷', 'g/homework/list · g/set/list · template res.json', true],
      ['练习页', 'collector.read / dialogue / picture 渲染 + 示范音频（bonus: collector.choose）', true],
      ['错题本', 'm/mistake/summary + m/mistake/list + 历史评测音频/XML', true],
      ['E 卡 / 系统配置', 'm/ecard/list（脱敏）· system/config 只读检索', true],
      ['录音采集', 'SndHelper 麦克风采集', false],
      ['ISE / AI 评测', 'wss://oe-pub.eduaiplat.com 双通道评分', false],
      ['考试提交', 'm/audio/sync-v2、g/homework/checkstart 等写接口', false],
      ['OSS / SLS 上传', '阿里云 STS PostObject / SLS 日志', false],
      ['自动更新器', 'EtsUpdate.exe / client/mobile-update', false],
      ['读写模拟题型', 'rw_data 无 content 包结构', false],
    ];
    setView(`
      <div class="page-head">
        <div><div class="page-title">关于 / 实现矩阵</div><div class="page-sub">${esc(data.title)} ${esc(data.version)} · 目标版本 ${esc(data.targetVersion)}</div></div>
        <div class="page-actions"><a class="btn" href="#/home">返回首页</a></div>
      </div>
      <div class="card" style="padding:6px 0;overflow:hidden;margin-bottom:18px">
        <table class="matrix">
          <thead><tr><th style="width:190px">能力</th><th>实现</th><th style="width:80px">状态</th></tr></thead>
          <tbody>${rows.map(([name, desc, ok]) => `<tr><td><b>${esc(name)}</b></td><td>${esc(desc)}</td><td class="${ok ? 'ok' : 'no'}">${ok ? '已实现' : '未实现'}</td></tr>`).join('')}</tbody>
        </table>
      </div>
      <div class="grid grid-2" style="margin-bottom:18px">
        <div class="card card-pad">
          <div class="card-title" style="margin-bottom:10px">已封装的只读接口</div>
          <div class="endpoint-grid">${data.endpoints.map((e) => `<span class="endpoint-item">${esc(e)}</span>`).join('')}</div>
        </div>
        <div class="card card-pad">
          <div class="card-title" style="margin-bottom:10px">未实现能力</div>
          <ul class="answer-list" style="margin:0">${data.notImplemented.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
          <div class="card-title" style="margin:16px 0 10px">安全说明</div>
          <ul class="answer-list" style="margin:0">${data.notes.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
        </div>
      </div>
      <div class="card card-pad">
        <div class="card-title" style="margin-bottom:10px">启动方式</div>
        <pre class="code-block">python reimpl/server.py            # http://127.0.0.1:8787
python reimpl/server.py --port 8790 --open</pre>
        <div class="small muted" style="margin-top:10px">签名：<span class="mono">${esc(data.signature)}</span><br>字段加密：<span class="mono">${esc(data.aes)}</span></div>
      </div>
    `);
  } catch (err) {
    if (isStale(token)) return;
    if (err.status === 401) { authLost(err); return; }
    setView(errorBanner(err.message, err.detail));
  }
}

/* ------------------------------------------------------------------ *
 * 事件绑定
 * ------------------------------------------------------------------ */
function setBusy(button, busy, text = '处理中…') {
  if (!button) return;
  if (busy) {
    button.dataset.oldText = button.textContent;
    button.textContent = text;
    button.disabled = true;
  } else {
    if (button.dataset.oldText) button.textContent = button.dataset.oldText;
    button.disabled = false;
  }
}
function toggleAnswer(targetId) {
  const node = document.getElementById(targetId);
  if (!node) return;
  node.classList.toggle('hidden');
  const button = document.querySelector(`[data-action="toggle-answer"][data-target="${targetId}"]`);
  if (button) {
    const hidden = node.classList.contains('hidden');
    button.textContent = hidden ? '显示答案与解析' : '收起答案与解析';
  }
}
document.addEventListener('click', async (event) => {
  const target = event.target.closest('[data-action]');
  const hrefNode = event.target.closest('[data-href]');
  if (hrefNode) {
    event.preventDefault();
    navigate(hrefNode.dataset.href);
    return;
  }
  if (!target) return;
  const action = target.dataset.action;
  try {
    switch (action) {
      case 'modal-close':
        closeModal();
        break;
      case 'refresh':
        S.home = null; S.modules = null; S.mistakes = null; S.ecards = null; S.config = null;
        S.detailCache = {};
        route();
        break;
      case 'login':
        await doLogin(target.dataset.mode, target);
        break;
      case 'logout':
        await api('/api/logout', { method: 'POST', body: '{}' });
        S.status = Object.assign({}, S.status, { loggedIn: false, user: null });
        S.home = null; S.detailCache = {};
        closeModal();
        applyStatus(S.status);
        renderLogin(S.status, '已退出登录。');
        toast('已退出登录（未删除 secrets/ 中的文件）');
        break;
      case 'show-account':
        openAccountModal();
        break;
      case 'hw-tab':
        navigate('#/homework?tab=' + encodeURIComponent(target.dataset.tab));
        break;
      case 'open-question':
        S.pendingQuestion = Number(String(target.dataset.index).split(':')[1] || 0);
        {
          const kind = target.dataset.kind;
          const id = target.dataset.id;
          const column = target.dataset.column;
          const structure = (kind === 'homework'
            ? (S.detailCache['hw:' + id] || {}).structure
            : (S.detailCache[`set:${column}:${id}`] || {}).structure) || [];
          const si = Number(String(target.dataset.index).split(':')[0] || 0);
          let flat = 0;
          for (let i = 0; i < si; i++) flat += (structure[i].contents || []).length;
          S.pendingQuestion = flat + Number(String(target.dataset.index).split(':')[1] || 0);
        }
        navigate(target.dataset.kind === 'homework'
          ? `#/practice/homework/${encodeURIComponent(target.dataset.id)}`
          : `#/practice/set/${encodeURIComponent(target.dataset.column)}/${encodeURIComponent(target.dataset.id)}`);
        break;
      case 'practice-open':
        loadPracticeQuestion(Number(target.dataset.index));
        break;
      case 'practice-prev':
        loadPracticeQuestion(S.practice.active - 1);
        break;
      case 'practice-next':
        loadPracticeQuestion(S.practice.active + 1);
        break;
      case 'practice-retry':
        {
          const index = Number(target.dataset.index);
          const p = S.practice;
          if (p) {
            delete p.loaded[p.items[index].stid];
            delete p.errors[p.items[index].stid];
            loadPracticeQuestion(index);
          }
        }
        break;
      case 'toggle-answer':
        toggleAnswer(target.dataset.target);
        break;
      case 'sets-search':
        {
          const input = document.getElementById('setSearch');
          navigate(`#/sets/${encodeURIComponent(target.dataset.column)}?q=${encodeURIComponent((input && input.value || '').trim())}`);
        }
        break;
      case 'sets-page':
        navigate(`#/sets/${encodeURIComponent(target.dataset.column)}?q=${encodeURIComponent(target.dataset.q || '')}&offset=${encodeURIComponent(target.dataset.offset || 0)}`);
        break;
      case 'set-no-struct':
        openModal('读写套卷目录', `<p>该套卷来自 <span class="mono">g/set/list</span> 的 <span class="mono">rw_data</span>，只包含目录信息，没有 content 包结构。</p>
          <div class="notice notice-warn">${svgIcon('warning')}<div>参考客户端未实现读写模拟题型渲染，不伪造题目。</div></div>`);
        break;
      case 'course-unit':
        navigate(`#/courses?book=${encodeURIComponent(target.dataset.book)}&unit=${encodeURIComponent(target.dataset.unit)}`);
        break;
      case 'config-search':
        {
          const input = document.getElementById('configSearch');
          S.configQuery = (input && input.value || '').trim();
          S.configPage = 1;
          paintConfig();
        }
        break;
      case 'config-page':
        S.configPage = Number(target.dataset.page) || 1;
        paintConfig();
        break;
      case 'config-expand':
        {
          const key = target.dataset.key;
          const value = ((S.config && S.config.config) || {})[key];
          openModal('配置项 ' + key, `<pre class="code-block" style="white-space:pre-wrap;word-break:break-all">${esc(String(value))}</pre>`);
        }
        break;
      case 'mistake-detail':
        navigate('#/mistake/' + encodeURIComponent(target.dataset.id));
        break;
      default:
        break;
    }
  } catch (err) {
    toast(err.message || '操作失败');
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeModal();
  if (event.key === 'Enter' && document.activeElement && document.activeElement.id === 'setSearch') {
    const node = document.querySelector('[data-action="sets-search"]');
    if (node) node.click();
  }
  if (event.key === 'Enter' && document.activeElement && document.activeElement.id === 'configSearch') {
    const node = document.querySelector('[data-action="config-search"]');
    if (node) node.click();
  }
});
document.getElementById('userChip').addEventListener('click', () => {
  if (!S.status || !S.status.loggedIn) { renderLogin(S.status, S.loginError); return; }
  openAccountModal();
});
document.querySelectorAll('.win-btn').forEach((node) => node.addEventListener('click', () => {
  toast('窗口装饰为视觉还原；请使用浏览器自带的最小化/关闭按钮。');
}));

function openAccountModal() {
  const status = S.status || {};
  const user = status.user || {};
  const ecard = status.ecard || {};
  openModal('账号信息', `
    <div class="kv" style="grid-template-columns:110px 1fr">
      <div class="k">姓名</div><div class="v">${esc(user.name || '—')}</div>
      <div class="k">手机号</div><div class="v">${esc(user.phone || '—')}</div>
      <div class="k">年级</div><div class="v">${esc(user.grade_name || '—')}</div>
      <div class="k">城市</div><div class="v">${esc(user.city_name || '—')}</div>
      <div class="k">E 卡</div><div class="v">${esc(ecard.number || '—')} ${esc(ecard.name || '')}</div>
      <div class="k">班级</div><div class="v">${esc(user.class_name || '—')}</div>
      <div class="k">有效期至</div><div class="v">${esc(ecard.expire_time || '—')}</div>
      <div class="k">登录来源</div><div class="v">${esc(status.tokenSource || '—')} <span class="tiny muted">（token ${esc(status.tokenMasked || '')}）</span></div>
      <div class="k">服务端时间</div><div class="v">${esc((status.serverTime && status.serverTime.date) || '—')}</div>
    </div>
    <div class="notice notice-info" style="margin-top:14px">${svgIcon('info')}<div>参考客户端只读；退出登录不会删除 <span class="mono">secrets/</span> 文件，只会清除 <span class="mono">reimpl/.state/token.json</span>。</div></div>
  `, `
    <a class="btn" href="#/ecards">查看 E 卡</a>
    <button class="btn" data-action="modal-close">关闭</button>
    <button class="btn" data-action="logout">退出登录</button>
  `);
}

/* ------------------------------------------------------------------ *
 * 启动
 * ------------------------------------------------------------------ */
async function boot() {
  try {
    const status = await api('/api/status');
    S.status = status;
    applyStatus(status);
    if (!status.loggedIn) {
      renderLogin(status, status.authError ? status.authError.message : null);
      return;
    }
    route();
  } catch (err) {
    setView(`
      <div class="empty" style="margin-top:40px">
        <div class="empty-ico">⚠️</div>
        <p><b>无法连接本地后端</b></p>
        <p class="small">${esc(err.message)}</p>
        <p class="small">请先在终端运行：<span class="mono">python reimpl/server.py</span>，然后刷新本页。</p>
        <button class="btn" data-action="refresh">重试</button>
      </div>`);
  }
}
boot();
