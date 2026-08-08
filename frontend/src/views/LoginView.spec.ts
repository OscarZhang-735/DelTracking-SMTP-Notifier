import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LoginView from './LoginView.vue'

describe('LoginView', () => {
  it('renders an accessible login scaffold', () => {
    const wrapper = mount(LoginView)

    expect(wrapper.get('h1').text()).toContain('物流变化')
    expect(wrapper.get('input[name="username"]').attributes('autocomplete')).toBe('username')
    expect(wrapper.get('input[name="password"]').attributes('type')).toBe('password')
    expect(wrapper.get('button').attributes()).toHaveProperty('disabled')
  })
})
