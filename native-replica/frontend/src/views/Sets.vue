<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">套卷练习</h1>
        <p class="page-sub">按栏目选择套卷，覆盖听说模拟与专项训练</p>
      </div>
      <div class="page-actions">
        <el-input v-model="keyword" placeholder="搜索套卷名称" clearable style="width: 200px" />
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error" />

    <div class="sets-layout">
      <section class="panel">
        <div class="panel-title"><h3>栏目</h3><span class="hint">g/set/column-v2</span></div>
        <div class="column-list">
          <div class="column-item" :class="{ active: activeColumn === 'all' }" @click="selectColumn('all')">
            <strong>全部套卷</strong>
            <span>目录共 {{ totalCount }} 套</span>
          </div>
          <div
            v-for="col in columns"
            :key="col.column_id"
            class="column-item"
            :class="{ active: String(activeColumn) === String(col.column_id) }"
            @click="selectColumn(col.column_id)"
          >
            <strong>{{ col.column_name }}</strong>
            <span>{{ col.column_set_count || 0 }} 套 · 已完成 {{ col.column_set_complete_count || 0 }}</span>
          </div>
        </div>
      </section>

      <section v-loading="loading" class="panel" style="min-height: 380px">
        <div class="panel-title">
          <h3>{{ currentColumnName }}</h3>
          <span class="hint">{{ filteredSets.length }} 套可选</span>
        </div>

        <el-empty v-if="!loading && filteredSets.length === 0" description="该栏目暂无套卷" />

        <div class="set-grid">
          <article v-for="set in filteredSets" :key="set.set_id" class="set-card">
            <div>
              <div class="set-tags">
                <el-tag size="small" effect="plain">{{ set.first_column_name || '套卷' }}</el-tag>
                <el-tag size="small" type="success" effect="plain">{{ set.set_module_name || '考试' }}</el-tag>
              </div>
              <h4 style="margin-top: 10px">{{ set.set_name }}</h4>
            </div>
            <div class="set-tags">
              <span class="small muted">难度 {{ difficultyText(set.difficulty_rate) }}</span>
              <span class="small muted">· {{ (set.contents && set.contents.length) || 0 }} 题</span>
              <span v-if="Number(set.avg_point) > 0" class="small muted">· 平均 {{ set.avg_point }} 分</span>
            </div>
            <div class="set-foot">
              <span class="small muted">set_id {{ set.set_id }}</span>
              <el-button type="primary" size="small" @click="openPractice(set)">开始练习</el-button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const columns = ref([])
const sets = ref([])
const baseUrl = ref('')
const activeColumn = ref('all')
const keyword = ref('')

const totalCount = computed(() => columns.value.reduce((sum, c) => sum + (Number(c.column_set_count) || 0), 0))

const currentColumnName = computed(() => {
  if (activeColumn.value === 'all') return '全部套卷'
  const col = columns.value.find((c) => String(c.column_id) === String(activeColumn.value))
  return col ? col.column_name : '套卷'
})

const filteredSets = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return sets.value
  return sets.value.filter((s) => String(s.set_name || '').toLowerCase().includes(kw))
})

function difficultyText(rate) {
  const n = Number(rate)
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n < 0.4) return '简单'
  if (n < 0.7) return '中等'
  return '较难'
}

async function loadColumns() {
  const body = await api.getColumns({})
  columns.value = (body && body.data) || []
}

async function loadSets() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: 1, limit: 50 }
    if (activeColumn.value !== 'all') params.column_id = activeColumn.value
    const body = await api.getSets(params)
    sets.value = (body && (body.data || body.list)) || []
    baseUrl.value = (body && body.base_url) || ''
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
    sets.value = []
  } finally {
    loading.value = false
  }
}

function selectColumn(id) {
  if (String(activeColumn.value) === String(id)) return
  activeColumn.value = id
}

function openPractice(set) {
  const contents = (set.contents && set.contents.length)
    ? set.contents
    : (set.structs && set.structs[0] && set.structs[0].contents) || []
  const first = contents[0] || {}
  const base = set.base_url || baseUrl.value || (set.structs && set.structs[0] && set.structs[0].base_url) || ''
  const zipUrl = first.url ? (base ? base.replace(/\/?$/, '/') + first.url : first.url) : ''
  router.push({
    path: '/practice',
    query: {
      stid: String(first.real_id || first.stid || set.set_id || ''),
      setid: String(set.set_id || ''),
      name: set.set_name || '',
      url: zipUrl
    }
  })
}

async function reload() {
  try {
    await loadColumns()
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
  }
  await loadSets()
}

watch(activeColumn, loadSets)
onMounted(reload)
</script>
