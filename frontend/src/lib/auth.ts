/**
 * Auth helpers used by route guards (FASE 6.10).
 *
 * `isAuthenticated()` returns true iff a non-expired access token is in
 * localStorage. The JWT payload is decoded inline (no jwt-decode dep —
 * REI-5 minimum code; the same pattern is already in dashboard.tsx and
 * course-detail.tsx, extracted here so route guards don't duplicate it).
 *
 * SECURITY MODEL: this is **client-side gating only**. The backend
 * re-validates every request. A forged or stale token client-side only
 * lets the user see the loading shell of a protected page; the first
 * API call returns 401, the global 401-refresh interceptor in api.ts
 * dispatches `auth:logout`, and the user is bounced to /login.
 */

import { tokenStorage } from './api'

export interface JwtPayload {
  sub: string
  role?: string
  exp?: number
  type?: 'access' | 'refresh'
}

export function decodeAccessToken(): JwtPayload | null {
  const tok = tokenStorage.getAccess()
  if (!tok) return null
  const parts = tok.split('.')
  if (parts.length !== 3) return null
  try {
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json) as JwtPayload
  } catch {
    return null
  }
}

export function isAuthenticated(): boolean {
  const payload = decodeAccessToken()
  if (!payload) return false
  if (payload.type && payload.type !== 'access') return false
  // exp is unix seconds. Allow a 5s clock skew so a token that expires
  // mid-render isn't flagged before the 401 interceptor catches it.
  if (typeof payload.exp === 'number' && Date.now() / 1000 > payload.exp + 5) {
    return false
  }
  return true
}

export function getRole(): string | undefined {
  return decodeAccessToken()?.role
}
