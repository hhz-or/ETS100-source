/**
 * ETS Replica · mq_server
 * ---------------------------------------------------------------------------
 * 与原作一致的“日志回传中继”：
 *   - 从 40001 起监听 WebSocket（127.0.0.1），端口占用则 +1；
 *   - 连接建立后立即下发 "hello mq_server!"；
 *   - 收到的每条消息原样写入 logs/ets_<年-月-日>.log，并广播给所有客户端（含发送者）；
 *   - 最终端口写入 mq_server/app.json 的 suspensionBallPort 字段。
 *
 * 启动：node main.js（或 npm start）
 * 注意：日志目录位于 mq_server 的上一级（与原生壳 logs/ 目录一致）。
 */
'use strict'

const fs = require('fs')
const path = require('path')
const { WebSocketServer } = require('ws')

const BASE_PORT = Number(process.env.MQ_PORT || 40001)
const MAX_PORT = 65535
const HOST = process.env.MQ_HOST || '127.0.0.1'

const APP_DIR = path.resolve(__dirname, '..')
const LOG_DIR = path.join(APP_DIR, 'logs')
const APP_JSON = path.join(__dirname, 'app.json')

// 文件名按“进程启动日”生成，月/日不补零（与原创 main.js 一致）
const START = new Date()
const LOG_FILE = path.join(LOG_DIR, `ets_${START.getFullYear()}-${START.getMonth() + 1}-${START.getDate()}.log`)

let activePort = null
let server = null

function ts() {
  const d = new Date()
  const p = (v, n = 2) => String(v).padStart(n, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`
}

function writeLog(level, message) {
  const line = `[${ts()}] [${level}] mq_server - ${message}\n`
  process.stdout.write(line)
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true })
    fs.appendFileSync(LOG_FILE, line, 'utf8')
  } catch (err) {
    process.stderr.write(`[mq_server] 写日志失败: ${err && err.message ? err.message : err}\n`)
  }
}

function readAppConfig() {
  try {
    const raw = fs.readFileSync(APP_JSON, 'utf8')
    if (!raw || !raw.trim()) return {}
    const data = JSON.parse(raw)
    return data && typeof data === 'object' ? data : {}
  } catch {
    return {}
  }
}

function writeAppConfig(port) {
  // 与原作一致：JSON.stringify 后覆盖写入（无缩进）
  fs.writeFileSync(APP_JSON, JSON.stringify({ suspensionBallPort: port }), 'utf8')
}

function registerPort(port) {
  const config = readAppConfig()
  if (config.suspensionBallPort === port) {
    writeLog('INFO', `read_app_config_success ${JSON.stringify(config)}`)
    return
  }
  writeLog('INFO', `update port to ${port}`)
  try {
    writeAppConfig(port)
    writeLog('INFO', `write_app_config_success ${JSON.stringify({ suspensionBallPort: port })}`)
  } catch (err) {
    writeLog('ERROR', `write_app_config_fail ${err && err.message ? err.message : err}`)
  }
}

function broadcast(payload) {
  if (!server) return
  for (const client of server.clients) {
    if (client.readyState === 1) {
      try {
        client.send(payload)
      } catch (err) {
        writeLog('ERROR', `broadcast error: ${err && err.message ? err.message : err}`)
      }
    }
  }
}

function listenOn(port) {
  return new Promise((resolve, reject) => {
    const wss = new WebSocketServer({ port, host: HOST })
    const onError = (err) => {
      wss.removeListener('listening', onListening)
      wss.close(() => {})
      reject(err)
    }
    const onListening = () => {
      wss.removeListener('error', onError)
      resolve(wss)
    }
    wss.once('error', onError)
    wss.once('listening', onListening)
  })
}

async function findAvailablePort(startPort) {
  for (let port = startPort; port <= MAX_PORT; port += 1) {
    try {
      return { wss: await listenOn(port), port }
    } catch (err) {
      if (err && err.code === 'EADDRINUSE') {
        process.stderr.write(`[mq_server] port ${port} in use, trying ${port + 1}\n`)
        continue
      }
      throw err
    }
  }
  throw new Error(`no available port in ${startPort}-${MAX_PORT}`)
}

function attachServer(wss, port) {
  server = wss
  activePort = port

  wss.on('connection', (ws) => {
    writeLog('INFO', 'new connection: [object Object]')

    ws.on('message', (message) => {
      const text = Buffer.isBuffer(message) ? message.toString('utf8') : String(message)
      writeLog('INFO', `received: ${text}`)
      broadcast(text)
    })

    ws.on('close', (code, reason) => {
      writeLog('INFO', `close, code : ${code}, reason: ${reason ? reason.toString() : ''}`)
    })

    ws.on('error', (err) => {
      writeLog('ERROR', `error: ${err && err.message ? err.message : err}`)
    })

    // 与原作一致：连接建立后服务端唯一主动下行
    try {
      ws.send('hello mq_server!')
    } catch (err) {
      writeLog('ERROR', `send hello failed: ${err && err.message ? err.message : err}`)
    }
  })

  wss.on('error', (err) => {
    writeLog('ERROR', `server error: ${err && err.message ? err.message : err}`)
  })

  writeLog('INFO', `mq_server running! port is ${port}`)
  registerPort(port)
}

function shutdown(signal) {
  writeLog('INFO', `received ${signal}, shutting down`)
  try {
    if (server) {
      for (const client of server.clients) {
        try { client.close(1001, 'server shutdown') } catch { /* ignore */ }
      }
      server.close(() => process.exit(0))
      // 兜底：2s 后强制退出
      setTimeout(() => process.exit(0), 2000).unref()
    } else {
      process.exit(0)
    }
  } catch {
    process.exit(0)
  }
}

async function main() {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true })
  } catch { /* 日志写入时会再次尝试 */ }

  const { wss, port } = await findAvailablePort(BASE_PORT)
  attachServer(wss, port)
}

process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))

main().catch((err) => {
  writeLog('ERROR', `startup failed: ${err && err.stack ? err.stack : err}`)
  process.exitCode = 1
})

module.exports = { getActivePort: () => activePort }
