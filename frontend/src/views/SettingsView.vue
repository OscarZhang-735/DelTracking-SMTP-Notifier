<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { apiGet, apiMutation, setCsrfToken, type Admin, type ScheduleSettings, type SmtpSettings } from '@/api/client'
import { useToast } from '@/composables/toast'

const toast = useToast()
const loading = ref(true)
const scheduleBusy = ref(false)
const smtpBusy = ref(false)
const testing = ref(false)
const passwordBusy = ref(false)
const smtpConfigured = ref(false)
const schedule = reactive({ enabled: true, interval_minutes: 30, timezone: 'Asia/Shanghai' })
const smtp = reactive({ host: '', port: 587, security: 'starttls' as 'ssl' | 'starttls' | 'none', username: '', password: '', sender_name: 'DelTracking', sender_email: '' })
const testRecipient = ref('')
const password = reactive({ current_password: '', new_password: '', confirm_password: '' })

async function load() {
  loading.value = true
  try {
    const [scheduleValue, smtpValue] = await Promise.all([
      apiGet<ScheduleSettings>('/settings/schedule'),
      apiGet<SmtpSettings>('/settings/smtp'),
    ])
    Object.assign(schedule, scheduleValue)
    Object.assign(smtp, {
      host: smtpValue.host ?? '', port: smtpValue.port ?? 587,
      security: smtpValue.security ?? 'starttls', username: smtpValue.username ?? '',
      password: '', sender_name: smtpValue.sender_name ?? 'DelTracking', sender_email: smtpValue.sender_email ?? '',
    })
    smtpConfigured.value = smtpValue.password_configured
  } catch (error) { toast.show(error instanceof Error ? error.message : '设置加载失败', 'error') }
  finally { loading.value = false }
}

async function saveSchedule() {
  scheduleBusy.value = true
  try { await apiMutation('/settings/schedule', 'PUT', schedule); toast.show('调度设置已保存') }
  catch (error) { toast.show(error instanceof Error ? error.message : '保存失败', 'error') }
  finally { scheduleBusy.value = false }
}

async function saveSmtp() {
  smtpBusy.value = true
  try {
    const payload: Record<string, unknown> = { ...smtp, username: smtp.username || null }
    if (!smtp.password) delete payload.password
    const result = await apiMutation<SmtpSettings>('/settings/smtp', 'PUT', payload)
    smtpConfigured.value = result.password_configured
    smtp.password = ''
    toast.show('SMTP 设置已保存')
  } catch (error) { toast.show(error instanceof Error ? error.message : '保存失败', 'error') }
  finally { smtpBusy.value = false }
}

async function sendTest() {
  testing.value = true
  try { await apiMutation('/settings/smtp/test', 'POST', { recipient_email: testRecipient.value }); toast.show('测试邮件已发送') }
  catch (error) { toast.show(error instanceof Error ? error.message : '测试邮件发送失败', 'error') }
  finally { testing.value = false }
}

async function changePassword() {
  if (password.new_password !== password.confirm_password) { toast.show('两次输入的新密码不一致', 'error'); return }
  passwordBusy.value = true
  try {
    const result = await apiMutation<Admin>('/auth/password', 'PUT', { current_password: password.current_password, new_password: password.new_password })
    setCsrfToken(result.csrf_token)
    Object.assign(password, { current_password: '', new_password: '', confirm_password: '' })
    toast.show('管理员密码已修改，其他会话已失效')
  } catch (error) { toast.show(error instanceof Error ? error.message : '密码修改失败', 'error') }
  finally { passwordBusy.value = false }
}

onMounted(load)
</script>

<template>
  <section aria-labelledby="settings-title">
    <div class="section-heading"><div><p class="eyebrow">CONFIGURATION</p><h2 id="settings-title">系统设置</h2><p>调整查询调度、邮件服务器和管理员凭据。</p></div></div><div v-if="loading" class="loading-panel">正在加载设置…</div><div v-else class="settings-grid">
      <form class="panel form-grid" @submit.prevent="saveSchedule"><div class="panel-header field-full"><div><h3>自动调度</h3><p>查询任务不会与手动任务重叠。</p></div><span class="badge" :class="schedule.enabled ? 'badge-delivered' : 'badge-cancelled'">{{ schedule.enabled ? '运行中' : '已暂停' }}</span></div><label class="field"><span>查询间隔（分钟）</span><input v-model.number="schedule.interval_minutes" type="number" min="5" max="1440" required /></label><label class="field"><span>时区</span><input v-model="schedule.timezone" required /></label><label class="switch-field field-full"><input v-model="schedule.enabled" type="checkbox" /><span>启用自动查询</span></label><div class="dialog-actions field-full"><button class="button button-primary" type="submit" :disabled="scheduleBusy">{{ scheduleBusy ? '保存中…' : '保存调度设置' }}</button></div></form>
      <form class="panel form-grid" @submit.prevent="saveSmtp"><div class="panel-header field-full"><div><h3>SMTP 邮件</h3><p>密码状态：{{ smtpConfigured ? '已配置' : '未配置' }}，不会显示明文。</p></div></div><label class="field"><span>服务器</span><input v-model="smtp.host" required placeholder="smtp.example.com" /></label><label class="field"><span>端口</span><input v-model.number="smtp.port" type="number" min="1" max="65535" required /></label><label class="field"><span>加密方式</span><select v-model="smtp.security"><option value="starttls">STARTTLS</option><option value="ssl">SSL/TLS</option><option value="none">无加密</option></select></label><label class="field"><span>用户名</span><input v-model="smtp.username" autocomplete="username" /></label><label class="field"><span>发件人名称</span><input v-model="smtp.sender_name" required /></label><label class="field"><span>发件邮箱</span><input v-model="smtp.sender_email" type="email" required /></label><label class="field field-full"><span>SMTP 密码 <small>留空则保持现有密码</small></span><input v-model="smtp.password" type="password" autocomplete="new-password" :placeholder="smtpConfigured ? '已配置' : '请输入密码'" /></label><div class="dialog-actions field-full"><button class="button button-primary" type="submit" :disabled="smtpBusy">{{ smtpBusy ? '保存中…' : '保存 SMTP 设置' }}</button></div></form>
      <form class="panel form-grid" @submit.prevent="sendTest"><div class="panel-header field-full"><div><h3>发送测试邮件</h3><p>使用当前已保存的 SMTP 设置。</p></div></div><label class="field field-full"><span>收件邮箱</span><input v-model="testRecipient" type="email" required placeholder="recipient@example.com" /></label><div class="dialog-actions field-full"><button class="button button-secondary" type="submit" :disabled="testing">{{ testing ? '发送中…' : '发送测试邮件' }}</button></div></form>
      <form class="panel form-grid" @submit.prevent="changePassword"><div class="panel-header field-full"><div><h3>修改管理员密码</h3><p>修改后其他已登录会话将立即失效。</p></div></div><label class="field field-full"><span>当前密码</span><input v-model="password.current_password" type="password" autocomplete="current-password" required /></label><label class="field"><span>新密码</span><input v-model="password.new_password" type="password" minlength="12" autocomplete="new-password" required /></label><label class="field"><span>确认新密码</span><input v-model="password.confirm_password" type="password" minlength="12" autocomplete="new-password" required /></label><div class="dialog-actions field-full"><button class="button button-secondary" type="submit" :disabled="passwordBusy">{{ passwordBusy ? '修改中…' : '修改密码' }}</button></div></form>
    </div>
  </section>
</template>
