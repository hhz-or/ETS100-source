import { createRouter, createWebHashHistory } from 'vue-router'
import { getToken } from '../api'

const MainLayout = () => import('../layout/MainLayout.vue')

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { public: true, title: '登录' }
  },
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', redirect: '/home' },
      { path: 'home', name: 'home', component: () => import('../views/Home.vue'), meta: { title: '首页' } },
      { path: 'homework', name: 'homework', component: () => import('../views/Homework.vue'), meta: { title: '作业' } },
      { path: 'homework/:id', name: 'homeworkDetail', component: () => import('../views/HomeworkDetail.vue'), meta: { title: '作业详情' } },
      { path: 'sets', name: 'sets', component: () => import('../views/Sets.vue'), meta: { title: '套卷' } },
      { path: 'courses', name: 'courses', component: () => import('../views/Courses.vue'), meta: { title: '同步课程' } },
      { path: 'practice', name: 'practice', component: () => import('../views/Practice.vue'), meta: { title: '练习' } },
      { path: 'mistakes', name: 'mistakes', component: () => import('../views/Mistakes.vue'), meta: { title: '错题本' } },
      { path: 'settings', name: 'settings', component: () => import('../views/Settings.vue'), meta: { title: '设置' } },
      { path: 'about', name: 'about', component: () => import('../views/About.vue'), meta: { title: '关于' } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const hasToken = !!getToken()
  if (!to.meta.public && !hasToken) {
    return { path: '/login', query: to.fullPath !== '/home' ? { redirect: to.fullPath } : {} }
  }
  if (to.name === 'login' && hasToken) return { path: '/home' }
  return true
})

router.afterEach((to) => {
  const title = to.meta && to.meta.title
  document.title = title ? `${title} · E听说` : 'E听说'
})

export default router
