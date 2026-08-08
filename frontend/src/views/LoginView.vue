<script setup lang="ts">
import { ref } from 'vue'

const username = ref('')
const password = ref('')
</script>

<template>
  <main class="login-page">
    <section class="login-intro" aria-labelledby="login-title">
      <div class="brand brand-on-dark">
        <span class="brand-mark" aria-hidden="true">D</span>
        <span>
          <strong>DelTracking</strong>
          <small>物流追踪管理</small>
        </span>
      </div>
      <div>
        <p class="eyebrow">DELIVERY, WITHOUT THE GUESSWORK</p>
        <h1 id="login-title">让每一次物流变化，都清晰可见。</h1>
        <p class="login-copy">集中管理运单、查询任务与邮件通知。</p>
      </div>
      <p class="login-footnote">安全登录能力将在认证步骤启用。</p>
    </section>

    <section class="login-form-panel" aria-labelledby="form-title">
      <form class="login-form" @submit.prevent>
        <div>
          <p class="eyebrow">WELCOME BACK</p>
          <h2 id="form-title">登录管理后台</h2>
          <p>请输入管理员凭据以继续。</p>
        </div>

        <label>
          <span>管理员账号</span>
          <input v-model="username" name="username" autocomplete="username" placeholder="请输入账号" />
        </label>

        <label>
          <span>密码</span>
          <input
            v-model="password"
            name="password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
        </label>

        <button type="submit" disabled>登录功能将在后续步骤启用</button>
      </form>
    </section>
  </main>
</template>
