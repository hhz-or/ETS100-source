<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">设置</h1>
        <p class="page-sub">账号、学习卡、设备与本地运行环境</p>
      </div>
      <div class="page-actions">
        <el-button @click="$router.push('/about')">关于本复刻</el-button>
      </div>
    </div>

    <div class="settings-grid">
      <div style="display: flex; flex-direction: column; gap: 16px">
        <section class="panel">
          <div class="panel-title"><h3>账号信息</h3><span class="hint">user/info</span></div>
          <div class="kv-grid">
            <div class="kv"><span>姓名</span><b>{{ store.displayName }}</b></div>
            <div class="kv"><span>手机号</span><b>{{ store.profile?.phone || '—' }}</b></div>
            <div class="kv"><span>年级</span><b>{{ store.profile?.grade_name || '—' }}</b></div>
            <div class="kv"><span>学段</span><b>{{ store.profile?.school_year_name || '—' }}</b></div>
            <div class="kv"><span>地区</span><b>{{ store.profile?.province_name || '—' }}{{ store.profile?.city_name ? ' · ' + store.profile.city_name : '' }}</b></div>
            <div class="kv"><span>账号 ID</span><b>{{ store.profile?.recent_account_id || '—' }}</b></div>
          </div>
          <div style="margin-top: 16px; display: flex; gap: 8px">
            <el-button @click="refresh">刷新资料</el-button>
            <el-button type="danger" plain @click="logout">退出登录</el-button>
          </div>
        </section>

        <section class="panel">
          <div class="panel-title">
            <h3>我的学习卡</h3>
            <span class="hint">m/ecard/list · 点击切换当前学习卡</span>
          </div>
          <el-empty v-if="store.ecards.length === 0" description="暂无学习卡" :image-size="64" />
          <div
            v-for="card in store.ecards"
            :key="card.id"
            class="ecard-row"
            :class="{ active: store.activeEcard && String(card.id) === String(store.activeEcard.id) }"
            @click="chooseEcard(card)"
          >
            <div class="ecard-badge">{{ (card.grade || 'E').slice(0, 1) }}</div>
            <div class="ecard-info">
              <strong>{{ card.name }}</strong>
              <span>{{ card.school_name || '—' }} · {{ card.grade }} · 至 {{ (card.expire_time || '').slice(0, 10) }}</span>
            </div>
            <el-tag v-if="store.activeEcard && String(card.id) === String(store.activeEcard.id)" size="small" effect="dark">使用中</el-tag>
            <el-tag v-else size="small" effect="plain">切换</el-tag>
          </div>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>设备信息</h3><span class="hint">ShellHelper.getpcinfo</span></div>
          <div class="kv-grid">
            <div class="kv"><span>计算机名</span><b>{{ pcinfo.computername || '—' }}</b></div>
            <div class="kv"><span>系统</span><b>{{ pcinfo.SystemVersion || '—' }}</b></div>
            <div class="kv"><span>位数</span><b>{{ pcinfo.OsBit ? pcinfo.OsBit + ' 位' : '—' }}</b></div>
            <div class="kv"><span>设备码</span><b class="mono">{{ device.device_code || '—' }}</b></div>
            <div class="kv"><span>本地 IP</span><b>{{ device.local_ip || '—' }}</b></div>
            <div class="kv"><span>客户端版本</span><b>{{ pcinfo.Version || '5.7.9' }}</b></div>
          </div>
        </section>
      </div>

      <div style="display: flex; flex-direction: column; gap: 16px">
        <section class="panel">
          <div class="panel-title"><h3>音频与网络</h3></div>
          <div class="setting-row">
            <div class="lab">系统音量<span>ShellHelper.setvolume</span></div>
            <div style="display: flex; align-items: center; gap: 10px; width: 190px">
              <el-slider v-model="volume" :min="0" :max="100" style="flex: 1" @change="saveVolume" />
              <span class="small muted" style="width: 32px; text-align: right">{{ volume }}</span>
            </div>
          </div>
          <div class="setting-row">
            <div class="lab">网络检测<span>ShellHelper.checkadapter</span></div>
            <el-button size="small" @click="checkNetwork">检测</el-button>
          </div>
          <div class="setting-row">
            <div class="lab">麦克风检测<span>soundhelper（未实现）</span></div>
            <el-tag size="small" type="info" effect="plain">未实现</el-tag>
          </div>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>本地目录</h3><span class="hint">__core.info</span></div>
          <div class="kv"><span>程序目录</span><b class="mono" style="font-size: 11px">{{ core.appDir || '—' }}</b></div>
          <div class="kv"><span>数据目录</span><b class="mono" style="font-size: 11px">{{ core.dataDir || '—' }}</b></div>
          <div class="kv"><span>缓存目录</span><b class="mono" style="font-size: 11px">{{ core.cacheDir || '—' }}</b></div>
          <div class="kv"><span>首页地址</span><b class="mono" style="font-size: 11px">{{ core.homeUrl || '—' }}</b></div>
          <div style="margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button size="small" @click="copyPath">复制缓存目录</el-button>
            <el-button size="small" disabled>清理缓存（未实现）</el-button>
            <el-button size="small" disabled>检查更新（未实现）</el-button>
          </div>
        </section>

        <section class="panel">
          <div class="panel-title"><h3>运行模式</h3></div>
          <div class="kv"><span>桥接模式</span><b>{{ isMock ? 'Mock（浏览器预览）' : 'Native（window.cef.message）' }}</b></div>
          <div class="kv"><span>MQ 端口</span><b>{{ mqPort || '40001（默认）' }}</b></div>
          <div class="kv"><span>登录 token</span><b class="mono" style="font-size: 11px">{{ tokenPreview }}</b></div>
          <p class="small muted" style="margin: 12px 0 0; line-height: 1.7">
            设置项仅保存在本机 localStorage，不写入源码；退出登录会清除 token。
          </p>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'
