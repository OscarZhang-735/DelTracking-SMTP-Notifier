import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SettingsView from './SettingsView.vue'

const { apiGet, apiMutation, setCsrfToken } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiMutation: vi.fn(),
  setCsrfToken: vi.fn(),
}))
vi.mock('@/api/client', () => ({ apiGet, apiMutation, setCsrfToken }))

describe('SettingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiGet.mockImplementation((path: string) => path.includes('schedule')
      ? Promise.resolve({ enabled: true, interval_minutes: 30, timezone: 'Asia/Shanghai' })
      : Promise.resolve({ host: 'smtp.example.com', port: 587, security: 'starttls', username: 'mailer', sender_name: 'DelTracking', sender_email: 'mailer@example.com', password_configured: true }))
    apiMutation.mockResolvedValue({})
  })

  it('shows only the SMTP password configuration state', async () => {
    const wrapper = mount(SettingsView)
    await flushPromises()
    expect(wrapper.text()).toContain('密码状态：已配置')
    expect(wrapper.get('input[autocomplete="new-password"]').attributes('placeholder')).toBe('已配置')
    expect(wrapper.text()).not.toContain('smtp-secret')
  })

  it('validates password confirmation before submitting', async () => {
    const wrapper = mount(SettingsView)
    await flushPromises()
    const passwordForm = wrapper.findAll('form')[3]
    const fields = passwordForm.findAll('input')
    await fields[0]!.setValue('current-password')
    await fields[1]!.setValue('new-password-123')
    await fields[2]!.setValue('different-password')
    await passwordForm.trigger('submit')
    expect(apiMutation).not.toHaveBeenCalledWith('/auth/password', 'PUT', expect.anything())
  })
})
