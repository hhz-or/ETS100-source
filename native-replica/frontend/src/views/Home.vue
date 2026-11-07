<template>
  <div class="page">
    <section class="hero">
      <div class="hero-inner">
        <div>
          <h2>{{ greeting(store.displayName) }}</h2>
          <p>
            {{ todayText() }}<span v-if="store.gradeName"> · {{ store.gradeName }}</span>。
            今天有 <b>{{ overview.todo }}</b> 份待完成作业，错题本还有 <b>{{ overview.mistakes }}</b> 道待订正。
          </p>
          <div class="hero-actions">
            <el-button type="primary" @click="$router.push('/homework')">去完成作业</el-button>
            <el-button plain style="color: #fff; border-color: rgba(255, 255, 255, 0.6); background: transparent" @click="$router.push('/courses')">
              继续同步学习
            </el-button>
          </div>
        </div>
        <div class="hero-stats">
          <div class="hero-stat">
            <div class="num">{{ overview.todo }}</div>
            <div class="lab">待完成作业</div>
          </div>
          <div class="hero-stat">
            <div class="num">{{ overview.mistakes }}</div>
            <div class="lab">待订正错题</div>
          </div>
          <div class="hero-stat">
            <div class="num">{{ overview.daysLeft }}</div>
            <div class="lab">学习卡剩余天数</div>
          </div>
        </div>
      </div>
    </section>

    <div class="quick-grid">
      <div class="metric-card" @click="$router.push('/homework')">
        <div class="metric-head">
          <div class="metric-icon">📝</div>
          <span class="status-pill todo">{{ overview.todo }} 份待完成</span>
        </div>
        <div class="metric-value">{{ overview.todo }}</div>
        <div class="metric-label">今日作业</div>
        <div class="metric-foot"><span>截止时间与老师要求</span><span>查看 ›</span></div>
      </div>

      <div class="metric-card" @click="$router.push('/mistakes')">
        <div class="metric-head">
          <div class="metric-icon orange">✎</div>
          <span class="status-pill done">已订正 {{ overview.corrected }}</span>
        </div>
        <div class="metric-value">{{ overview.mistakes }}</div>
        <div class="metric-label">错题待订正</div>
        <div class="metric-foot"><span>听说 {{ mistake.audio }} · 读写 {{ mistake.read_write }}</span><span>订正 ›</span></div>
      </div>

      <div class="metric-card" @click="$router.push('/settings')">
        <div class="metric-head">
          <div class="metric-icon teal">💳</div>
          <span class="small muted">{{ ecard ? ecard.grade : '未绑定' }}</span>
        </div>
        <div class="metric-value" style="font-size: 18px">{{ ecard ? ecard.name : '暂无学习卡' }}</div>
        <div class="metric-label">{{ ecard ? ecard.school_name : '绑定后解锁同步课程' }}</div>
        <div class="metric-foot">
          <span>{{ ecard ? '到期 ' + (ecard.expire_time || '').slice(0, 10) : '—' }}</span>
          <span>管理 ›</span>
        </div>
      </div>
    </div>

    <section class="panel">
      <div class="panel-title">
        <h3>学习模块</h3>
        <span class="hint">按原作信息架构组织的快捷入口</span>
      </div>
      <div class="module-grid">
        <div v-for="m in modules" :key="m.title" class="module-card" :class="{ disabled: m.disabled }" @click="openModule(m)">
          <div class="mi">{{ m.icon }}</div>
          <strong>{{ m.title }}</strong>
          <span>{{ m.desc }}</span>
          <el-tag v-if="m.disabled" size="small" type="info" effect="plain" style="align-self: flex-start">未实现</el-tag>
        </div>
      </div>
    </section>

    <div class="home-grid">
      <section class="panel">
        <div class="panel-title">
          <h3>最近作业</h3>
          <el-button text size="small" @click="$router.push('/homework')">全部作业 ›</el-button>
        </div>
        <el-empty v-if="!loading && recentHomework.length === 0" description="暂无作业" :image-size="72" />
        <div v-else>
          <div v-for="hw in recentHomework" :key="hw.id" class="mini-hw" @click="$router.push('/homework/' + hw.id)">
            <div class="date">
              <b>{{ dayOf(hw.end) }}</b>
              <span>{{ monthOf(hw.end) }}月</span>
            </div>
            <div class="info">
              <strong>{{ hw.name || hw.set_name }}</strong>
              <span>{{ hw.first_column_name || hw.column || '作业' }} · {{ stateText(homeworkState(hw)) }}</span>
            </div>
            <span class="status-pill" :class="homeworkState(hw)">{{ stateText(homeworkState(hw)) }}</span>
          </div>
        </div>
      </section>

      <div style="display: flex; flex-direction: column; gap: 16px">
        <section class="panel">
          <div class="panel-title"><h3>学习卡</h3></div>
          <div v-if="store.ecards.length === 0" class="muted small">暂无学习卡</div>
          <div v-for="card in store.ecards.slice(0, 3)" :key="card.id" class="ecard-row" :class="{ active: ecard && card.id === ecard.id }" @click="switchEcard(card)">
            <div class="ecard-badge">{{ (card.grade || 'E').slice(0, 1) }}</div>
            <div class="ecard-info">
              <strong>{{ card.name }}</strong>
              <span>{{ card.school_name || '—' }} · 至 {{ (card.expire_time || '').slice(0, 10) }}</span>
            </div>
            <el-tag v-if="ecard && card.id === ecard.id" size="small" effect="dark">使用中</el-tag>
          </div>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>公告</h3></div>
          <div v-if="store.announcement && (store.announcement.title || store.announcement.detail)" class="notice-box">
            <strong>{{ store.announcement.title || '公告' }}</strong><br />
            {{ store.announcement.detail || '暂无公告内容' }}
          </div>
          <div v-else class="muted small">暂无公告。</div>
        </section>
      </div>
    </div>

    <div v-if="error" class="panel muted small">部分数据加载失败：{{ error }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useUserStore } from '../stores/user'
