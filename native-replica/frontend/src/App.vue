<template>
  <router-view v-slot="{ Component }">
    <transition name="page-fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { AUTH_EXPIRED_EVENT } from './api'
import { useUserStore } from './stores/user'

const router = useRouter()
const store = useUserStore()

function onAuthExpired() {
  store.reset()
  ElMessage.warning('登录状态已失效，请重新登录')
  const current = router.currentRoute.value.fullPath
  router.replace({
    path: '/login',
    query: current && current !== '/login' ? { redirect: current } : {}
  })
}

onMounted(() => {
  window.addEventListener(AUTH_EXPIRED_EVENT, onAuthExpired)
  const placeholder = document.getElementById('placeholderScreen')
  if (placeholder) placeholder.remove()
})

onUnmounted(() => {
  window.removeEventListener(AUTH_EXPIRED_EVENT, onAuthExpired)
})
</script>
