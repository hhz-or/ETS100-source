<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">同步课程</h1>
        <p class="page-sub">教材 → 单元 → 模块，逐层进入听说练习</p>
      </div>
      <div class="page-actions">
        <el-select v-model="activeGradeId" placeholder="选择年级" style="width: 130px" @change="onGradeChange">
          <el-option v-for="g in grades" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
        <el-button :loading="loading" @click="reload">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error" />

    <section class="panel">
      <div class="panel-title">
        <h3>教材</h3>
        <span class="hint">g/resource/book-list · 共 {{ booksOfGrade.length }} 本</span>
      </div>
      <div class="book-strip">
        <div
          v-for="book in booksOfGrade"
          :key="book.id"
          class="book-chip"
          :class="{ active: activeBook && book.id === activeBook.id }"
          @click="selectBook(book)"
        >
          {{ book.display_name || book.name }}<span v-if="book.name"> · {{ book.name }}</span>
        </div>
        <span v-if="booksOfGrade.length === 0" class="muted small">当前年级暂无教材</span>
      </div>
    </section>

    <div v-loading="loading" class="course-layout">
      <section class="panel">
        <div class="panel-title">
          <h3>单元</h3>
          <span class="hint">{{ units.length }} 个</span>
        </div>
        <div class="unit-list">
          <div
            v-for="unit in units"
            :key="unit.unit_id"
            class="unit-item"
            :class="{ active: activeUnit && unit.unit_id === activeUnit.unit_id }"
            @click="selectUnit(unit)"
          >
            <span style="flex: 1">{{ unit.unit_name }}</span>
            <span>{{ unit.unit_set_count || 0 }} 套</span>
          </div>
          <el-empty v-if="units.length === 0" description="暂无单元" :image-size="60" />
        </div>
      </section>

      <section class="panel" style="min-height: 380px">
        <div class="panel-title">
          <h3>{{ activeUnit ? activeUnit.unit_name : '选择单元' }}</h3>
          <span class="hint" v-if="unitInfo">
            {{ unitInfo.unit_set_count || 0 }} 套 · 已完成 {{ unitInfo.unit_set_complete_count || 0 }}
          </span>
        </div>

        <el-empty v-if="!activeUnit" description="请选择左侧单元" />
        <template v-else>
          <div class="module-grid">
            <div v-for="mod in modules" :key="mod.module_id" class="module-card" @click="openModule(mod)">
              <div class="mi">{{ moduleIcon(mod.module_name) }}</div>
              <strong>{{ mod.module_name }}</strong>
              <span>{{ mod.module_set_count || 0 }} 套练习<span v-if="mod.module_set_complete_count"> · 已完成 {{ mod.module_set_complete_count }}</span></span>
              <el-tag v-if="Number(mod.module_is_lock) === 1" size="small" type="info" effect="plain" style="align-self: flex-start">未解锁</el-tag>
              <el-tag v-else size="small" effect="plain" style="align-self: flex-start">进入练习</el-tag>
            </div>
          </div>

          <el-empty v-if="!loading && modules.length === 0" description="该单元暂无模块" :image-size="70" />

          <div class="small muted" style="margin-top: 18px; line-height: 1.7">
            说明：模块练习会打开 content 包并渲染 collector.read / dialogue / picture；
            Mock 模式使用内置示例题，原生模式下由 HttpHelper + SevenZip 解包真实资源。
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useUserStore } from '../stores/user'

const router = useRouter()
const store = useUserStore()

const loading = ref(false)
const error = ref('')
const grades = ref([])
const books = ref([])
const units = ref([])
const modules = ref([])
const unitInfo = ref(null)

const activeGradeId = ref(null)
const activeBook = ref(null)
const activeUnit = ref(null)

const booksOfGrade = computed(() => {
  if (!activeGradeId.value) return books.value
  const grade = grades.value.find((g) => g.id === activeGradeId.value)
  if (!grade) return books.value
  return books.value.filter((b) => String(b.resource_id) === String(grade.resource_id))
})

function moduleIcon(name) {
  if (!name) return '📘'
  if (name.includes('课文')) return '📖'
  if (name.includes('词汇')) return '🔤'
  if (name.includes('听说')) return '🎧'
  if (name.includes('读写')) return '✍️'
  if (name.includes('听力')) return '👂'
  return '📘'
}

async function loadBase() {
  loading.value = true
  error.value = ''
  try {
    await store.bootstrap()
    const [g, b] = await Promise.all([api.getGrades(), api.getBooks({})])
    grades.value = (g && g.grades) || []
    books.value = (b && b.books) || []

    const ecard = store.activeEcard
    const preferred =
      grades.value.find((gr) => ecard && String(gr.resource_id) === String(ecard.resource_id)) ||
      grades.value.find((gr) => gr.name === (ecard && ecard.grade)) ||
      grades.value[0]
    activeGradeId.value = preferred ? preferred.id : null

    const firstBook = booksOfGrade.value[0] || books.value[0] || null
    if (firstBook) await selectBook(firstBook)
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function selectBook(book) {
  activeBook.value = book
  unitInfo.value = null
  modules.value = []
  activeUnit.value = null
  try {
    const body = await api.getUnits({ book_id: book.id, resource_id: book.resource_id })
    units.value = (body && body.data) || []
    if (units.value.length) await selectUnit(units.value[0])
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
    units.value = []
  }
}

async function selectUnit(unit) {
  activeUnit.value = unit
  modules.value = []
  unitInfo.value = null
  loading.value = true
  try {
    const ctx = {
      resource_id: (activeBook.value && activeBook.value.resource_id) || 363,
      book_id: (activeBook.value && activeBook.value.id) || 0,
      unit_id: unit.unit_id,
      is_need_score: 1
    }
    const [infoRes, modRes] = await Promise.allSettled([
      api.getUnitInfo(ctx),
      api.getModules(ctx)
    ])
    if (infoRes.status === 'fulfilled') unitInfo.value = (infoRes.value && infoRes.value.data) || null
    if (modRes.status === 'fulfilled') modules.value = (modRes.value && modRes.value.data) || []
    const bad = [infoRes, modRes].find((r) => r.status === 'rejected')
    if (bad) error.value = bad.reason && bad.reason.message ? bad.reason.message : String(bad.reason)
  } finally {
    loading.value = false
  }
}

async function onGradeChange() {
  const first = booksOfGrade.value[0] || null
  if (first) await selectBook(first)
  else {
    books.value = []
    units.value = []
    modules.value = []
  }
}

function openModule(mod) {
  if (Number(mod.module_is_lock) === 1) {
    ElMessage.warning('该模块尚未解锁')
    return
  }
  const infos = mod.module_set_infos || []
  const firstSetId = infos[0] && infos[0].set_ids && infos[0].set_ids[0]
  if (!firstSetId) {
    ElMessage.info('该模块暂无可练习的套卷')
    return
  }
  router.push({
    path: '/practice',
    query: {
      stid: String(firstSetId),
      setid: String(firstSetId),
      name: `${activeUnit.value ? activeUnit.value.unit_name : ''} · ${mod.module_name}`,
      module: mod.module_name
    }
  })
}

async function reload() {
  await loadBase()
}

onMounted(loadBase)
</script>
