import { createRouter, createWebHistory } from 'vue-router'

import { useAuth } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '管理员登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppShell.vue'),
      children: [
        { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '仪表盘' } },
        { path: 'trackings', name: 'trackings', component: () => import('@/views/TrackingsView.vue'), meta: { title: '运单管理' } },
        { path: 'trackings/:id', name: 'tracking-detail', component: () => import('@/views/TrackingDetailView.vue'), meta: { title: '运单详情' } },
        { path: 'recipients', name: 'recipients', component: () => import('@/views/RecipientsView.vue'), meta: { title: '收件人' } },
        { path: 'settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: '系统设置' } },
        { path: 'runs', name: 'runs', component: () => import('@/views/RunsView.vue'), meta: { title: '运行记录' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  await auth.initialize()
  if (!to.meta.public && !auth.state.admin) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.name === 'login' && auth.state.admin) return { name: 'dashboard' }
  document.title = `${String(to.meta.title ?? '管理后台')} · DelTracking`
})

export default router
