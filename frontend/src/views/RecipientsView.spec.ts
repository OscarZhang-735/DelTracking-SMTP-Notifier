import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RecipientsView from './RecipientsView.vue'

const { apiGet, apiMutation } = vi.hoisted(() => ({ apiGet: vi.fn(), apiMutation: vi.fn() }))
vi.mock('@/api/client', () => ({ apiGet, apiMutation }))

describe('RecipientsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiGet.mockImplementation((path: string) => path === '/recipients'
      ? Promise.resolve({ items: [{ id: 1, name: 'Alice', email: 'alice@example.com', enabled: true, tracking_count: 1 }] })
      : Promise.resolve({ items: [{ id: 8, tracking_number: '1024658760', recipients: [{ id: 1 }] }], total: 1 }))
    apiMutation.mockResolvedValue(undefined)
  })

  it('shows recipient associations and confirms deletion', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mount(RecipientsView)
    await flushPromises()
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('1 条')
    await wrapper.get('.danger-link').trigger('click')
    await flushPromises()
    expect(confirm).toHaveBeenCalled()
    expect(apiMutation).toHaveBeenCalledWith('/recipients/1', 'DELETE')
    confirm.mockRestore()
  })
})
