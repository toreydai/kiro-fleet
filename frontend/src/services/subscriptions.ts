import api from '../lib/axios'

export interface Subscription {
  id: string
  user_id: string
  username?: string
  email?: string
  plan: string
  status: string
  created_at: string
  canceled_at?: string
}

export const subscriptionsApi = {
  list: (accountId: number) =>
    api.get<{ items: Subscription[] } | Subscription[]>(
      `/accounts/${accountId}/subscriptions`,
    ),

  create: (accountId: number, data: Record<string, unknown>) =>
    api.post<Subscription>(`/accounts/${accountId}/subscriptions`, data),

  changePlan: (accountId: number, sid: string, data: { plan: string }) =>
    api.put<Subscription>(
      `/accounts/${accountId}/subscriptions/${sid}/change-plan`,
      data,
    ),

  cancel: (accountId: number, sid: string) =>
    api.delete(`/accounts/${accountId}/subscriptions/${sid}`),

  listCanceled: (accountId: number) =>
    api.get<{ items: Subscription[] } | Subscription[]>(
      `/accounts/${accountId}/subscriptions/canceled`,
    ),

  listAll: () =>
    api.get<{ items: Subscription[] } | Subscription[]>('/subscriptions'),

  changePlanBulk: (data: { subscription_ids: string[]; new_plan: string }) =>
    api.post('/subscriptions/change-plan-bulk', data),
}
