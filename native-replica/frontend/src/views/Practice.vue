<template>
  <div class="page">
    <div class="page-head">
      <div>
        <el-button text size="small" @click="goBack">‹ 返回</el-button>
        <h1 class="page-title" style="margin-top: 6px">{{ title }}</h1>
        <p class="page-sub">
          {{ subtitle }}
          <span v-if="stid"> · stid {{ stid }}</span>
        </p>
      </div>
      <div class="page-actions">
        <el-switch v-model="showAnswer" active-text="显示答案" inactive-text="隐藏答案" />
        <el-button :loading="loading" @click="load">重新加载</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error">
      <template #default>
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 6px">
          <span class="small">content 包链路失败时可先载入内置示例，便于查看渲染效果。</span>
          <el-button size="small" type="warning" plain @click="useFallback">载入内置示例</el-button>
        </div>
      </template>
    </el-alert>

    <div v-loading="loading" class="practice-layout">
      <section class="question-card" v-if="content">
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
          <span class="question-type">{{ typeLabel }}</span>
          <el-tag size="small" effect="plain">content 包</el-tag>
          <el-tag v-if="fallbackUsed" size="small" type="warning" effect="plain">内置示例</el-tag>
          <el-tag v-if="isMock" size="small" type="info" effect="plain">Mock 数据</el-tag>
        </div>

        <h2 class="question-stem">{{ info.value || '（题干为空）' }}</h2>
        <p v-if="info.translate" class="question-translate">{{ info.translate }}</p>

        <div v-if="info.audio && audioUrl" class="audio-box">
          <span class="audio-label">示范音频</span>
          <audio controls preload="metadata" :src="audioUrl"></audio>
        </div>

        <!-- collector.read -->
        <template v-if="kind === 'read'">
          <div v-if="showAnswer" class="answer-box">
            <h4>参考原文</h4>
            <div class="rich-text">{{ info.value }}</div>
          </div>
        </template>

        <!-- collector.dialogue -->
        <template v-else-if="kind === 'dialogue'">
          <div v-for="(q, i) in questions" :key="i" class="sub-question">
            <div class="ask" v-html="safeRichText(q.ask || q.value || '')"></div>
            <div v-if="askAudioUrls[i]" class="audio-box" style="margin: 10px 0">
              <span class="audio-label">问句音频</span>
              <audio controls preload="metadata" :src="askAudioUrls[i]"></audio>
            </div>
            <div v-if="showAnswer" class="std-list">
              <div v-for="(std, j) in q.std || []" :key="j" class="std-item">{{ std.value }}</div>
              <div v-if="q.keywords" class="keypoint-chips">
                <span v-for="kw in q.keywords.split('|')" :key="kw" class="keypoint-chip">{{ kw }}</span>
              </div>
            </div>
          </div>

          <div v-if="showAnswer && info.answer" class="answer-box">
            <h4>参考答案</h4>
            <div class="rich-text">{{ info.answer }}</div>
          </div>
        </template>

        <!-- collector.picture -->
        <template v-else-if="kind === 'picture'">
          <div class="picture-frame">
            <img v-if="imageUrl" :src="imageUrl" alt="题目配图" />
            <span v-else>本题未提供图片资源</span>
          </div>

          <div v-if="info.topic" class="keypoint-chips" style="margin-bottom: 10px">
            <span class="keypoint-chip">话题：{{ info.topic }}</span>
            <span v-if="info.keypoint" class="keypoint-chip">{{ info.keypoint }}</span>
          </div>

          <div v-if="showAnswer && info.std && info.std.length" class="answer-box">
            <h4>参考范文</h4>
            <div v-for="(std, i) in info.std" :key="i" class="rich-text" style="margin-bottom: 8px">
              {{ std.value }}
            </div>
          </div>
        </template>
        <template v-else>
          <el-alert
            type="info"
            :closable="false"
            show-icon
            :title="'暂不支持的 structure_type：' + (parsed.type || '未知')"
          />
          <pre class="mono small" style="white-space: pre-wrap; margin-top: 12px">{{ JSON.stringify(content, null, 2) }}</pre>
        </template>

        <!-- 录音 + ISE 评测（朗读 / 情景问答 / 看图说话都支持） -->
        <div v-if="['read', 'dialogue', 'picture'].includes(kind)" class="answer-box" style="margin-top: 14px">
          <h4>录音评测 <span class="small muted">（speex 16k → ISE WebSocket）</span></h4>
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 10px 0">
            <el-button v-if="!recording" type="primary" @click="startRecord" :disabled="evaluating">
              {{ evalResult ? '重新录音' : '开始录音' }}
            </el-button>
            <el-button v-else type="danger" @click="stopRecord">停止并评测</el-button>
            <span class="small muted" v-if="recording">录音中… {{ recordSeconds }}s</span>
            <span class="small muted" v-if="evaluating">评测中…</span>
          </div>
          <el-alert v-if="evalError" type="error" :closable="false" show-icon :title="evalError" />
          <div v-if="evalResult && evalResult.scores" class="kv-grid">
            <div class="kv"><span>准确度</span><b>{{ fmtScore(evalResult.scores.accuracy) }}</b></div>
            <div class="kv"><span>流利度</span><b>{{ fmtScore(evalResult.scores.fluency) }}</b></div>
            <div class="kv"><span>完整度</span><b>{{ fmtScore(evalResult.scores.integrity) }}</b></div>
            <div class="kv"><span>总分</span><b>{{ fmtScore(evalResult.scores.total) }}</b></div>
          </div>
          <div v-if="evalResult && evalResult.scores && evalResult.scores.words && evalResult.scores.words.length"
               class="keypoint-chips" style="margin-top: 10px">
            <span v-for="(w, i) in evalResult.scores.words" :key="i" class="keypoint-chip"
                  :style="{ color: wordColor(w.score) }">{{ w.content }}</span>
          </div>
          <div v-if="evalResult && evalResult.scores && evalResult.scores.isRejected" class="small muted" style="margin-top: 8px">
            评测被拒绝（except_info={{ evalResult.scores.exceptInfo }}），请重新录音朗读。
          </div>

          <div v-if="evalResult && evalResult.scores && !evalResult.scores.isRejected" style="margin-top: 12px">
            <el-button type="success" :loading="uploadBusy" :disabled="uploadBusy || recording || evaluating"
                       @click="uploadResult">上传并回传成绩</el-button>
            <span class="small muted" style="margin-left: 10px">{{ uploadMsg }}</span>
          </div>
          <div v-if="syncInfo" class="kv-grid" style="margin-top: 10px">
            <div class="kv"><span>本题得分</span><b>{{ fmtScore(syncInfo.point) }}</b></div>
            <div class="kv"><span>完成度</span><b>{{ fmtScore(syncInfo.complete) }}</b></div>
            <div class="kv" v-if="syncInfo.submitTime"><span>提交时间</span><b>{{ syncInfo.submitTime }}</b></div>
          </div>
        </div>


        <div v-if="showAnswer && info.analyze" class="analysis-box">
          <h4>解析</h4>
          <div class="rich-text" v-html="safeRichText(info.analyze)"></div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 22px; gap: 10px; flex-wrap: wrap">
          <span class="small muted">数据目录：{{ dir || '—' }}</span>
          <div class="practice-nav">
            <el-button v-if="homeworkId" @click="$router.push('/homework/' + homeworkId)">返回作业详情</el-button>
            <el-button v-else @click="$router.push('/sets')">返回套卷</el-button>
            <el-button type="primary" :loading="loading" @click="load">重新加载</el-button>
          </div>
        </div>
      </section>

      <section v-else-if="!loading" class="panel">
        <el-empty description="暂未加载到题目内容">
          <el-button type="primary" @click="load">重新加载</el-button>
          <el-button @click="useFallback">载入内置示例</el-button>
        </el-empty>
      </section>

      <aside class="practice-aside">
        <div class="aside-card">
          <h4>加载过程</h4>
          <ul class="step-list">
            <li v-for="(step, i) in steps" :key="i">
              <span class="step-dot" :class="step.status">{{ step.status === 'ok' ? '✓' : step.status === 'fail' ? '!' : step.status === 'skip' ? '–' : '·' }}</span>
              <div class="step-body">
                <strong>{{ step.name }}</strong>
                <span v-if="step.detail">{{ step.detail }}</span>
              </div>
            </li>
            <li v-if="steps.length === 0">
              <span class="step-dot run">·</span>
              <div class="step-body"><strong>等待加载</strong><span>准备 content 包链路</span></div>
            </li>
          </ul>
        </div>

        <div class="aside-card">
          <h4>题目信息</h4>
          <div class="kv"><span>题型</span><b>{{ typeLabel }}</b></div>
          <div class="kv"><span>structure_type</span><b class="mono" style="font-size: 11px">{{ parsed.type || '—' }}</b></div>
          <div class="kv"><span>stid</span><b>{{ stid || '—' }}</b></div>
          <div class="kv"><span>set_id</span><b>{{ setId || '—' }}</b></div>
          <div class="kv" v-if="moduleName"><span>模块</span><b>{{ moduleName }}</b></div>
          <div class="kv"><span>子题数量</span><b>{{ kind === 'dialogue' ? questions.length : kind === 'picture' ? (info.std || []).length : 1 }}</b></div>
        </div>

        <div class="aside-card">
          <h4>说明</h4>
          <p class="small muted" style="margin: 0; line-height: 1.8">
            content 包由 <code>HttpHelper.download</code> 下载、<code>SevenZip.unzip</code> 解压、
            <code>FileHelper.readfile</code> 读取 content.json；音频经 <code>__core.media_url</code>
            转为壳内 HTTP 地址后交给 &lt;audio&gt; 播放。录音/评测链路未在本复刻前端实现。
          </p>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMockContent } from '../mock'
