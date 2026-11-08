/**
 * 麦克风录音（16kHz 单声道 PCM16）
 * 浏览器/WebView2 用 getUserMedia + WebAudio，输出可直接交给 soundhelper.encode_speex。
 */
export class PcmRecorder {
  constructor({ sampleRate = 16000 } = {}) {
    this.sampleRate = sampleRate
    this.recording = false
    this.chunks = []
    this.ctx = null
    this.stream = null
    this.source = null
    this.processor = null
  }

  async start() {
    if (this.recording) return
    this.chunks = []
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: this.sampleRate,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false
      }
    })
    this.ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this.sampleRate })
    this.source = this.ctx.createMediaStreamSource(this.stream)
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1)
    this.processor.onaudioprocess = (ev) => {
      if (!this.recording) return
      this.chunks.push(new Float32Array(ev.inputBuffer.getChannelData(0)))
    }
    this.source.connect(this.processor)
    // 需要连接到 destination 才会持续回调（用静音增益避免回放）
    const mute = this.ctx.createGain()
    mute.gain.value = 0
    this.processor.connect(mute)
    mute.connect(this.ctx.destination)
    this.recording = true
  }

  async stop() {
    this.recording = false
    try { this.source && this.source.disconnect() } catch (e) {}
    try { this.processor && this.processor.disconnect() } catch (e) {}
    try { this.stream && this.stream.getTracks().forEach(t => t.stop()) } catch (e) {}
    try { this.ctx && this.ctx.close() } catch (e) {}
    const total = this.chunks.reduce((a, c) => a + c.length, 0)
    const merged = new Float32Array(total)
    let off = 0
    for (const c of this.chunks) { merged.set(c, off); off += c.length }
    this.chunks = []
    return this.toPcm16(merged)
  }

  /** Float32 [-1,1] → Int16 PCM；必要时重采样到 16k */
  toPcm16(float32) {
    const srcRate = this.ctx ? this.ctx.sampleRate : this.sampleRate
    let data = float32
    if (srcRate !== 16000) data = resampleLinear(float32, srcRate, 16000)
    // 去直流 + 简单增益归一化（避免录音过小）
    let mean = 0
    for (let i = 0; i < data.length; i++) mean += data[i]
    mean /= data.length || 1
    const out = new Int16Array(data.length)
    for (let i = 0; i < data.length; i++) {
      const v = Math.max(-1, Math.min(1, (data[i] - mean) * 1.5))
      out[i] = v < 0 ? v * 0x8000 : v * 0x7fff
    }
    return new Uint8Array(out.buffer)
  }

  /** 录制时长（秒） */
  get duration() {
    return this.chunks.reduce((a, c) => a + c.length, 0) / this.sampleRate
  }
}

function resampleLinear(input, from, to) {
  const ratio = from / to
  const outLen = Math.floor(input.length / ratio)
  const out = new Float32Array(outLen)
  for (let i = 0; i < outLen; i++) {
    const pos = i * ratio
    const i0 = Math.floor(pos)
    const i1 = Math.min(input.length - 1, i0 + 1)
    const frac = pos - i0
    out[i] = input[i0] * (1 - frac) + input[i1] * frac
  }
  return out
}

export default PcmRecorder
