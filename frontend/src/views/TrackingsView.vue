<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { apiGet, apiMutation, type QueryResult, type Recipient, type Tracking, type TrackingList } from '@/api/client'
import AppDialog from '@/components/AppDialog.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToast } from '@/composables/toast'

const toast = useToast()
const data = ref<TrackingList>({ items: [], total: 0, page: 1, page_size: 20 })
const recipients = ref<Recipient[]>([])
const search = ref('')
const statusFilter = ref('')
const loading = ref(false)
const busy = ref(false)
const dialogOpen = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ tracking_number: '', notes: '', enabled: true, recipient_ids: [] as number[] })
let searchTimer: number | undefined

async function load(page = data.value.page) {
  loading.value = true
  try {
    const params = new URLSearchParams({ page: String(page), page_size: '20' })
    if (search.value.trim()) params.set('search', search.value.trim())
    if (statusFilter.value) params.set('shipment_status', statusFilter.value)
    data.value = await apiGet<TrackingList>(`/trackings?${params}`)
  } catch (error) {
    toast.show(error instanceof Error ? error.message : '运单加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { tracking_number: '', notes: '', enabled: true, recipient_ids: [] })
  dialogOpen.value = true
}

function openEdit(item: Tracking) {
  editingId.value = item.id
  Object.assign(form, { tracking_number: item.tracking_number, notes: item.notes ?? '', enabled: item.enabled, recipient_ids: item.recipients.map((recipient) => recipient.id) })
  dialogOpen.value = true
}

async function save() {
  busy.value = true
  try {
    const payload = { ...form, notes: form.notes.trim() || null }
    if (editingId.value) await apiMutation(`/trackings/${editingId.value}`, 'PATCH', payload)
    else await apiMutation('/trackings', 'POST', payload)
    toast.show(editingId.value ? '运单已更新' : '运单已添加')
    dialogOpen.value = false
    await load(editingId.value ? data.value.page : 1)
  } catch (error) {
    toast.show(error instanceof Error ? error.message : '保存失败', 'error')
  } finally {
    busy.value = false
  }
}

async function remove(item: Tracking) {
  if (!window.confirm(`确定删除运单 ${item.tracking_number}？此操作不会删除收件人。`)) return
  try {
    await apiMutation(`/trackings/${item.id}`, 'DELETE')
    toast.show('运单已删除')
    await load()
  } catch (error) { toast.show(error instanceof Error ? error.message : '删除失败', 'error') }
}

async function toggle(item: Tracking) {
  try {
    await apiMutation(`/trackings/${item.id}`, 'PATCH', { enabled: !item.enabled })
    toast.show(item.enabled ? '已停用运单' : '已启用运单')
    await load()
  } catch (error) { toast.show(error instanceof Error ? error.message : '状态更新失败', 'error') }
}

async function query(item: Tracking) {
  try {
    const result = await apiMutation<QueryResult>(`/trackings/${item.id}/query`, 'POST')
    toast.show(`查询完成：成功 ${result.success_count}，失败 ${result.failure_count}`, result.failure_count ? 'error' : 'success')
    await load()
  } catch (error) { toast.show(error instanceof Error ? error.message : '查询失败', 'error') }
}

async function queryAll() {
  if (!window.confirm('立即查询全部启用运单？')) return
  try {
    const result = await apiMutation<QueryResult>('/trackings/query-all', 'POST')
    toast.show(`全部查询完成：成功 ${result.success_count}，失败 ${result.failure_count}`, result.failure_count ? 'error' : 'success')
    await load()
  } catch (error) { toast.show(error instanceof Error ? error.message : '查询失败', 'error') }
}

watch([search, statusFilter], () => { window.clearTimeout(searchTimer); searchTimer = window.setTimeout(() => load(1), 250) })
onMounted(async () => { await Promise.all([load(1), apiGet<{ items: Recipient[] }>('/recipients').then((value) => { recipients.value = value.items })]) })
</script>

<template>
  <section aria-labelledby="trackings-title">
    <div class="section-heading"><div><p class="eyebrow">SHIPMENTS</p><h2 id="trackings-title">运单管理</h2><p>搜索、关联收件人并立即刷新物流轨迹。</p></div><div class="button-row"><button class="button button-secondary" type="button" @click="queryAll">查询全部</button><button class="button button-primary" type="button" @click="openCreate">添加运单</button></div></div>
    <div class="toolbar"><label class="search-field"><span class="sr-only">搜索运单</span><input v-model="search" type="search" placeholder="搜索运单号、系统单号或客户单号" /></label><label><span class="sr-only">状态筛选</span><select v-model="statusFilter"><option value="">全部状态</option><option value="ready">已下单</option><option value="picked">已收货</option><option value="in_transit">运输中</option><option value="delivered">已签收</option><option value="returned">退件</option><option value="cancelled">已取消</option></select></label></div>
    <div class="table-wrap"><table><thead><tr><th>运单</th><th>状态</th><th>承运信息</th><th>最近查询</th><th><span class="sr-only">操作</span></th></tr></thead><tbody><tr v-if="loading"><td colspan="5" class="table-message">正在加载…</td></tr><tr v-else-if="!data.items.length"><td colspan="5" class="table-message">没有符合条件的运单</td></tr><tr v-for="item in data.items" v-else :key="item.id"><td><RouterLink class="record-link" :to="`/trackings/${item.id}`">{{ item.tracking_number }}</RouterLink><small>{{ item.notes || '无备注' }}</small></td><td><StatusBadge :status="item.shipment_status" :label="item.localized_status" /><small>{{ item.enabled ? '已启用' : '已停用' }}</small></td><td>{{ item.outer_carrier_code || '—' }}<small>{{ item.country || '国家未知' }} {{ item.postcode || '' }}</small></td><td>{{ item.last_checked_at ? new Date(item.last_checked_at).toLocaleString('zh-CN') : '尚未查询' }}<small v-if="item.last_error" class="error-text">{{ item.last_error }}</small></td><td><div class="row-actions"><button type="button" @click="query(item)">查询</button><button type="button" @click="toggle(item)">{{ item.enabled ? '停用' : '启用' }}</button><button type="button" @click="openEdit(item)">编辑</button><button class="danger-link" type="button" @click="remove(item)">删除</button></div></td></tr></tbody></table></div>
    <div class="pagination"><span>共 {{ data.total }} 条</span><div><button type="button" :disabled="data.page <= 1" @click="load(data.page - 1)">上一页</button><span>第 {{ data.page }} 页</span><button type="button" :disabled="data.page * data.page_size >= data.total" @click="load(data.page + 1)">下一页</button></div></div>
    <AppDialog v-if="dialogOpen" :title="editingId ? '编辑运单' : '添加运单'" description="系统会在首次成功查询时建立基线，不发送通知。" :busy="busy" @close="dialogOpen = false"><form class="form-grid" @submit.prevent="save"><label class="field field-full"><span>运单号</span><input v-model="form.tracking_number" required maxlength="100" /></label><label class="field field-full"><span>备注</span><textarea v-model="form.notes" maxlength="2000" rows="3"></textarea></label><fieldset class="field field-full"><legend>关联收件人</legend><div class="check-grid"><label v-for="recipient in recipients" :key="recipient.id"><input v-model="form.recipient_ids" type="checkbox" :value="recipient.id" />{{ recipient.name }} · {{ recipient.email }}</label><span v-if="!recipients.length" class="muted">请先添加收件人</span></div></fieldset><label class="switch-field field-full"><input v-model="form.enabled" type="checkbox" /><span>启用自动查询</span></label><div class="dialog-actions field-full"><button class="button button-secondary" type="button" :disabled="busy" @click="dialogOpen = false">取消</button><button class="button button-primary" type="submit" :disabled="busy">{{ busy ? '保存中…' : '保存' }}</button></div></form></AppDialog>
  </section>
</template>