import { isMock } from '../bridge'
import { loadContentPackage, parseStructure, resolveMedia, safeRichText } from '../content'
import { PcmRecorder } from '../recorder'
import * as ise from '../ise'
import * as flow from '../practiceFlow'
import { sendRequest } from '../api'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// ---- 录音评测状态 ----
const recording = ref(false)
const recordSeconds = ref(0)
const evaluating = ref(false)
const evalResult = ref(null)
const evalError = ref('')
const uploadBusy = ref(false)
const uploadMsg = ref('')
const syncInfo = ref(null)
let recorder = null
let recordTimer = null
let pcmBuffer = null
let spxBytes = null
let recordStartedAt = 0
let evalSession = null

function fmtScore(v) {
  return Number.isFinite(Number(v)) ? (Math.round(Number(v) * 100) / 100) : '—'
}
function wordColor(score) {
  const s = Number(score) || 0
  if (s >= 4) return '#12b76a'
  if (s >= 2.5) return '#e0a100'
  return '#e5484d'
}

async function resolvePaperId() {
  try {
    const body = await sendRequest('g/set/ppr-res', {
      batch: [{ entity_id: String(stid.value), order: '1' }]
    })
    const batch = (body && body.batch) || []
    return (batch[0] && batch[0].res_id) || ''
  } catch (e) {
    return ''
  }
}

