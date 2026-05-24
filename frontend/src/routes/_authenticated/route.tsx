/**
 * Authenticated layout route — gates the entire `_authenticated/**` tree
 * behind the JWT presence + expiry check (FASE 6.10).
 *
 * The `beforeLoad` runs before the component mounts and before any
 * loader/query fires, so unauthenticated users never see a flash of the
 * protected UI. We pass the current href as `?redirect=` so the login
 * page can bounce them back here on success.
 */

import { createFileRoute, redirect } from '@tanstack/react-router'
import { AuthenticatedLayout } from '@/components/layout/authenticated-layout'
import { isAuthenticated } from '@/lib/auth'

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: ({ location }) => {
    if (!isAuthenticated()) {
      throw redirect({
        to: '/login',
        search: { redirect: location.href },
      })
    }
  },
  component: AuthenticatedLayout,
})
