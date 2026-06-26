import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface SystemUser {
  id: number
  username: string
  email: string
  role: string
}

interface AuthState {
  user: SystemUser | null
  accessToken: string | null
  refreshToken: string | null
  setUser: (user: SystemUser) => void
  setTokens: (access: string, refresh: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      setUser: (user) => set({ user }),

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),

      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null })
        window.location.href = '/login'
      },
    }),
    { name: 'kiro-auth' },
  ),
)
