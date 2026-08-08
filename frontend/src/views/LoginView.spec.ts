import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LoginView from './LoginView.vue'

const replace = vi.fn()
const login = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace }),
}))
vi.mock('@/stores/auth', () => ({ useAuth: () => ({ login }) }))

describe('LoginView', () => {
  beforeEach(() => vi.clearAllMocks())

  it('submits credentials and navigates to the dashboard', async () => {
    login.mockResolvedValue(undefined)
    const wrapper = mount(LoginView)

    await wrapper.get('input[name="username"]').setValue('admin')
    await wrapper.get('input[name="password"]').setValue('secret-password')
    await wrapper.get('form').trigger('submit')

    expect(login).toHaveBeenCalledWith('admin', 'secret-password')
    expect(replace).toHaveBeenCalledWith('/')
  })

  it('announces authentication errors', async () => {
    login.mockRejectedValue(new Error('账号或密码错误'))
    const wrapper = mount(LoginView)
    await wrapper.get('input[name="username"]').setValue('admin')
    await wrapper.get('input[name="password"]').setValue('wrong')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('[role="alert"]').text()).toContain('账号或密码错误')
  })
})