import { daysLeft, greeting, homeworkState, stateText, todayText } from '../utils'

const router = useRouter()
const store = useUserStore()

const loading = ref(true)
const error = ref('')
const homeworkList = ref([])
const mistake = reactive({ audio: 0, read_write: 0, corrected: 0, total: 0 })
const advertisements = ref([])

const ecard = computed(() => store.activeEcard)

const overview = computed(() => {
  const todo = homeworkList.value.filter((h) => homeworkState(h) === 'todo').length
  const mistakes = Number(mistake.audio || 0) + Number(mistake.read_write || 0)
  const dl = ecard.value ? daysLeft(ecard.value.expire_time ? Date.parse(ecard.value.expire_time.replace(/-/g, '/')) / 1000 : 0) : null
  return {
    todo,
    mistakes,
    corrected: Number(mistake.corrected || 0),
    daysLeft: dl === null || Number.isNaN(dl) ? '—' : Math.max(0, dl)
  }
})

const recentHomework = computed(() => {
  const rank = { todo: 0, overdue: 1, done: 2 }
  return [...homeworkList.value]
    .sort((a, b) => (rank[homeworkState(a)] ?? 3) - (rank[homeworkState(b)] ?? 3))
    .slice(0, 4)
})

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    await store.bootstrap()
    let parentId = (store.activeEcard && store.activeEcard.parent_id) || ''
    if (!parentId) {
      try {
        const e = await api.getEcardList()
        const raw = (e && e.data) || e || []
        const arr = Array.isArray(raw) ? raw : (Array.isArray(raw.data) ? raw.data : [])
        parentId = (arr[0] && arr[0].parent_id) || ''
      } catch { /* ignore */ }
    }
    const [hwRes, mkRes, adRes] = await Promise.allSettled([
      (async () => {
        const seen = new Set()
        const merged = []
        for (const status of [0, 2, 3]) {
          try {
            const body = await api.getHomeworkList({ parent_account_id: parentId, status, limit: 50 })
            for (const item of (body && body.data) || []) {
              const key = String(item.id || '')
              if (key && !seen.has(key)) { seen.add(key); merged.push(item) }
            }
          } catch { /* one status may be empty */ }
        }
        return { data: merged }
      })(),
      api.getMistakeSummary({ parent_account_id: parentId }),
      api.getAdvertisements()
    ])
    if (hwRes.status === 'fulfilled' && hwRes.value) {
      homeworkList.value = Array.isArray(hwRes.value.data) ? hwRes.value.data : []
      try { localStorage.setItem('ets_homework_cache', JSON.stringify(homeworkList.value.slice(0, 50))) } catch { /* ignore */ }
    }
    if (mkRes.status === 'fulfilled' && mkRes.value) {
      const summary = mkRes.value
      mistake.audio = (summary.to_correct_count && summary.to_correct_count.audio) || 0
      mistake.read_write = (summary.to_correct_count && summary.to_correct_count.read_write) || 0
      mistake.corrected =
        ((summary.corrected_count && summary.corrected_count.audio) || 0) +
        ((summary.corrected_count && summary.corrected_count.read_write) || 0)
    }
    if (adRes.status === 'fulfilled' && adRes.value) {
      advertisements.value = adRes.value.advertisement || []
    }
    const failures = [hwRes, mkRes, adRes].filter((r) => r.status === 'rejected')
    if (failures.length) error.value = failures[0].reason && failures[0].reason.message ? failures[0].reason.message : String(failures[0].reason)
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

const modules = [
  { title: '同步课程', desc: '教材 · 单元 · 模块逐层练习', icon: '📚', path: '/courses' },
  { title: '套卷练习', desc: '听说模拟 / 专项套卷', icon: '📄', path: '/sets' },
  { title: '作业中心', desc: '待完成、已完成与过期作业', icon: '🗒️', path: '/homework' },
  { title: '错题本', desc: '按题型沉淀薄弱点', icon: '📌', path: '/mistakes' },
  { title: '专项训练', desc: '音标、词汇、听说专项', icon: '🎯', disabled: true },
  { title: '单词 PK', desc: '在线匹配与排行榜', icon: '⚡', disabled: true },
  { title: '推荐配音', desc: '跟读配音与作品分享', icon: '🎬', disabled: true },
  { title: '学习计划', desc: '老师布置的学习计划', icon: '🗓️', disabled: true }
]

function openModule(m) {
  if (m.disabled) {
    ElMessage.info('该模块暂未实现（见 docs/frontend_build.md 未实现项）')
    return
  }
  router.push(m.path)
}

function switchEcard(card) {
  store.setActiveEcard(card.id)
  ElMessage.success('已切换到「' + card.name + '」')
  load()
}

function dayOf(sec) {
  const n = Number(sec)
  if (!n) return '—'
  return new Date(n * 1000).getDate()
}
function monthOf(sec) {
  const n = Number(sec)
  if (!n) return '—'
  return new Date(n * 1000).getMonth() + 1
}

onMounted(load)
</script>
