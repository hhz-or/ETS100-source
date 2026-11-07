<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">我的作业</h1>
        <p class="page-sub">老师布置的听说作业，按待完成 / 已完成 / 已过期分类</p>
      </div>
      <div class="page-actions">
        <el-select v-model="columnFilter" placeholder="全部类型" clearable style="width: 150px">
          <el-option v-for="c in columnOptions" :key="c" :label="c" :value="c" />
        </el-select>
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="$router.push('/courses')">去同步课程</el-button>
      </div>
    </div>

    <section class="panel">
      <div class="toolbar" style="justify-content: space-between">
        <el-segmented v-model="tab" :options="tabOptions" />
        <span class="small muted">当前分类 {{ filtered.length }} 份 · 全部 {{ list.length }} 份 · 数据来自 g/homework/list</span>
      </div>
    </section>

    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error" />

    <div v-loading="loading" class="homework-list">
      <el-empty v-if="!loading && filtered.length === 0" description="该分类下暂无作业" />

      <article
        v-for="hw in paged"
        :key="hw.id"
        class="homework-card"
        @click="openDetail(hw)"
        style="cursor: pointer"
      >
        <div class="homework-main">
          <div class="homework-title">
            <h3>{{ hw.name || hw.set_name || '未命名作业' }}</h3>
            <span class="status-pill" :class="homeworkState(hw)">{{ stateText(homeworkState(hw)) }}</span>
            <el-tag v-if="hw.need_redo" size="small" type="warning" effect="plain">需重做</el-tag>
          </div>
          <div class="homework-sub">{{ hw.set_name || '—' }}</div>
          <div class="homework-meta">
            <span>类型：<b>{{ hw.first_column_name || hw.column || '—' }}</b></span>
            <span>模块：<b>{{ hw.set_module_name || '—' }}</b></span>
            <span>截止：<b>{{ fmtDate(hw.end, true) }}</b></span>
            <span>题目：<b>{{ (hw.contents && hw.contents.length) || (hw.structs && hw.structs[0] && hw.structs[0].contents ? hw.structs[0].contents.length : 0) }} 题</b></span>
            <span>总分：<b>{{ hw.total_point || 10 }}</b></span>
          </div>
        </div>
        <div class="homework-side">
          <template v-if="homeworkState(hw) === 'done'">
            <div class="homework-score">
              {{ formatScore(hw) }}<small> / {{ hw.total_point || 10 }}</small>
            </div>
            <div class="small muted">用时 {{ Math.round((Number(hw.use_time) || 0) / 60) }} 分钟</div>
            <el-button size="small" @click.stop="openDetail(hw)">查看详情</el-button>
          </template>
          <template v-else>
            <div class="small muted" style="text-align: right">
              {{ homeworkState(hw) === 'overdue' ? '已超过截止时间' : '截止 ' + fmtDate(hw.end, true) }}
              <br />允许补做：{{ Number(hw.allow_overtime) === 1 ? '是' : '否' }}
            </div>
            <el-button type="primary" size="small" @click.stop="start(hw)">
              {{ homeworkState(hw) === 'overdue' ? '查看作业' : '开始练习' }}
            </el-button>
          </template>
        </div>
      </article>
    </div>

    <div v-if="filtered.length > pageSize" style="display: flex; justify-content: center">
      <el-pagination
        v-model:current-page="page"
        background
        layout="prev, pager, next"
        :page-size="pageSize"
        :total="filtered.length"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { fmtDate, homeworkState, stateText } from '../utils'
import { useUserStore } from '../stores/user'

const router = useRouter()
const store = useUserStore()
const loading = ref(false)
const error = ref('')
const list = ref([])
const baseUrl = ref('')
const tab = ref('todo')
const columnFilter = ref('')
const page = ref(1)
const pageSize = 8

