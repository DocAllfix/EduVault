/**
 * Route /admin — Admin dashboard (FASE 6.9).
 */

import { createFileRoute } from '@tanstack/react-router'
import { Admin } from '@/features/admin'

export const Route = createFileRoute('/_authenticated/admin/')({
  component: Admin,
})
