import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import TrackingDetailView from './TrackingDetailView.vue'

const { apiGet, apiMutation } = vi.hoisted(() => ({ apiGet: vi.fn(), apiMutation: vi.fn() }))
vi.mock('@/api/client', () => ({ apiGet, apiMutation }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

describe('TrackingDetailView', () => {
  it('renders supplier time text without timezone conversion', async () => {
    apiGet.mockResolvedValue({
      id: 1, tracking_number: '1024658760', shipment_status: 'in_transit', localized_status: '运输中',
      shipment_id: 'SHIP-1', client_reference: 'CLIENT-1', outer_carrier_code: 'CA',
      outer_carrier_tracking_number: 'OUTER-1', country: 'CA', postcode: 'A1A1A1', parcel_count: 1,
      last_success_at: '2026-08-08T10:00:00Z', last_error: null, recipients: [],
      traces: [{ id: 1, time_raw: '2026-08-08 17:42:01', info: 'Shipment departed' }],
    })
    apiMutation.mockResolvedValue({ changed_count: 0 })
    const wrapper = mount(TrackingDetailView)
    await flushPromises()
    expect(wrapper.text()).toContain('2026-08-08 17:42:01')
    expect(wrapper.text()).toContain('Shipment departed')
  })
})
