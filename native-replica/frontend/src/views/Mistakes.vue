<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">错题本</h1>
        <p class="page-sub">按题型沉淀薄弱点，支持反复订正（听说题进入 content 包练习）</p>
      </div>
      <div class="page-actions">
        <el-select v-model="typeFilter" style="width: 140px">
          <el-option label="全部题型" value="all" />
          <el-option label="听说" value="audio" />
          <el-option label="读写" value="read_write" />
        </el-select>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error" />

    <div class="quick-grid">
      <div class="metric-card">
        <div class="metric-head"><div class="metric-icon orange">🎧</div><span class="small muted">听说</span></div>
        <div class="metric-value">{{ summary.to_correct_count.audio || 0 }}</div>
        <div class="metric-label">待订正听说题</div>
      </div>
      <div class="metric-card">
        <div class="metric-head"><div class="metric-icon">✍️</div><span class="small muted">读写</span></div>
        <div class="metric-value">{{ summary.to_correct_count.read_write || 0 }}</div>
        <div class="metric-label">待订正读写题</div>
      </div>
      <div class="metric-card">
        <div class="metric-head"><div class="metric-icon teal">✅</div><span class="small muted">累计</span></div>
        <div class="metric-value">{{ correctedTotal }}</div>
        <div class="metric-label">已订正题目</div>
      </div>
    </div>

    <section class="panel">
      <div class="toolbar" style="justify-content: space-between">
        <el-segmented v-model="tab" :options="tabOptions" />
        <span class="small muted">数据来自 m/mistake/summary + m/mistake/list</span>
      </div>
    </section>

    <div v-loading="loading" class="mistake-list">
      <el-empty v-if="!loading && filtered.length === 0" description="该分类下暂无错题" />

      <article v-for="item in filtered" :key="item.id" class="mistake-card">
        <div class="mistake-main">
          <div class="mistake-q">{{ item.content || item.value || '题目内容暂缺' }}</div>
          <div class="mistake-meta">
            <el-tag size="small" effect="plain">{{ item.group_name || (item.type === 'read_write' ? '读写' : '听说') }}</el-tag>
            <span>{{ item.set_name || '—' }}</span>
            <span>{{ item.create_time || '—' }}</span>
          </div>
          <div v-if="showAnswer" class="answer-box" style="margin-top: 12px">
            <h4>参考答案</h4>
            <div class="rich-text">{{ item.answer || '—' }}</div>
            <div v-if="item.analyze" class="small muted" style="margin-top: 6px">{{ item.analyze }}</div>
          </div>
        </div>
        <div class="mistake-score">
          <div class="sc" :class="{ pass: (Number(item.score) || 0) >= (Number(item.full_score) || 5) * 0.6 }">
            {{ item.score ?? '—' }}<small style="font-size: 11px; font-weight: 400; color: #9aa7bc"> / {{ item.full_score || 5 }}</small>
          </div>
          <el-tag size="small" :type="item.corrected ? 'success' : 'warning'" effect="plain">
            {{ item.corrected ? '已订正' : '待订正' }}
          </el-tag>
          <el-button size="small" :type="item.corrected ? 'default' : 'primary'" @click="practice(item)">
            {{ item.corrected ? '再做一次' : '去订正' }}
          </el-button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const list = ref([])
const tab = ref('todo')
const typeFilter = ref('all')
const showAnswer = ref(true)
const summary = reactive({
  to_correct_count: { audio: 0, read_write: 0 },
  corrected_count: { audio: 0, read_write: 0 }
})

const tabOptions = [
  { label: '待订正', value: 'todo' },
  { label: '已订正', value: 'done' }
]

const correctedTotal = computed(
  () => (Number(summary.corrected_count.audio) || 0) + (Number(summary.corrected_count.read_write) || 0)
)

const filtered = computed(() => {
  return list.value
    .filter((m) => (tab.value === 'done' ? !!m.corrected : !m.corrected))
    .filter((m) => typeFilter.value === 'all' || m.type === typeFilter.value)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [sumRes, listRes] = await Promise.allSettled([api.getMistakeSummary(), api.getMistakeList({ page: 1, limit: 100 })])
    if (sumRes.status === 'fulfilled' && sumRes.value) {
      const s = sumRes.value
      summary.to_correct_count = s.to_correct_count || { audio: 0, read_write: 0 }
      summary.corrected_count = s.corrected_count || { audio: 0, read_write: 0 }
    }
    if (listRes.status === 'fulfilled' && listRes.value) {
      const body = listRes.value
      list.value = Array.isArray(body.data) ? body.data : Array.isArray(body.list) ? body.list : []
    }
    const bad = [sumRes, listRes].find((r) => r.status === 'rejected')
    if (bad) error.value = bad.reason && bad.reason.message ? bad.reason.message : String(bad.reason)
  } finally {
    loading.value = false
  }
}

function practice(item) {
  router.push({
    path: '/practice',
    query: {
      stid: String(item.entity_id || item.stid || '900101'),
      setid: String(item.set_id || ''),
      name: (item.group_name || '错题') + ' · 订正'
    }
  })
}

onMounted(load)
</script>