async function startRecord() {
  evalError.value = ''
  evalResult.value = null
  uploadMsg.value = ''
  syncInfo.value = null
  pcmBuffer = null
  spxBytes = null
  try {
    recorder = new PcmRecorder({ sampleRate: 16000 })
    await recorder.start()
    recording.value = true
    recordSeconds.value = 0
    recordStartedAt = Date.now()
    recordTimer = setInterval(() => { recordSeconds.value = Math.round(recorder.duration) }, 250)
  } catch (e) {
    evalError.value = '无法打开麦克风：' + (e && e.message ? e.message : e)
  }
}

async function stopRecord() {
  if (!recorder) return
  recording.value = false
  if (recordTimer) { clearInterval(recordTimer); recordTimer = null }
  evaluating.value = true
  try {
    const pcm = await recorder.stop()
    if (!pcm.length || pcm.length < 16000 * 0.6) throw new Error('录音太短（至少约 0.6 秒）')
    pcmBuffer = pcm
    await userStore.bootstrap().catch(() => {})
    const paperId = await resolvePaperId()
    const category = kind.value === 'read' ? 'read_sentence'
      : kind.value === 'dialogue' ? 'simple_expression_ufi'
      : kind.value === 'picture' ? 'topic' : 'read_sentence'
    const session = ise.buildSession(userStore, {
      sceneType: homeworkId.value ? 'homework' : 'practice',
      sceneId: homeworkId.value || setId.value || '',
      paperId,
      category,
      region: 'shanghai'
    })
    evalSession = session
    const enc = await ise.encodeSpeex(pcm)
    spxBytes = enc.spx
    const result = await ise.evaluateEncoded(enc.spx, session, { timeoutMs: 120000 })
    if (!result || !result.xml) throw new Error('评测服务未返回结果：' + ((result && result.msg) || ''))
    evalResult.value = result
    if (result.scores && result.scores.isRejected) {
      ElMessage.warning('本次录音被评测拒绝，请重试')
    } else {
      ElMessage.success('评测完成')
    }
  } catch (e) {
    evalError.value = e && e.message ? e.message : String(e)
  } finally {
    evaluating.value = false
  }
}

