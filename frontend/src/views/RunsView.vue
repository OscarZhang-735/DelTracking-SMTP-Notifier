<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { apiGet, apiMutation, type RunDetail, type RunList, type RunSummary } from '@/api/client'
import { useToast } from '@/composables/toast'

const toast = useToast()
const data = ref<RunList>({ items: [], total: 0, page: 1, page_size: 20 })
const selected = ref<RunDetail | null>(null)
const loading = ref(true)
const detailLoading = ref(false)

function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString('zh-CN') : '—' }
function triggerLabel(value: string) { return value === 'scheduled' ? '自动调度' : value === 'manual' ? '手动运行' : value }

async function load(page = 1) {
  loading.value = true
  try { data.value = await apiGet<RunList>(`/runs?page=${page}&page_size=20`) }
  catch (error) { toast.show(error instanceof Error ? error.message : '运行记录加载失败', 'error') }
  finally { loading.value = false }
}

async function showDetail(run: RunSummary) {
  detailLoading.value = true
  try { selected.value = await apiGet<RunDetail>(`/runs/${run.id}`) }
  catch (error) { toast.show(error instanceof Error ? error.message : '运行详情加载失败', 'error') }
  finally { detailLoading.value = false }
}

async function retry(notificationId: number) {
  if (!window.confirm('立即重试发送这封邮件？')) return
  try {
    const result = await apiMutation<{ sent: number; failed: number }>(`/notifications/${notificationId}/retry`, 'POST')
    toast.show(result.sent ? '邮件已成功发送' : '邮件重试仍然失败', result.sent ? 'success' : 'error')
    if (selected.value) selected.value = await apiGet<RunDetail>(`/runs/${selected.value.id}`)
  } catch (error) { toast.show(error instanceof Error ? error.message : '重试失败', 'error') }
}

onMounted(() => load())
</script>

<template>
  <section aria-labelledby="runs-title">
    <div class="section-heading"><div><p class="eyebrow">AUDIT LOG</p><h2 id="runs-title">运行记录</h2><p>查看每次任务的结果、逐单错误和邮件发送状态。</p></div></div><div class="runs-layout">
      <div class="table-wrap"><table><thead><tr><th>运行</th><th>状态</th><th>结果</th><th>开始时间</th></tr></thead><tbody><tr v-if="loading"><td colspan="4" class="table-message">正在加载…</td></tr><tr v-else-if="!data.items.length"><td colspan="4" class="table-message">尚无运行记录</td></tr><tr v-for="run in data.items" v-else :key="run.id" class="clickable-row" tabindex="0" @click="showDetail(run)" @keydown.enter="showDetail(run)"><td><strong>#{{ run.id }}</strong><small>{{ triggerLabel(run.trigger) }}</small></td><td><span class="badge" :class="`badge-${run.status}`">{{ run.status }}</span></td><td>成功 {{ run.success_count }} / 失败 {{ run.failure_count }}<small>变化 {{ run.changed_count }} 条</small></td><td>{{ formatDate(run.started_at) }}</td></tr></tbody></table><div class="pagination"><span>共 {{ data.total }} 次</span><div><button type="button" :disabled="data.page <= 1" @click="load(data.page - 1)">上一页</button><span>第 {{ data.page }} 页</span><button type="button" :disabled="data.page * data.page_size >= data.total" @click="load(data.page + 1)">下一页</button></div></div></div>
      <aside class="panel run-detail" aria-label="运行详情"><div v-if="detailLoading" class="loading-panel">正在加载详情…</div><div v-else-if="!selected" class="empty-state">选择一条运行记录查看详情</div><template v-else><div class="panel-header"><div><h3>运行 #{{ selected.id }}</h3><p>{{ formatDate(selected.started_at) }} · {{ triggerLabel(selected.trigger) }}</p></div><span class="badge" :class="`badge-${selected.status}`">{{ selected.status }}</span></div><p v-if="selected.error_summary" class="alert alert-error">{{ selected.error_summary }}</p><h4>逐单结果</h4><ul class="audit-list"><li v-for="item in selected.items" :key="item.id"><span><strong>{{ item.tracking_number }}</strong><small>{{ item.error || `新增轨迹 ${item.added_event_count} 条` }}</small></span><span class="badge" :class="`badge-${item.status}`">{{ item.status }}</span></li></ul><h4>邮件通知</h4><div v-if="!selected.notifications.length" class="empty-state compact">本次运行没有邮件通知</div><ul v-else class="audit-list"><li v-for="notification in selected.notifications" :key="notification.id"><span><strong>{{ notification.recipient_email }}</strong><small>{{ notification.last_error || notification.subject }}</small></span><span><span class="badge" :class="`badge-${notification.status}`">{{ notification.status }}</span><button v-if="notification.status !== 'sent'" class="text-button" type="button" @click="retry(notification.id)">重试</button></span></li></ul></template></aside>
    </div>
  </section>
</template>
