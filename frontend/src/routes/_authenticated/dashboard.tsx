/**
 * Dashboard route — EduVault (BP §10).
 *
 * Moved from `/_authenticated/` to `/_authenticated/dashboard` in FASE
 * 6.10 — the prompt mandates `/dashboard` as the canonical URL.
 * `_authenticated/index.tsx` now redirects `/` → `/dashboard`.
 *
 * Search schema enables URL-synced table state (page, page size, filter,
 * status + target faceted filters). `useTableUrlState` in `courses-table.tsx`
 * reads from this schema; the `from:` literal there must stay in sync.
 */

import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { Dashboard } from '@/features/dashboard'
import {
  courseStatuses,
  courseTargets,
} from '@/features/dashboard/data/courses-meta'

const dashboardSearchSchema = z.object({
  page: z.number().optional().catch(1),
  pageSize: z.number().optional().catch(10),
  filter: z.string().optional().catch(''),
  status: z
    .array(z.enum(courseStatuses.map((s) => s.value) as [string, ...string[]]))
    .optional()
    .catch([]),
  target: z
    .array(z.enum(courseTargets.map((t) => t.value) as [string, ...string[]]))
    .optional()
    .catch([]),
})

export const Route = createFileRoute('/_authenticated/dashboard')({
  validateSearch: dashboardSearchSchema,
  component: Dashboard,
})
