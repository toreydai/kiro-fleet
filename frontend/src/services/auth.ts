import api from '../lib/axios'

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{
      access_token?: string
      refresh_token?: string
      requires_mfa?: boolean
      pre_auth_token?: string
    }>('/auth/login', { username, password }),

  mfaVerify: (pre_auth_token: string, code: string) =>
    api.post<{
      access_token: string
      refresh_token: string
    }>('/auth/mfa-verify', { pre_auth_token, code }),

  refresh: (refresh_token: string) =>
    api.post<{
      access_token: string
      refresh_token: string
    }>('/auth/refresh', { refresh_token }),

  me: () =>
    api.get<{
      id: number
      username: string
      email: string
      role: string
    }>('/auth/me'),
}
