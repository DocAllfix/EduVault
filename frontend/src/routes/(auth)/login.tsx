/**
 * `/login` — entry point for unauthenticated users (FASE 6.10).
 *
 * Replaces the template's `/sign-in` route (renamed to match the prompt
 * canonical URLs). Already-authenticated visitors are bounced to the
 * dashboard (or to `?redirect=...` if the gate stashed one).
 */

import { z } from 'zod'
import { createFileRoute, redirect } from '@tanstack/react-router'
import { SignIn } from '@/features/auth/sign-in'
import { isAuthenticated } from '@/lib/auth'

const searchSchema = z.object({
  redirect: z.string().optional(),
})

export const Route = createFileRoute('/(auth)/login')({
  validateSearch: searchSchema,
  beforeLoad: ({ search }) => {
    if (isAuthenticated()) {
      // `redirect` is arbitrary user-supplied; bounce to dashboard if
      // it's unsafe or absent, otherwise pass it through with a cast.
      const safe = typeof search.redirect === 'string' && search.redirect.startsWith('/')
      // Cast through `as` because TanStack's `to` is typed against the
      // known route tree, but the URL string here only validates at
      // runtime.
      throw redirect({
        to: (safe ? search.redirect : '/dashboard') as '/dashboard',
      })
    }
  },
  component: SignIn,
})
