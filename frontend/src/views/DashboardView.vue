<template>
  <section aria-labelledby="dashboard-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">OVERVIEW</p>
        <h2 id="dashboard-title">今日概览</h2>
      </div>
      <p>数据连接将在后续步骤完成。</p>
    </div>

    <div class="metric-grid" aria-label="运单指标占位">
      <article class="metric-card">
        <span>启用运单</span>
        <strong>—</strong>
        <small>等待数据服务</small>
      </article>
      <article class="metric-card">
        <span>运输中</span>
        <strong>—</strong>
        <small>等待数据服务</small>
      </article>
      <article class="metric-card">
        <span>今日更新</span>
        <strong>—</strong>
        <small>等待调度服务</small>
      </article>
    </div>

    <article class="empty-panel">
      <div class="empty-icon" aria-hidden="true">↗</div>
      <div>
        <h3>管理框架已建立</h3>
        <p>数据库、查询任务和通知能力会在后续步骤接入。</p>
      </div>
    </article>
  </section>
</template>