const tabOptions = computed(() => [
  { label: '待完成 ' + counts.value.todo, value: 'todo' },
  { label: '已完成 ' + counts.value.done, value: 'done' },
  { label: '已过期 ' + counts.value.overdue, value: 'overdue' }
])

const counts = computed(() => {
  const c = { todo: 0, done: 0, overdue: 0 }
  for (const hw of list.value) c[homeworkState(hw)] += 1
  return c
})

const columnOptions = computed(() => {
  const set = new Set()
  for (const hw of list.value) {
    const label = hw.first_column_name || hw.column
    if (label) set.add(label)
  }
  return [...set]
})

const filtered = computed(() => {
  return list.value
    .filter((hw) => homeworkState(hw) === tab.value)
    .filter((hw) => !columnFilter.value || (hw.first_column_name || hw.column) === columnFilter.value)
})

const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return filtered.value.slice(start, start + pageSize)
})

watch([tab, columnFilter], () => { page.value = 1 })

function formatScore(hw) {
  const point = Number(hw.point || 0)
  return Number.isFinite(point) ? (Math.round(point * 10) / 10) : 0
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await store.bootstrap()
    let parentId = (store.activeEcard && store.activeEcard.parent_id) || ''
    if (!parentId) {
      // bootstrap 未拿到学习卡时直接补一次（页面可独立工作）
      try {
        const e = await api.getEcardList()
        const raw = (e && e.data) || e || []
        const arr = Array.isArray(raw) ? raw : (Array.isArray(raw.data) ? raw.data : [])
        parentId = (arr[0] && arr[0].parent_id) || ''
      } catch { /* ignore */ }
    }
    if (!parentId) throw new Error('没有找到有效班级（学习卡未绑定 parent_id，可在设置页填写设备指纹或重新登录）')
    console.log('[hw] parentId=', parentId, 'ecards=', JSON.stringify((store.ecards || []).map(e => ({ id: e.id, pid: e.parent_id }))))
    // g/homework/list 需要 parent_account_id + 完整参数；状态 0/2/3 合并去重（与参考实现一致）
    const seen = new Set()
    const merged = []
    let firstError = ''
    for (const status of [0, 2, 3]) {
      try {
        const body = await api.getHomeworkList({ parent_account_id: parentId, status, limit: 100 })
        if (body && body.base_url && !baseUrl.value) baseUrl.value = body.base_url
        for (const item of (body && body.data) || []) {
          const key = String(item.id || '')
          if (key && !seen.has(key)) { seen.add(key); merged.push(item) }
        }
      } catch (e) {
        if (!firstError) firstError = e && e.message ? e.message : String(e)
      }
    }
    if (!merged.length && firstError) throw new Error(firstError)
    list.value = merged
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
    // 失败时回退到首页缓存，避免白屏
    try {
      const cached = JSON.parse(localStorage.getItem('ets_homework_cache') || '[]')
      if (Array.isArray(cached) && cached.length) list.value = cached
    } catch { /* ignore */ }
  } finally {
    loading.value = false
  }
}

function openDetail(hw) {
  router.push('/homework/' + hw.id)
}

function start(hw) {
  const contents = (hw.contents && hw.contents.length)
    ? hw.contents
    : (hw.structs && hw.structs[0] && hw.structs[0].contents) || []
  if (!contents.length) {
    ElMessage.info('该作业暂无题目资源，先查看详情')
    openDetail(hw)
    return
  }
  const first = contents[0]
  const base = hw.base_url || (hw.structs && hw.structs[0] && hw.structs[0].base_url) || baseUrl.value || ''
  const zipUrl = first.url ? (base ? String(base).replace(/\/?$/, '/') + first.url : first.url) : ''
  router.push({
    path: '/practice',
    query: {
      stid: String(first.real_id || first.stid || ''),
      setid: String(hw.set_id || ''),
      homework_id: String(hw.id || ''),
      name: hw.name || hw.set_name || '',
      url: zipUrl
    }
  })
}

onMounted(load)
</script>
