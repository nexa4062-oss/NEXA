import { create } from 'zustand'
import api from '../services/api'

interface User {
  id: string
  employee_id: string
  username: string
  display_name: string
  email: string | null
  department: string | null
  designation: string | null
  role: string | null
  role_display: string | null
  permissions: string[]
  status: string
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  fetchUser: () => Promise<void>
  hasPermission: (perm: string) => boolean
}

/**
 * Root cause of the "user/organisation details disappear, then
 * sometimes come back" bug: login() called fetchUser() itself, AND the
 * isAuthenticated flip it caused separately triggered App.tsx's
 * `useEffect(() => { if (isAuthenticated) fetchUser() }, [isAuthenticated])`
 * - two concurrent /auth/me requests fired almost simultaneously (and
 * doubled again by React 18 StrictMode's double effect-invocation in
 * dev). Whichever request happened to *resolve* last won, regardless of
 * which was *issued* last - so a slow/transient failure on either call
 * could stomp already-correct data with null a moment after it was
 * shown. The catch block also nulled `user` on ANY error, including
 * ordinary network blips or a briefly slow API, not just a truly
 * invalid session.
 *
 * Fixed by: (1) sharing one in-flight request across overlapping
 * fetchUser() calls instead of firing duplicates, (2) a monotonically
 * increasing request id so a late/stale response can never overwrite
 * state set by a newer one, and (3) only clearing `user` on a real
 * auth failure (401/403) - any other error (network, timeout, 5xx)
 * keeps the last-known-good user data on screen and just stops the
 * loading spinner, per "never replace valid user data with null/
 * undefined/default state; use proper loading states".
 */
let inFlightFetch: Promise<void> | null = null
let latestRequestId = 0

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: false,

  login: async (username: string, password: string) => {
    set({ isLoading: true })
    try {
      const res = await api.post('/auth/login', { username, password })
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('refresh_token', res.data.refresh_token)
      set({ isAuthenticated: true })
      await get().fetchUser()
    } finally {
      set({ isLoading: false })
    }
  },

  logout: async () => {
    try {
      await api.post('/auth/logout')
    } catch {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    inFlightFetch = null
    set({ user: null, isAuthenticated: false })
  },

  fetchUser: async () => {
    // Share one in-flight request instead of firing a duplicate - this
    // is what actually happens when login() and App's effect both call
    // fetchUser() within the same tick.
    if (inFlightFetch) return inFlightFetch

    const requestId = ++latestRequestId
    set({ isLoading: true })

    const run = (async () => {
      try {
        const res = await api.get('/auth/me')
        // A newer fetchUser() call already resolved (or started) after
        // this one - don't let this stale response overwrite it.
        if (requestId !== latestRequestId) return
        set({ user: res.data, isAuthenticated: true, isLoading: false })
      } catch (err: any) {
        if (requestId !== latestRequestId) return
        const status = err?.response?.status
        if (status === 401 || status === 403) {
          // Session is genuinely invalid - safe to clear.
          set({ user: null, isAuthenticated: false, isLoading: false })
        } else {
          // Transient failure (network, timeout, 5xx, slow API): keep
          // whatever user data is already on screen, just stop loading.
          set({ isLoading: false })
        }
      } finally {
        inFlightFetch = null
      }
    })()

    inFlightFetch = run
    return run
  },

  hasPermission: (perm: string) => {
    const { user } = get()
    if (!user) return false
    if (user.role === 'super_admin') return true
    return user.permissions.includes(perm)
  },
}))
