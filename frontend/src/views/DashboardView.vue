<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { apiGet, type RunList, type ScheduleSettings, type TrackingList } from '@/api/client'

const runs = ref<RunList | null>(null)
const schedule = ref<ScheduleSettings | null>(null)
const totals = reactive({ enabled: 0, inTransit: 0, delivered: 0 })
const loading = ref(true)
const errorMessage = ref('')

const metrics = computed(() => {
  return [
    { label: '启用运单', value: totals.enabled, hint: '参与自动查询的运单' },
    { label: '运输中', value: totals.inTransit, hint: '正在运输途中的包裹' },
    { label: '已签收', value: totals.delivered, hint: '已完成配送' },
    { label: '失败数', value: runs.value?.items[0]?.failure_count ?? 0, hint: '最近一次运行的失败数' },
  ]
})

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '暂无'
}

const nextRun = computed(() => {
  if (!schedule.value?.enabled) return '已暂停'
  const last = runs.value?.items[0]?.started_at
  if (!last) return '等待首次运行'
  return formatDate(new Date(new Date(last).getTime() + schedule.value.interval_minutes * 60000).toISOString())
})

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [enabled, inTransit, delivered, runList, scheduleValue] = await Promise.all([
      apiGet<TrackingList>('/trackings?enabled=true&page_size=1'),
      apiGet<TrackingList>('/trackings?shipment_status=in_transit&page_size=1'),
      apiGet<TrackingList>('/trackings?shipment_status=delivered&page_size=1'),
      apiGet<RunList>('/runs?page_size=5'),
      apiGet<ScheduleSettings>('/settings/schedule'),
    ])
    totals.enabled = enabled.total
    totals.inTransit = inTransit.total
    totals.delivered = delivered.total
    runs.value = runList
    schedule.value = scheduleValue
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '仪表盘加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section aria-labelledby="dashboard-title">
    <div class="section-heading"><div><p class="eyebrow">OVERVIEW</p><h2 id="dashboard-title">运行概览</h2></div><RouterLink class="button button-primary" to="/trackings">管理运单</RouterLink></div>
    <p v-if="errorMessage" class="alert alert-error" role="alert">{{ errorMessage }} <button type="button" @click="load">重试</button></p>
    <div v-if="loading" class="loading-panel" role="status">正在加载概览…</div>
    <template v-else>
      <div class="metric-grid metric-grid-four">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.hint }}</small></article>
      </div>
      <div class="dashboard-grid">
        <article class="panel"><div class="panel-header"><div><h3>调度状态</h3><p>自动查询任务的运行节奏</p></div><span class="badge" :class="schedule?.enabled ? 'badge-delivered' : 'badge-cancelled'">{{ schedule?.enabled ? '运行中' : '已暂停' }}</span></div><dl class="details-list"><div><dt>查询间隔</dt><dd>{{ schedule?.interval_minutes }} 分钟</dd></div><div><dt>上次运行</dt><dd>{{ formatDate(runs?.items[0]?.started_at) }}</dd></div><div><dt>预计下次</dt><dd>{{ nextRun }}</dd></div></dl><RouterLink class="text-link" to="/settings">调整调度设置 →</RouterLink></article>
        <article class="panel"><div class="panel-header"><div><h3>最近运行</h3><p>最新五次查询任务</p></div><RouterLink class="text-link" to="/runs">查看全部</RouterLink></div><div v-if="!runs?.items.length" class="empty-state compact">尚无运行记录</div><ul v-else class="run-list"><li v-for="run in runs.items" :key="run.id"><span><strong>#{{ run.id }} · {{ run.trigger === 'manual' ? '手动' : '自动' }}</strong><small>{{ formatDate(run.started_at) }}</small></span><span class="badge" :class="`badge-${run.status}`">{{ run.status }}</span></li></ul></article>
      </div>
    </template>
  </section>
</template>
