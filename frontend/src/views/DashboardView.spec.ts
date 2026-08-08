import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DashboardView from './DashboardView.vue'

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }))
vi.mock('@/api/client', () => ({ apiGet }))

describe('DashboardView', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders shipment metrics and scheduling state', async () => {
    apiGet.mockImplementation((path: string) => {
      if (path.includes('enabled=true')) return Promise.resolve({ items: [], total: 3 })
      if (path.includes('in_transit')) return Promise.resolve({ items: [], total: 1 })
      if (path.includes('delivered')) return Promise.resolve({ items: [], total: 1 })
      if (path.startsWith('/runs')) return Promise.resolve({ items: [{ id: 1, trigger: 'manual', status: 'completed', started_at: '2026-08-08T10:00:00Z', failure_count: 1 }] })
      return Promise.resolve({ enabled: true, interval_minutes: 30, timezone: 'Asia/Shanghai' })
    })
    const wrapper = mount(DashboardView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
    await flushPromises()

    expect(wrapper.text()).toContain('启用运单3')
    expect(wrapper.text()).toContain('运输中1')
    expect(wrapper.text()).toContain('已签收1')
    expect(wrapper.text()).toContain('失败数1')
    expect(wrapper.text()).toContain('运行中')
  })

  it('shows a recoverable loading error', async () => {
    apiGet.mockRejectedValue(new Error('服务暂不可用'))
    const wrapper = mount(DashboardView, { global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('服务暂不可用')
    expect(wrapper.get('[role="alert"] button').text()).toBe('重试')
  })
})
