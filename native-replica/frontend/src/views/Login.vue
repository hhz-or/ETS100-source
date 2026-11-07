<template>
  <div class="login-page">
    <section class="login-visual">
      <div class="lv-brand">
        <div class="brand-logo">E</div>
        <div>
          <div style="font-size: 17px; font-weight: 700; letter-spacing: 0.5px">E听说</div>
          <div style="font-size: 11px; opacity: 0.72; letter-spacing: 2px">ETS REPLICA · PC</div>
        </div>
      </div>

      <div>
        <h1>
          让每一次开口，<br />都有回响。
          <span>同步教材 · 智能评测 · 错题沉淀</span>
        </h1>
        <div class="login-features">
          <div class="login-feature">
            <div class="fi">🎧</div>
            <div><b>听说同步练</b><br />跟着教材单元练朗读、应答、复述与表达。</div>
          </div>
          <div class="login-feature">
            <div class="fi">📈</div>
            <div><b>即时评分反馈</b><br />录音上传后由评测引擎给出多维评分与解析。</div>
          </div>
          <div class="login-feature">
            <div class="fi">🗂️</div>
            <div><b>错题自动归档</b><br />按题型沉淀薄弱点，支持反复订正。</div>
          </div>
        </div>
      </div>

      <footer>学习用途复刻版本 · 与官方 E听说无关</footer>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <h2>欢迎回来</h2>
        <p class="sub">登录后继续你的英语听说练习</p>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
          <el-form-item label="手机号" prop="phone">
            <el-input
              v-model="form.phone"
              size="large"
              maxlength="11"
              placeholder="请输入手机号"
              autocomplete="username"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              size="large"
              type="password"
              show-password
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button class="login-submit" type="primary" :loading="loading" @click="submit">
            登 录
          </el-button>
        </el-form>

        <div class="login-extra">
          <el-checkbox v-model="remember">记住手机号</el-checkbox>
          <span>忘记密码？请在官方客户端找回</span>
        </div>

        <div v-if="isMock" class="login-demo">
          <span>浏览器 Mock 模式：任意手机号 / 密码均可登录，或一键进入演示账号。</span>
          <el-button size="small" type="warning" plain @click="demoLogin">一键体验</el-button>
        </div>

        <div class="login-foot">
          {{ isMock ? 'MOCK PREVIEW · 数据均为内置示例' : '登录信息仅用于本地加密后提交，不写入源码' }}
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import { isMock } from '../bridge'

const router = useRouter()
const route = useRoute()
const store = useUserStore()

const formRef = ref(null)
const loading = ref(false)
const remember = ref(true)
const form = reactive({
  phone: localStorage.getItem('ets_login_phone') || '',
  password: ''
})

const rules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '请输入 11 位手机号', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, message: '密码至少 4 位', trigger: 'blur' }
  ]
}

async function doLogin(phone, password) {
  loading.value = true
  try {
    await store.login(phone, password)
    try {
      if (remember.value) localStorage.setItem('ets_login_phone', phone)
      else localStorage.removeItem('ets_login_phone')
    } catch { /* ignore */ }
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' && redirect.startsWith('/') ? redirect : '/home')
  } catch (err) {
    const msg = err && err.message ? err.message : '登录失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch { return }
  doLogin(form.phone.trim(), form.password)
}

function demoLogin() {
  form.phone = '13800000000'
  form.password = 'demo1234'
  doLogin(form.phone, form.password)
}

onMounted(() => {
  if (isMock && route.query.autologin === '1' && !loading.value) demoLogin()
})
</script>
