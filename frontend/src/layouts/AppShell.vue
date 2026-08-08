<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { useToast } from '@/composables/toast'
import { useAuth } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const toast = useToast()
const loggingOut = ref(false)
const mobileOpen = ref(false)
const pageTitle = computed(() => String(route.meta.title ?? '管理中心'))

const links = [
  { to: '/', label: '仪表盘', icon: '⌂' },
  { to: '/trackings', label: '运单管理', icon: '▣' },
  { to: '/recipients', label: '收件人', icon: '◎' },
  { to: '/runs', label: '运行记录', icon: '↻' },
  { to: '/settings', label: '系统设置', icon: '⚙' },
]

async function signOut() {
  loggingOut.value = true
  try {
    await auth.logout()
    await router.replace('/login')
  } catch (error) {
    toast.show(error instanceof Error ? error.message : '退出失败', 'error')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div class="app-shell">
    <button class="mobile-menu" type="button" :aria-expanded="mobileOpen" aria-controls="main-navigation" @click="mobileOpen = !mobileOpen">菜单</button>
    <aside id="main-navigation" class="sidebar" :class="{ 'sidebar-open': mobileOpen }" aria-label="主导航">
      <RouterLink class="brand" to="/" aria-label="DelTracking 首页" @click="mobileOpen = false">
        <span class="brand-mark" aria-hidden="true">D</span>
        <span><strong>DelTracking</strong><small>物流追踪管理</small></span>
      </RouterLink>
      <nav class="nav-list">
        <RouterLink v-for="link in links" :key="link.to" class="nav-link" :to="link.to" @click="mobileOpen = false">
          <span class="nav-icon" aria-hidden="true">{{ link.icon }}</span>{{ link.label }}
        </RouterLink>
      </nav>
      <div class="sidebar-account">
        <span class="avatar" aria-hidden="true">{{ auth.state.admin?.username.slice(0, 1).toUpperCase() }}</span>
        <span><strong>{{ auth.state.admin?.username }}</strong><small>管理员</small></span>
        <button type="button" :disabled="loggingOut" @click="signOut">退出</button>
      </div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <div><p class="eyebrow">DELIVERY OPERATIONS</p><h1>{{ pageTitle }}</h1></div>
        <span class="status-pill"><span aria-hidden="true"></span>服务已连接</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>