/** 上传 mp3/spx/xml 并回传成绩（/m/audio/sync-v2） */
async function uploadResult() {
  if (!evalResult.value || !pcmBuffer || !spxBytes) return
  uploadBusy.value = true
  uploadMsg.value = ''
  syncInfo.value = null
  try {
    const scores = evalResult.value.scores || {}
    if (scores.isRejected) throw new Error('评测被拒绝（未识别到有效朗读），不能回传成绩')
    const resourceId = String(route.query.resource_id || userStore.activeResourceId || '239')
    const ppr = await resolvePaperInfo()
    const category = kind.value === 'read' ? 'read_sentence'
      : kind.value === 'dialogue' ? 'simple_expression_ufi'
      : kind.value === 'picture' ? 'topic' : 'read_sentence'
    const { urls, sync } = await flow.uploadAndSync({
      pcm: pcmBuffer,
      spxBytes,
      xml: evalResult.value.xml,
      traceId: evalResult.value.traceId,
      scores,
      homeworkId: homeworkId.value,
      setId: setId.value,
      entityId: ppr.entityId || stid.value,
      order: ppr.order || 1,
      resourceId,
      firstColumnId: ppr.firstColumnId || '1',
      questionTypeScore: ppr.questionTypeScore || '0.5',
      graduation: ppr.graduation || '0.125',
      category
    })
    syncInfo.value = { point: sync && sync.point, complete: sync && sync.complete, submitTime: sync && sync.submit_time, urls }
    uploadMsg.value = `回传成功：得分 ${fmtScore(sync && sync.point)} / 完成度 ${fmtScore(sync && sync.complete)}`
    ElMessage.success('成绩已回传')
    if (sync && sync.is_complete_and_udpated) {
      try {
        await flow.mistakeUpdate({ homeworkId: homeworkId.value, setId: setId.value, resourceId })
        await flow.setUseTime({ homeworkId: homeworkId.value, resourceId, useTime: (Date.now() - (recordStartedAt || Date.now())) / 1000 })
        uploadMsg.value += '（已完成练习）'
      } catch (e) { /* 非关键 */ }
    }
  } catch (e) {
    uploadMsg.value = '回传失败：' + (e && e.message ? e.message : e)
    ElMessage.error('回传失败')
  } finally {
    uploadBusy.value = false
  }
}

async function resolvePaperInfo() {
  try {
    const body = await sendRequest('g/set/ppr-res', { batch: [{ entity_id: String(stid.value), order: '1' }] })
    const item = ((body && body.batch) || [])[0] || {}
    return {
      entityId: item.entity_id || stid.value,
      order: item.order || 1,
      resId: item.res_id || '',
      firstColumnId: '1',
      questionTypeScore: '0.5',
      graduation: '0.125'
    }
  } catch (e) {
    return { entityId: stid.value, order: 1 }
  }
}

const stid = computed(() => String(route.query.stid || route.query.setid || '900101'))
const setId = computed(() => String(route.query.setid || ''))
const homeworkId = computed(() => String(route.query.homework_id || ''))
const moduleName = computed(() => String(route.query.module || ''))

const loading = ref(false)
const error = ref('')
const steps = ref([])
const content = ref(null)
const dir = ref('')
const fallbackUsed = ref(false)
const showAnswer = ref(true)
const audioUrl = ref('')
const imageUrl = ref('')
const askAudioUrls = ref([])
let loadToken = 0

const parsed = computed(() => parseStructure(content.value))
const kind = computed(() => parsed.value.kind)
const info = computed(() => parsed.value.info || {})
const questions = computed(() => {
  const q = info.value.question
  return Array.isArray(q) ? q : []
})

const typeLabel = computed(() => {
  if (kind.value === 'read') return '朗读'
  if (kind.value === 'dialogue') return '交际应答'
  if (kind.value === 'picture') return '复述 / 表达'
  return '未知题型'
})

const title = computed(() => {
  const q = route.query.name
  if (q) return String(q)
  if (info.value.topic) return String(info.value.topic)
  return '题目练习'
})

const subtitle = computed(() => {
  const parts = []
  if (moduleName.value) parts.push(moduleName.value)
  if (kind.value) parts.push(typeLabel.value)
  return parts.join(' · ') || 'content 包练习'
})

