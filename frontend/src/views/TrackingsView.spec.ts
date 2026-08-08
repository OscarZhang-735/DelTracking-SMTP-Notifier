import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TrackingsView from './TrackingsView.vue'

const { apiGet, apiMutation } = vi.hoisted(() => ({ apiGet: vi.fn(), apiMutation: vi.fn() }))
vi.mock('@/api/client', () => ({ apiGet, apiMutation }))

describe('TrackingsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiGet.mockImplementation((path: string) => path === '/recipients'
      ? Promise.resolve({ items: [{ id: 2, name: 'Alice', email: 'alice@example.com', enabled: true, tracking_count: 0 }] })
      : Promise.resolve({ items: [], total: 0, page: 1, page_size: 20 }))
    apiMutation.mockResolvedValue({ id: 1 })
  })

  it('adds a tracking item with selected recipients', async () => {
    const wrapper = mount(TrackingsView, { global: { stubs: { RouterLink: true } } })
    await flushPromises()
    await wrapper.get('.section-heading .button-primary').trigger('click')
    await wrapper.get('input[required]').setValue('1024658760')
    await wrapper.get('input[type="checkbox"][value="2"]').setValue(true)
    await wrapper.get('.dialog-card form').trigger('submit')
    await flushPromises()

    expect(apiMutation).toHaveBeenCalledWith('/trackings', 'POST', expect.objectContaining({
      tracking_number: '1024658760', recipient_ids: [2], enabled: true,
    }))
  })

  it('renders an empty state without losing search controls', async () => {
    const wrapper = mount(TrackingsView, { global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(wrapper.text()).toContain('没有符合条件的运单')
    expect(wrapper.get('input[type="search"]').attributes('placeholder')).toContain('搜索运单号')
  })
})
