<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" aria-label="主导航">
      <RouterLink class="brand" to="/" aria-label="DelTracking 首页">
        <span class="brand-mark" aria-hidden="true">D</span>
        <span>
          <strong>DelTracking</strong>
          <small>物流追踪管理</small>
        </span>
      </RouterLink>

      <nav class="nav-list">
        <RouterLink class="nav-link" to="/">
          <span class="nav-dot" aria-hidden="true"></span>
          概览
        </RouterLink>
      </nav>

      <p class="sidebar-note">管理功能将在后续步骤逐项启用。</p>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <div>
          <p class="eyebrow">DELIVERY OPERATIONS</p>
          <h1>管理中心</h1>
        </div>
        <span class="status-pill"><span aria-hidden="true"></span>骨架已就绪</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>
