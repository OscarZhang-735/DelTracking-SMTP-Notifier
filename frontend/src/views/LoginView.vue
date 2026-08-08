<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuth } from '@/stores/auth'

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const busy = ref(false)
const route = useRoute()
const router = useRouter()
const auth = useAuth()

async function submit() {
  errorMessage.value = ''
  busy.value = true
  try {
    await auth.login(username.value, password.value)
    const destination = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(destination)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败，请稍后重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-intro" aria-labelledby="login-title">
      <div class="brand brand-on-dark"><span class="brand-mark" aria-hidden="true">D</span><span><strong>DelTracking</strong><small>物流追踪管理</small></span></div>
      <div><p class="eyebrow">DELIVERY, WITHOUT THE GUESSWORK</p><h1 id="login-title">让每一次物流变化，都清晰可见。</h1><p class="login-copy">集中管理运单、查询任务与邮件通知。</p></div>
      <p class="login-footnote">会话采用安全 Cookie 保存，敏感操作受 CSRF 保护。</p>
    </section>
    <section class="login-form-panel" aria-labelledby="form-title">
      <form class="login-form" @submit.prevent="submit">
        <div><p class="eyebrow">WELCOME BACK</p><h2 id="form-title">登录管理后台</h2><p>请输入管理员凭据以继续。</p></div>
        <p v-if="errorMessage" class="alert alert-error" role="alert">{{ errorMessage }}</p>
        <label><span>管理员账号</span><input v-model="username" name="username" autocomplete="username" required autofocus placeholder="请输入账号" /></label>
        <label><span>密码</span><input v-model="password" name="password" type="password" autocomplete="current-password" required placeholder="请输入密码" /></label>
        <button class="button button-primary button-block" type="submit" :disabled="busy || !username || !password">{{ busy ? '正在登录…' : '登录' }}</button>
      </form>
    </section>
  </main>
</template>
