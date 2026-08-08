import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import RunsView from './RunsView.vue'

const { apiGet, apiMutation } = vi.hoisted(() => ({ apiGet: vi.fn(), apiMutation: vi.fn() }))
vi.mock('@/api/client', () => ({ apiGet, apiMutation }))

const run = { id: 3, trigger: 'manual', status: 'partial', started_at: '2026-08-08T10:00:00Z', finished_at: null, total_count: 1, success_count: 0, failure_count: 1, changed_count: 0, error_summary: '1 tracking query failed' }

describe('RunsView', () => {
  it('shows per-item errors and retries failed notifications', async () => {
    apiGet.mockImplementation((path: string) => path === '/runs?page=1&page_size=20'
      ? Promise.resolve({ items: [run], total: 1, page: 1, page_size: 20 })
      : Promise.resolve({ ...run, items: [{ id: 1, tracking_number: '1024658760', status: 'failed', error: 'Provider timeout', changed: false, added_event_count: 0 }], notifications: [{ id: 9, recipient_email: 'alice@example.com', subject: 'Update', status: 'failed', attempt_count: 6, last_error: 'SMTP unavailable' }] }))
    apiMutation.mockResolvedValue({ sent: 1, failed: 0 })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mount(RunsView)
    await flushPromises()
    await wrapper.get('.clickable-row').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Provider timeout')
    expect(wrapper.text()).toContain('SMTP unavailable')
    await wrapper.get('.text-button').trigger('click')
    await flushPromises()
    expect(apiMutation).toHaveBeenCalledWith('/notifications/9/retry', 'POST')
  })
})
