import { create } from 'zustand'

export interface Account {
  id: number
  name: string
  description?: string | null
  access_key_id?: string
  secret_access_key?: string
  sso_region: string
  kiro_region: string
  instance_arn: string
  identity_store_id: string
  status: string
  last_verified?: string | null
  sync_interval_minutes: number
  last_synced?: string | null
  is_default: boolean
  kiro_login_url?: string | null
  created_at: string
  updated_at: string
}

interface AppState {
  loading: boolean
  accounts: Account[]
  selectedAccountId: number | null
  setLoading: (v: boolean) => void
  setAccounts: (accounts: Account[]) => void
  setSelectedAccount: (id: number | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  loading: false,
  accounts: [],
  selectedAccountId: null,

  setLoading: (v) => set({ loading: v }),
  setAccounts: (accounts) => set({ accounts }),
  setSelectedAccount: (id) => set({ selectedAccountId: id }),
}))
