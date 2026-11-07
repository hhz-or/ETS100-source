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
          <audio controls preload="none" :src="audioUrl"></audio>
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
              <audio controls preload="none" :src="askAudioUrls[i]"></audio>
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

const route = useRoute()
const router = useRouter()

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
