import api from '../lib/axios'

export interface IcUser {
  id: string
  username: string
  email: string
  display_name?: string
  status?: string
  created_at?: string
}

export const usersApi = {
  list: (accountId: number, params?: Record<string, unknown>) =>
    api.get<{ items: IcUser[] } | IcUser[]>(`/accounts/${accountId}/users`, { params }),

  create: (accountId: number, data: Record<string, unknown>) =>
    api.post<IcUser>(`/accounts/${accountId}/users`, data),

  update: (accountId: number, uid: string, data: Record<string, unknown>) =>
    api.put<IcUser>(`/accounts/${accountId}/users/${uid}`, data),

  delete: (accountId: number, uid: string) =>
    api.delete(`/accounts/${accountId}/users/${uid}`),

  resetPassword: (accountId: number, uid: string) =>
    api.post<{ temporary_password?: string; new_password?: string }>(
      `/accounts/${accountId}/users/${uid}/reset-password`,
    ),

  verifyEmail: (accountId: number, uid: string) =>
    api.post(`/accounts/${accountId}/users/${uid}/verify-email`),

  listGroups: (accountId: number) =>
    api.get<{ items: { id: string; name: string }[] } | { id: string; name: string }[]>(
      `/accounts/${accountId}/groups`,
    ),

  addGroup: (accountId: number, uid: string, data: { group_id: string }) =>
    api.post(`/accounts/${accountId}/users/${uid}/add-group`, data),
}
