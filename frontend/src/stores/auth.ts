import { reactive } from 'vue'

import { ApiError, apiGet, login as apiLogin, logout as apiLogout, type Admin } from '@/api/client'

interface AuthState {
  admin: Admin | null
  initialized: boolean
}

const state = reactive<AuthState>({ admin: null, initialized: false })

export function useAuth() {
  async function initialize() {
    if (state.initialized) return
    try {
      state.admin = await apiGet<Admin>('/auth/me')
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error
      state.admin = null
    } finally {
      state.initialized = true
    }
  }

  async function login(username: string, password: string) {
    state.admin = await apiLogin(username, password)
    state.initialized = true
  }

  async function logout() {
    await apiLogout()
    state.admin = null
  }

  return { state, initialize, login, logout }
}
