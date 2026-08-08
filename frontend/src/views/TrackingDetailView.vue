<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { apiGet, apiMutation, type QueryResult, type Tracking } from '@/api/client'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToast } from '@/composables/toast'

const route = useRoute()
const toast = useToast()
const tracking = ref<Tracking | null>(null)
const loading = ref(true)
const querying = ref(false)

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '—'
}

async function load() {
  loading.value = true
  try { tracking.value = await apiGet<Tracking>(`/trackings/${route.params.id}`) }
  catch (error) { toast.show(error instanceof Error ? error.message : '详情加载失败', 'error') }
  finally { loading.value = false }
}

async function query() {
  querying.value = true
  try {
    const result = await apiMutation<QueryResult>(`/trackings/${route.params.id}/query`, 'POST')
    toast.show(`查询完成：新增变化 ${result.changed_count} 条`)
    await load()
  } catch (error) { toast.show(error instanceof Error ? error.message : '查询失败', 'error') }
  finally { querying.value = false }
}

onMounted(load)
</script>

<template>
  <section aria-labelledby="detail-title">
    <div class="section-heading"><div><RouterLink class="back-link" to="/trackings">← 返回运单列表</RouterLink><h2 id="detail-title">{{ tracking?.tracking_number || '运单详情' }}</h2><p v-if="tracking"><StatusBadge :status="tracking.shipment_status" :label="tracking.localized_status" /></p></div><button class="button button-primary" type="button" :disabled="querying || !tracking" @click="query">{{ querying ? '查询中…' : '立即查询' }}</button></div>
    <div v-if="loading" class="loading-panel">正在加载详情…</div>
    <template v-else-if="tracking">
      <div class="detail-grid">
        <article class="panel"><div class="panel-header"><div><h3>运输信息</h3><p>接口返回的包裹元数据</p></div></div><dl class="details-list two-column"><div><dt>系统单号</dt><dd>{{ tracking.shipment_id || '—' }}</dd></div><div><dt>客户单号</dt><dd>{{ tracking.client_reference || '—' }}</dd></div><div><dt>承运商</dt><dd>{{ tracking.outer_carrier_code || '—' }}</dd></div><div><dt>承运单号</dt><dd>{{ tracking.outer_carrier_tracking_number || '—' }}</dd></div><div><dt>国家 / 邮编</dt><dd>{{ tracking.country || '—' }} / {{ tracking.postcode || '—' }}</dd></div><div><dt>包裹件数</dt><dd>{{ tracking.parcel_count ?? '—' }}</dd></div><div><dt>最近成功</dt><dd>{{ formatDate(tracking.last_success_at) }}</dd></div><div><dt>关联收件人</dt><dd>{{ tracking.recipients.map((item) => item.name).join('、') || '未关联' }}</dd></div></dl><p v-if="tracking.last_error" class="alert alert-error">最近错误：{{ tracking.last_error }}</p></article>
        <article class="panel"><div class="panel-header"><div><h3>完整轨迹</h3><p>轨迹时间按供应商原文显示</p></div><span>{{ tracking.traces.length }} 条</span></div><div v-if="!tracking.traces.length" class="empty-state">首次查询后将在这里显示轨迹</div><ol v-else class="timeline"><li v-for="event in tracking.traces" :key="event.id"><span class="timeline-dot" aria-hidden="true"></span><time>{{ event.time_raw }}</time><p>{{ event.info }}</p></li></ol></article>
      </div>
    </template>
  </section>
</template>
