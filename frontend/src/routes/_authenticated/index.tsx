/**
 * `/` (authenticated) — redirects to `/dashboard`.
 *
 * The `_authenticated` parent route already gates on auth (FASE 6.10
 * `_authenticated/route.tsx`), so unauthenticated visitors never reach
 * this redirect — they're sent to `/login` first.
 */

import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authenticated/')({
  beforeLoad: () => {
    throw redirect({ to: '/dashboard' })
  },
})