function goBack() {
  if (homeworkId.value) router.push('/homework/' + homeworkId.value)
  else router.back()
}

function mockIllustration(name) {
  const safe = String(name || '').replace(/[<>&"]/g, '')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="320" viewBox="0 0 640 320">
    <defs>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#dbe8ff"/><stop offset="1" stop-color="#eefbf8"/>
      </linearGradient>
    </defs>
    <rect width="640" height="320" fill="url(#sky)"/>
    <circle cx="508" cy="74" r="38" fill="#ffd88a"/>
    <rect x="0" y="228" width="640" height="92" fill="#bfe8df"/>
    <rect x="60" y="120" width="120" height="108" rx="6" fill="#a9c7f2"/>
    <rect x="80" y="140" width="24" height="24" fill="#eef5ff"/><rect x="120" y="140" width="24" height="24" fill="#eef5ff"/>
    <rect x="80" y="176" width="24" height="24" fill="#eef5ff"/><rect x="120" y="176" width="24" height="24" fill="#eef5ff"/>
    <rect x="220" y="96" width="150" height="132" rx="8" fill="#8fb6ea"/>
    <rect x="246" y="120" width="30" height="30" fill="#f2f8ff"/><rect x="296" y="120" width="30" height="30" fill="#f2f8ff"/>
    <rect x="246" y="168" width="30" height="30" fill="#f2f8ff"/><rect x="296" y="168" width="30" height="30" fill="#f2f8ff"/>
    <circle cx="470" cy="196" r="20" fill="#ffb27a"/>
    <rect x="452" y="216" width="36" height="60" rx="12" fill="#5b86c9"/>
    <text x="320" y="306" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="13" fill="#6a86ab">示例图片 · ${safe}</text>
  </svg>`
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
}

async function resolveAssets(token) {
  const { kind: k, info: inf } = parsed.value
  audioUrl.value = ''
  imageUrl.value = ''
  askAudioUrls.value = []
  if (!content.value) return

  const jobs = []
  if (inf.audio) {
    jobs.push(
      resolveMedia(dir.value, inf.audio).then((url) => { if (token === loadToken) audioUrl.value = url })
    )
  }
  if (inf.image) {
    if (isMock) {
      imageUrl.value = mockIllustration(inf.image)
    } else {
      jobs.push(resolveMedia(dir.value, inf.image).then((url) => { if (token === loadToken) imageUrl.value = url }))
    }
  }
  if (k === 'dialogue') {
    const urls = new Array(questions.value.length).fill('')
    questions.value.forEach((q, i) => {
      if (q.askaudio) {
        jobs.push(resolveMedia(dir.value, q.askaudio).then((url) => { urls[i] = url }))
      }
    })
    await Promise.allSettled(jobs)
    if (token === loadToken) askAudioUrls.value = urls
    return
  }
  await Promise.allSettled(jobs)
}

async function load() {
  const token = ++loadToken
  loading.value = true
  error.value = ''
  fallbackUsed.value = false
  content.value = null
  steps.value = []
  audioUrl.value = ''
  imageUrl.value = ''
  askAudioUrls.value = []
  try {
    const res = await loadContentPackage({
      stid: stid.value,
      zipUrl: route.query.url ? String(route.query.url) : ''
    })
    if (token !== loadToken) return
    content.value = res.content
    dir.value = res.dir
    steps.value = res.steps || []
    await resolveAssets(token)
  } catch (e) {
    if (token !== loadToken) return
    steps.value = (e && e.steps) || []
    error.value = e && e.message ? e.message : String(e)
    if (steps.value.length === 0) {
      steps.value = [
        { name: '准备缓存目录', status: 'fail', detail: '未开始' },
        { name: '下载 content 包', status: 'skip', detail: '' },
        { name: '解压 content 包', status: 'skip', detail: '' },
        { name: '读取 content.json', status: 'skip', detail: '' }
      ]
    }
  } finally {
    if (token === loadToken) loading.value = false
  }
}

async function useFallback() {
  const token = ++loadToken
  content.value = getMockContent(stid.value)
  dir.value = '（内置示例，无实际目录）'
  fallbackUsed.value = true
  error.value = ''
  steps.value = [
    { name: '使用内置示例 content.json', status: 'ok', detail: '结构：' + parseStructure(content.value).type }
  ]
  await resolveAssets(token)
  ElMessage.info('已载入内置示例题目')
}

watch(() => route.query.stid, () => { load() })
onMounted(load)
</script>
