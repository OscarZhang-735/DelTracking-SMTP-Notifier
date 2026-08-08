<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { apiGet, apiMutation, type Recipient, type TrackingList } from '@/api/client'
import AppDialog from '@/components/AppDialog.vue'
import { useToast } from '@/composables/toast'

const toast = useToast()
const recipients = ref<Recipient[]>([])
const trackings = ref<TrackingList | null>(null)
const loading = ref(true)
const dialogOpen = ref(false)
const editingId = ref<number | null>(null)
const busy = ref(false)
const form = reactive({ name: '', email: '', enabled: true, tracking_ids: [] as number[] })

async function load() {
  loading.value = true
  try {
    const result = await apiGet<{ items: Recipient[] }>('/recipients')
    recipients.value = result.items
    trackings.value = await apiGet<TrackingList>('/trackings?page_size=100')
  } catch (error) { toast.show(error instanceof Error ? error.message : '收件人加载失败', 'error') }
  finally { loading.value = false }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', email: '', enabled: true, tracking_ids: [] })
  dialogOpen.value = true
}

function openEdit(recipient: Recipient) {
  editingId.value = recipient.id
  Object.assign(form, { name: recipient.name, email: recipient.email, enabled: recipient.enabled, tracking_ids: trackings.value?.items.filter((item) => item.recipients.some((linked) => linked.id === recipient.id)).map((item) => item.id) ?? [] })
  dialogOpen.value = true
}

async function syncTrackingLinks(recipientId: number) {
  const all = trackings.value?.items ?? []
  await Promise.all(all.map((item) => {
    const existing = item.recipients.map((recipient) => recipient.id)
    const shouldLink = form.tracking_ids.includes(item.id)
    const isLinked = existing.includes(recipientId)
    if (shouldLink === isLinked) return Promise.resolve()
    return apiMutation(`/trackings/${item.id}`, 'PATCH', { recipient_ids: shouldLink ? [...existing, recipientId] : existing.filter((id) => id !== recipientId) })
  }))
}

async function save() {
  busy.value = true
  try {
    const recipient = editingId.value
      ? await apiMutation<Recipient>(`/recipients/${editingId.value}`, 'PATCH', { name: form.name, email: form.email, enabled: form.enabled })
      : await apiMutation<Recipient>('/recipients', 'POST', { name: form.name, email: form.email, enabled: form.enabled })
    await syncTrackingLinks(recipient.id)
    toast.show(editingId.value ? '收件人已更新' : '收件人已添加')
    dialogOpen.value = false
    await load()
  } catch (error) { toast.show(error instanceof Error ? error.message : '保存失败', 'error') }
  finally { busy.value = false }
}

async function remove(recipient: Recipient) {
  if (!window.confirm(`确定删除收件人 ${recipient.name}？关联运单不会被删除。`)) return
  try { await apiMutation(`/recipients/${recipient.id}`, 'DELETE'); toast.show('收件人已删除'); await load() }
  catch (error) { toast.show(error instanceof Error ? error.message : '删除失败', 'error') }
}

onMounted(load)
</script>

<template>
  <section aria-labelledby="recipients-title">
    <div class="section-heading"><div><p class="eyebrow">NOTIFICATIONS</p><h2 id="recipients-title">收件人管理</h2><p>每位收件人只会收到其关联运单的变化摘要。</p></div><button class="button button-primary" type="button" @click="openCreate">添加收件人</button></div><div class="table-wrap"><table><thead><tr><th>姓名</th><th>邮箱</th><th>关联运单</th><th>状态</th><th><span class="sr-only">操作</span></th></tr></thead><tbody><tr v-if="loading"><td colspan="5" class="table-message">正在加载…</td></tr><tr v-else-if="!recipients.length"><td colspan="5" class="table-message">尚未添加收件人</td></tr><tr v-for="recipient in recipients" v-else :key="recipient.id"><td><strong>{{ recipient.name }}</strong></td><td>{{ recipient.email }}</td><td>{{ recipient.tracking_count }} 条</td><td><span class="badge" :class="recipient.enabled ? 'badge-delivered' : 'badge-cancelled'">{{ recipient.enabled ? '启用' : '停用' }}</span></td><td><div class="row-actions"><button type="button" @click="openEdit(recipient)">编辑</button><button class="danger-link" type="button" @click="remove(recipient)">删除</button></div></td></tr></tbody></table></div>
    <AppDialog v-if="dialogOpen" :title="editingId ? '编辑收件人' : '添加收件人'" description="可同时选择需要接收通知的运单。" :busy="busy" @close="dialogOpen = false"><form class="form-grid" @submit.prevent="save"><label class="field"><span>姓名</span><input v-model="form.name" required maxlength="100" /></label><label class="field"><span>邮箱</span><input v-model="form.email" type="email" required autocomplete="email" /></label><fieldset class="field field-full"><legend>关联运单</legend><div class="check-grid"><label v-for="item in trackings?.items" :key="item.id"><input v-model="form.tracking_ids" type="checkbox" :value="item.id" />{{ item.tracking_number }}</label><span v-if="!trackings?.items.length" class="muted">尚无运单</span></div></fieldset><label class="switch-field field-full"><input v-model="form.enabled" type="checkbox" /><span>启用邮件通知</span></label><div class="dialog-actions field-full"><button class="button button-secondary" type="button" @click="dialogOpen = false">取消</button><button class="button button-primary" type="submit" :disabled="busy">{{ busy ? '保存中…' : '保存' }}</button></div></form></AppDialog>
  </section>
</template>
