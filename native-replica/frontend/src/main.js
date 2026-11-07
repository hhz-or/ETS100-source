import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './styles.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn, size: 'default' })
app.mount('#app')

// 移除 index.html 的启动占位屏
const placeholder = document.getElementById('placeholderScreen')
if (placeholder) placeholder.remove()