import { getToken, getDeviceInfo } from '../api'
import { coreInfo, invokeJson, isMock } from '../bridge'

const router = useRouter()
const store = useUserStore()

const volume = ref(80)
const pcinfo = ref({})
const device = ref({})
const core = ref({})
const mqPort = ref('')

const tokenPreview = computed(() => {
  const t = getToken()
  if (!t) return '—'
  return t.length > 18 ? t.slice(0, 10) + '…' + t.slice(-6) : t
})

async function loadEnv() {
  try {
    const info = await coreInfo()
    if (info && typeof info === 'object') core.value = info
  } catch { /* ignore */ }
  try {
    device.value = await getDeviceInfo()
    pcinfo.value = (device.value && device.value.raw) || {}
  } catch { /* ignore */ }
  try {
    const cfg = await invokeJson('ShellHelper', 'getconfig', '', 5000)
    mqPort.value = cfg && (cfg.suspensionBallPort || cfg.port) ? String(cfg.suspensionBallPort || cfg.port) : ''
  } catch { /* ignore */ }
  try {
    const v = await invokeJson('ShellHelper', 'getvolume', '', 5000)
    if (v && typeof v === 'object' && Number.isFinite(Number(v.volume))) volume.value = Number(v.volume)
  } catch { /* ignore */ }
}

async function saveVolume(val) {
  try {
    await invokeJson('ShellHelper', 'setvolume', { volume: Number(val) }, 5000)
    ElMessage.success('音量已设置为 ' + val)
  } catch (e) {
    ElMessage.warning('设置音量失败：' + (e && e.message ? e.message : e))
  }
}

async function checkNetwork() {
  try {
    const r = await invokeJson('ShellHelper', 'checkadapter', '', 8000)
    if (r && (r.rncode === 1 || r.normal)) ElMessage.success(r.rnmsg || '网卡正常')
    else ElMessage.warning((r && r.rnmsg) || '网络检测返回未知结果')
  } catch (e) {
    ElMessage.error('网络检测失败：' + (e && e.message ? e.message : e))
  }
}

async function copyPath() {
  const path = core.value.cacheDir || ''
  if (!path) return ElMessage.info('暂无缓存目录')
  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success('已复制缓存目录')
  } catch {
    ElMessage.info(path)
  }
}

async function chooseEcard(card) {
  store.setActiveEcard(card.id)
  ElMessage.success('已切换到「' + card.name + '」')
  await store.bootstrap(true)
}

async function refresh() {
  await store.bootstrap(true)
  ElMessage.success('资料已刷新')
}

async function logout() {
  try {
    await ElMessageBox.confirm('退出后将返回登录页，确定继续吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch { return }
  await store.logout()
  router.replace('/login')
}

onMounted(loadEnv)
</script>
