#!/usr/bin/env node
/**
 * 可选的前端交互自测（需要 Node.js 22+ 与已开启 CDP 的 Chrome）。
 *
 * 1) 以调试端口启动 Chrome：
 *    chrome --headless=new --remote-debugging-port=9222 --user-data-dir=%TEMP%\ets-ref-chrome about:blank
 * 2) 运行：
 *    node reimpl/tools/cdp_probe.js
 *
 * 检查首页 / 作业列表 / 详情 / 练习页（read 题、音频、答案展开、下一题）/ 错题本 / 系统配置，
 * 并收集页面 console error 与未捕获异常。不打印任何凭据。
 */
'use strict';

const CDP = process.env.CDP_ENDPOINT || 'http://127.0.0.1:9222';
const BASE = process.env.ETS_BASE || 'http://127.0.0.1:8787';
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' · ' + detail : ''}`);
}

async function main() {
  const create = await fetch(`${CDP}/json/new?${encodeURIComponent(BASE + '/#/home')}`, { method: 'PUT' });
  if (!create.ok) throw new Error(`无法创建 CDP 页面：HTTP ${create.status}`);
  const target = await create.json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = () => reject(new Error('CDP WebSocket 连接失败'));
  });

  let nextId = 1;
  const pending = new Map();
  const events = [];
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    } else if (message.method) {
      events.push(message);
    }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) {
      throw new Error('页面脚本异常：' + (result.exceptionDetails.exception?.description || result.exceptionDetails.text));
    }
    return result.result?.value;
  };
  const navigate = async (hash, delay = 1800) => {
    await evaluate(`location.hash = ${JSON.stringify(hash)}`);
    await wait(delay);
  };
  const waitFor = async (expression, timeout = 10000, interval = 300) => {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (await evaluate(expression)) return true;
      await wait(interval);
    }
    return false;
  };

  await send('Runtime.enable');
  await send('Log.enable');
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await wait(1200);

  // 首页
  check('首页渲染', await waitFor(`!!document.querySelector('.hero-card') && document.body.innerText.includes('学习中心')`));
  check('首页统计卡', await evaluate(`document.querySelectorAll('.stat-card').length === 3`));
  check('首页模块卡', await evaluate(`document.querySelectorAll('.module-card').length === 3`));

  // 作业列表
  await navigate('#/homework?tab=todo', 1500);
  check('作业列表 tabs', await evaluate(`document.querySelectorAll('.tabs .tab').length === 4`));
  check('作业列表卡片', await evaluate(`document.querySelectorAll('.hw-card').length >= 1`));

  // 详情
  await navigate('#/homeworkDetail/111203417', 3000);
  check('作业详情 / 试卷结构', await evaluate(`!!document.querySelector('.detail-title') && document.querySelectorAll('.tl-item').length >= 3`));
  check('详情题目列表', await evaluate(`document.querySelectorAll('.question-row').length === 6`));

  // 练习页（read 题）
  await navigate('#/practice/homework/111203417', 4500);
  check('练习页题目 rail', await evaluate(`document.querySelectorAll('.rail-item').length === 6`));
  check('read 题题干', await evaluate(`document.querySelector('.q-text')?.innerText.includes('Do you know any workers') === true`));
  check('示范音频可播放元素', await evaluate(`!!document.querySelector('.audio-row audio[src*="/api/audio/"]')`));
  const hiddenBefore = await evaluate(`document.querySelectorAll('.answer-panel.hidden').length`);
  await evaluate(`document.querySelector('[data-action="toggle-answer"]').click()`);
  await wait(400);
  const hiddenAfter = await evaluate(`document.querySelectorAll('.answer-panel.hidden').length`);
  check('展开答案与解析', hiddenAfter < hiddenBefore, `${hiddenBefore} → ${hiddenAfter}`);
  check('解析文本渲染', await evaluate(`document.body.innerText.includes('解析')`));
  await evaluate(`document.querySelector('[data-action="practice-next"]').click()`);
  await wait(2200);
  check('下一题切换', await evaluate(`document.querySelector('.rail-item.active')?.innerText.includes('st2') === true`));

  // 错题本
  await navigate('#/mistakes', 2200);
  check('错题本统计与列表', await evaluate(`document.querySelectorAll('.mistake-row').length >= 1`), `rows=${await evaluate(`document.querySelectorAll('.mistake-row').length`)}`);

  // 系统配置
  await navigate('#/config', 2600);
  check('系统配置表', await evaluate(`document.querySelectorAll('.config-table tbody tr').length > 0`));

  // 点击跳转链路
  await navigate('#/home', 3000);
  await evaluate(`document.querySelector('.module-card').click()`);
  await wait(1400);
  check('模块卡点击 → 套卷目录', await evaluate(`location.hash.startsWith('#/sets/')`), await evaluate(`location.hash`));
  await navigate('#/homework?tab=todo', 1800);
  await evaluate(`document.querySelector('.hw-card').click()`);
  await wait(1800);
  check('作业卡点击 → 详情', await evaluate(`location.hash.startsWith('#/homeworkDetail/')`), await evaluate(`location.hash`));
  await wait(1600);
  await evaluate(`document.querySelector('.question-row').click()`);
  await wait(2600);
  check('题目行点击 → 练习页', await evaluate(`location.hash.startsWith('#/practice/')`), await evaluate(`location.hash`));
  await navigate('#/mistakes', 2200);
  await evaluate(`document.querySelector('.mistake-row').click()`);
  await wait(2600);
  check('错题行点击 → 错题详情', await evaluate(`location.hash.startsWith('#/mistake/')`), await evaluate(`location.hash`));
  check('错题详情含真实评测记录', await evaluate(`document.body.innerText.includes('我的评测记录')`));

  // 控制台错误
  const errors = events.filter((message) => {
    if (message.method === 'Runtime.exceptionThrown') return true;
    if (message.method === 'Log.entryAdded' && message.params?.entry?.level === 'error') return true;
    if (message.method === 'Runtime.consoleAPICalled' && message.params?.type === 'error') return true;
    return false;
  });
  const errorText = errors.map((message) => JSON.stringify(message.params).slice(0, 300)).join(' | ');
  check('无页面 console error / 未捕获异常', errors.length === 0, errorText || '0 条');

  await fetch(`${CDP}/json/close/${target.id}`).catch(() => {});
  ws.close();
  const passed = results.filter((r) => r.ok).length;
  console.log(`\n合计：${passed}/${results.length} 通过`);
  return passed === results.length ? 0 : 1;
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error('CDP 自测失败：', error.message);
  process.exit(2);
});
