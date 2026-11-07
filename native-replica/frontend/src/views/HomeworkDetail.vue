<template>
  <div class="page" v-loading="loading">
    <div class="page-head">
      <div>
        <el-button text size="small" @click="$router.back()">‹ 返回</el-button>
        <h1 class="page-title" style="margin-top: 6px">作业详情</h1>
      </div>
      <div class="page-actions">
        <el-button @click="$router.push('/homework')">作业列表</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error" />

    <template v-if="homework">
      <section class="detail-hero">
        <div>
          <h2>{{ homework.name || homework.set_name }}</h2>
          <div class="sub">
            {{ homework.set_name || '—' }} · {{ homework.first_column_name || homework.column || '作业' }}
            <span v-if="homework.set_module_name"> · {{ homework.set_module_name }}</span>
          </div>
          <div style="margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap">
            <span class="status-pill" :class="homeworkState(homework)" style="background: rgba(255,255,255,.18); color: #fff">
              {{ stateText(homeworkState(homework)) }}
            </span>
            <span v-if="Number(homework.allow_overtime) === 1" class="status-pill" style="background: rgba(255,255,255,.18); color: #fff">允许补做</span>
            <span v-if="homework.need_redo" class="status-pill" style="background: rgba(255,255,255,.18); color: #fff">需重做</span>
          </div>
        </div>
        <div class="detail-stats">
          <div>
            <div class="num">{{ formatScore(homework) }}</div>
            <div class="lab">得分 / {{ homework.total_point || 10 }}</div>
          </div>
          <div>
            <div class="num">{{ Math.round((Number(homework.use_time) || 0) / 60) }}′</div>
            <div class="lab">用时</div>
          </div>
          <div>
            <div class="num">{{ contents.length }}</div>
            <div class="lab">题目</div>
          </div>
        </div>
      </section>

      <div class="home-grid">
        <section class="panel">
          <div class="panel-title">
            <h3>题目列表</h3>
            <span class="hint">点击题目进入练习页（读取 content 包）</span>
          </div>
          <el-empty v-if="contents.length === 0" description="该作业没有下发题目资源" :image-size="72" />
          <div v-for="(item, idx) in contents" :key="item.real_id || idx" class="content-row">
            <div class="content-index">{{ idx + 1 }}</div>
            <div class="content-info">
              <strong>{{ item.first_type_name || item.group_name || '题目 ' + (idx + 1) }}</strong>
              <span>
                {{ item.group_name || '—' }} · {{ fmtSize(item.size) }}
                <template v-if="item.code_id"> · {{ item.code_id }}</template>
              </span>
            </div>
            <div class="content-side">
              <el-tag size="small" effect="plain">{{ item.first_type_name || '听说' }}</el-tag>
              <el-button type="primary" size="small" plain @click="practice(item)">练习</el-button>
            </div>
          </div>
        </section>

        <div style="display: flex; flex-direction: column; gap: 16px">
          <section class="panel">
            <div class="panel-title"><h3>作业要求</h3></div>
            <div class="kv"><span>开始时间</span><b>{{ fmtDate(homework.begin, true) }}</b></div>
            <div class="kv"><span>截止时间</span><b>{{ fmtDate(homework.end, true) }}</b></div>
            <div class="kv"><span>总分</span><b>{{ homework.total_point || 10 }} 分</b></div>
            <div class="kv"><span>难度系数</span><b>{{ homework.difficulty_rate || '—' }}</b></div>
            <div class="kv"><span>允许补做</span><b>{{ Number(homework.allow_overtime) === 1 ? '是' : '否' }}</b></div>
            <div class="kv"><span>说明</span><b>{{ homework.introduction || '—' }}</b></div>
          </section>

          <section class="panel">
            <div class="panel-title"><h3>操作</h3></div>
            <div style="display: flex; flex-direction: column; gap: 8px">
              <el-button type="primary" :disabled="contents.length === 0" @click="startAll">
                {{ homeworkState(homework) === 'done' ? '重新练习第一题' : '开始练习第一题' }}
              </el-button>
              <el-button @click="$router.push('/mistakes')">去错题本订正</el-button>
            </div>
            <p class="small muted" style="margin: 12px 0 0; line-height: 1.7">
              练习页会按「下载 content 包 → 解压 → 读取 content.json」链路加载题目；
              Mock 模式下使用内置样例包。
            </p>
          </section>
        </div>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="未找到该作业" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { fmtDate, fmtSize, homeworkState, stateText } from '../utils'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const error = ref('')
const homework = ref(null)
const baseUrl = ref('')

const contents = computed(() => {
  const hw = homework.value
  if (!hw) return []
  if (Array.isArray(hw.contents) && hw.contents.length) return hw.contents
  const out = []
  for (const st of hw.structs || []) {
    for (const c of st.contents || []) {
      out.push({ ...c, _base_url: hw.base_url || st.base_url || '' })
    }
  }
  return out
})

function formatScore(hw) {
  const p = Number(hw.point || 0)
  return Number.isFinite(p) ? Math.round(p * 10) / 10 : 0
}

function zipUrlOf(item) {
  const base = item._base_url || baseUrl.value || homework.value.base_url || ''
  if (!item.url) return ''
  if (/^https?:\/\//i.test(item.url)) return item.url
  return base ? String(base).replace(/\/?$/, '/') + item.url : item.url
}

function practice(item) {
  router.push({
    path: '/practice',
    query: {
      stid: String(item.real_id || item.stid || ''),
      setid: String(homework.value.set_id || ''),
      homework_id: String(homework.value.id || ''),
      name: homework.value.name || homework.value.set_name || '',
      url: zipUrlOf(item)
    }
  })
}

function startAll() {
  if (contents.value.length) practice(contents.value[0])
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const body = await api.getHomeworkInfo(route.params.id)
    const hw = body && body.data && !Array.isArray(body.data) ? body.data : body
    homework.value = hw || null
    baseUrl.value = (body && body.base_url) || (hw && hw.base_url) || ''
  } catch (e) {
    error.value = e && e.message ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
