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
          <article v-for="set in filteredSets" :key="set._key" class="set-card">
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
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const resourceId = computed(() => String(userStore.activeResourceId || '239'))
const loading = ref(false)
const error = ref('')
const columns = ref([])
const sets = ref([])
const baseUrl = ref('')
const activeColumn = ref('all')
const keyword = ref('')

const totalCount = computed(() => {
  const sum = columns.value.reduce((acc, c) => acc + (Number(c.column_set_count) || 0), 0)
  // 服务端的 column_set_count 与实际返回条数可能略有差异（读写套卷在 rw_data 中）
  if (activeColumn.value === 'all' && sets.value.length) return sets.value.length
  return sum
})

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
  const body = await api.getColumns({ resource_id: Number(resourceId.value) })
  columns.value = (body && body.data) || []
  if (activeColumn.value !== 'all' && !columns.value.some((c) => String(c.column_id) === String(activeColumn.value))) {
    activeColumn.value = 'all'
  }
}

async function loadSets() {
  loading.value = true
  error.value = ''
  try {
    // g/set/list 必须带 first_column_id（数组），且一次只查一个栏目；
    // “全部套卷”= 合并各栏目结果并去重。
    const ids = activeColumn.value === 'all'
      ? columns.value.map((c) => Number(c.column_id)).filter(Boolean)
      : [Number(activeColumn.value)]
    const merged = []
    const colName = (cid) => {
      const c = columns.value.find((x) => String(x.column_id) === String(cid))
      return c ? c.column_name : '套卷'
    }
    for (const cid of ids) {
      const body = await api.getSets({ first_column_id: [cid], page: 1, limit: 200, resource_id: resourceId.value })
      if (!baseUrl.value) baseUrl.value = (body && body.base_url) || ''
      // 听说/听力在 data；读写模拟在 rw_data
      const rows = [
        ...((body && (body.data || body.list)) || []),
        ...((body && (body.rw_data || body.read_write_data)) || [])
      ]
      for (const s of rows) {
        const st = (s && s.struct) || {}
        const sid = String(s.set_id || st.set_id || s.id || s.serial_id || '')
        if (!sid) continue
        merged.push({
          ...s,
          _key: `${cid}_${sid}`,
          set_id: sid,
          set_name: s.set_name || st.set_name || '',
          first_column_name: s.first_column_name || colName(cid),
          set_module_name: s.set_module_name || st.module_name || '',
          contents: Array.isArray(s.contents) ? s.contents : (Array.isArray(st.contents) ? st.contents : []),
          difficulty_rate: s.difficulty_rate ?? st.difficulty_rate ?? 0,
          avg_point: s.avg_point ?? 0
        })
      }
    }
    sets.value = merged
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
onMounted(async () => {
  await userStore.bootstrap().catch(() => {})
  await reload()
})
</script>
