import api from '../lib/axios'
import type { Account } from '../stores/appStore'

type CreatePayload = Omit<Account, 'id' | 'created_at' | 'updated_at'>

export const accountsApi = {
  list: () => api.get<{ items: Account[] } | Account[]>('/accounts'),

  create: (data: Partial<CreatePayload>) => api.post<Account>('/accounts', data),

  get: (id: number) => api.get<Account>(`/accounts/${id}`),

  update: (id: number, data: Partial<CreatePayload>) =>
    api.patch<Account>(`/accounts/${id}`, data),

  delete: (id: number) => api.delete(`/accounts/${id}`),

  verify: (id: number) => api.post(`/accounts/${id}/verify`),

  sync: (id: number) => api.post(`/accounts/${id}/sync`),

  exportJson: (id: number) =>
    api.post(`/accounts/${id}/export`, {}, { responseType: 'blob' }),

  stats: (id: number) =>
    api.get<{
      total_users: number
      active_subscriptions: number
      total_credits: number
      recent_logs: number
    }>(`/accounts/${id}/stats`),
}
