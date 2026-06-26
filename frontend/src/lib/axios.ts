import axios, { type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '../stores/authStore'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 请求拦截：注入 Bearer token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

// 响应拦截：401 自动续 token 并重试
let isRefreshing = false
let pendingQueue: Array<(token: string) => void> = []

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original: RetryConfig = error.config

    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }

    original._retry = true

    if (isRefreshing) {
      // 等待刷新完成后重试
      return new Promise((resolve) => {
        pendingQueue.push((token: string) => {
          original.headers.set('Authorization', `Bearer ${token}`)
          resolve(api(original))
        })
      })
    }

    isRefreshing = true
    try {
      const { refreshToken, setTokens, logout } = useAuthStore.getState()
      if (!refreshToken) {
        logout()
        return Promise.reject(error)
      }

      const res = await axios.post('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
      })
      const { access_token, refresh_token } = res.data
      setTokens(access_token, refresh_token)

      // 刷新成功：唤醒所有等待队列
      pendingQueue.forEach((cb) => cb(access_token))
      pendingQueue = []

      original.headers.set('Authorization', `Bearer ${access_token}`)
      return api(original)
    } catch {
      pendingQueue = []
      useAuthStore.getState().logout()
      return Promise.reject(error)
    } finally {
      isRefreshing = false
    }
  },
)

export default api
