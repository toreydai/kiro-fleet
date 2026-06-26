import api from '../lib/axios'

export interface CreditRecord {
  id: string
  user_id?: string
  username?: string
  email?: string
  used: number
  remaining: number
  total: number
  period?: string
  updated_at?: string
}

export interface CreditSummary {
  total_used: number
  total_remaining: number
  user_count: number
}

export const creditsApi = {
  list: (accountId: number) =>
    api.get<{ items: CreditRecord[]; summary?: CreditSummary } | CreditRecord[]>(
      `/accounts/${accountId}/credits`,
    ),

  sync: (accountId: number) => api.post(`/accounts/${accountId}/credits/sync`),
}
