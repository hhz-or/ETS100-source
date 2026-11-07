<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-brand">
        <div class="brand-logo">E</div>
        <div class="brand-text">
          <strong>E听说</strong>
          <span>ETS REPLICA</span>
        </div>
      </div>

      <div class="topbar-center">
        <span class="topbar-grade">{{ store.gradeName || '同步学习' }}</span>
        <el-tag v-if="store.isMockMode" type="warning" effect="plain" size="small" round>
          Mock 预览模式
        </el-tag>
      </div>

      <div class="topbar-actions">
        <el-tooltip content="公告" placement="bottom">
          <el-button text circle @click="showNotice">🔔</el-button>
        </el-tooltip>
        <el-tooltip content="当前学习卡" placement="bottom">
          <el-button text circle @click="$router.push('/settings')">💳</el-button>
        </el-tooltip>

        <el-dropdown trigger="click" @command="onCommand">
          <div class="user-chip">
            <div class="avatar">{{ initial }}</div>
            <div class="user-meta">
              <strong>{{ store.displayName }}</strong>
              <span>{{ store.schoolName || 'E听说学习中心' }}</span>
            </div>
            <span class="small muted">▾</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">账号与设置</el-dropdown-item>
              <el-dropdown-item command="about">关于本复刻</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="layout-body">
      <aside class="sidebar">
        <nav>
          <div
            v-for="item in navs"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="go(item.path)"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </div>
        </nav>
        <div class="sidebar-foot">
          <div class="ecard-mini" v-if="ecard">
            <strong>{{ ecard.name }}</strong>
            {{ ecard.school_name || '—' }}<br />
            有效期至 {{ (ecard.expire_time || '').slice(0, 10) || '—' }}
          </div>
          <el-button text size="small" @click="$router.push('/about')">
            v5.7.9 · 原生复刻
          </el-button>
        </div>
      </aside>

      <main class="content">
        <div v-if="store.isMockMode" class="mock-banner">
          <span class="dot"></span>
          <span>
            当前为浏览器 Mock 预览：所有接口与插件调用均使用内置演示数据，不访问真实服务器；
            在 WebView2 壳中运行时会自动切换到原生桥。
          </span>
        </div>

        <div v-if="!store.ready" class="panel page-loading">
          <div style="text-align: center">
            <el-skeleton :rows="5" animated style="width: min(680px, 80vw)" />
            <p class="small muted" style="margin-top: 12px">正在同步账号与学习卡数据…</p>
          </div>
        </div>

        <router-view v-else v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const store = useUserStore()

const navs = [
  { path: '/home', label: '首页', icon: '⌂' },
  { path: '/homework', label: '我的作业', icon: '☑' },
  { path: '/sets', label: '套卷练习', icon: '▤' },
  { path: '/courses', label: '同步课程', icon: '✦' },
  { path: '/mistakes', label: '错题本', icon: '✎' },
  { path: '/settings', label: '设置', icon: '⚙' },
  { path: '/about', label: '关于', icon: 'ⓘ' }
]

const initial = computed(() => String(store.displayName || '同').slice(0, 1))
const ecard = computed(() => store.activeEcard)

function isActive(path) {
  if (path === '/home') return route.path === '/home' || route.path === '/'
  if (path === '/homework') return route.path.startsWith('/homework')
  return route.path === path
}

function go(path) {
  if (route.path !== path) router.push(path)
}

function showNotice() {
  const a = store.announcement
  if (!a || (!a.title && !a.detail)) {
    ElMessage.info('暂无公告')
    return
  }
  ElNotification({
    title: a.title || '公告',
    message: a.detail || '暂无公告内容',
    duration: 6000,
    position: 'bottom-right'
  })
}

async function onCommand(cmd) {
  if (cmd === 'settings') router.push('/settings')
  if (cmd === 'about') router.push('/about')
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出当前账号吗？', '退出登录', {
        confirmButtonText: '退出',
        cancelButtonText: '取消',
        type: 'warning'
      })
    } catch { return }
    await store.logout()
    ElMessage.success('已退出登录')
    router.replace('/login')
  }
}

onMounted(() => {
  store.bootstrap().catch(() => { /* 页面各自展示错误 */ })
})
</script>
