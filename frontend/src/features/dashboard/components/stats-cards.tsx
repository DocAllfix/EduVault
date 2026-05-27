/**
 * Four KPI cards across the top of the Dashboard.
 *
 * Data: `api.getDashboardStats()` (BP §10 → `/api/dashboard/stats`).
 * The backend returns only THREE counts:
 *   - `courses_count`        (all statuses)
 *   - `regulations_count`    (all statuses)
 *   - `l2_count`             (Level-2 / certified / approved_courses)
 *
 * The prompt asks for FOUR cards including "Corsi in generazione" which
 * the stats endpoint does not break out. We derive that fourth metric
 * client-side from `api.getCourses({ status: 'generating', per_page: 1 })`
 * with `page=1, per_page=100` (small page is fine — the active jobs queue
 * is bounded by the asyncio.Semaphore(1) + queued/research/content/
 * building states, realistically <10 at any time).
 *
 * Loading state: shadcn `Skeleton`. Errors: a discreet inline "—"
 * value plus a toast at the parent level (Dashboard owns the query).
 */

import {
  BookOpen,
  Library,
  Loader2,
  ShieldCheck,
} from 'lucide-react'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { DashboardStats } from '@/lib/api'

interface StatsCardsProps {
  stats: DashboardStats | undefined
  generatingCount: number | undefined
  isLoading: boolean
}

interface CardSpec {
  label: string
  value: number | undefined
  icon: React.ComponentType<{ className?: string }>
  /** Adds a subtle accent — used to mark the "live" generating card. */
  liveAccent?: boolean
}

export function StatsCards({
  stats,
  generatingCount,
  isLoading,
}: StatsCardsProps) {
  const cards: CardSpec[] = [
    {
      label: 'Corsi totali',
      value: stats?.courses_count,
      icon: BookOpen,
    },
    {
      label: 'In generazione',
      value: generatingCount,
      icon: Loader2,
      liveAccent: (generatingCount ?? 0) > 0,
    },
    {
      label: 'Normative indicizzate',
      value: stats?.regulations_count,
      icon: Library,
    },
    {
      label: 'Corsi certificati (L2)',
      value: stats?.l2_count,
      icon: ShieldCheck,
    },
  ]

  return (
    <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
      {cards.map((c) => (
        <Card
          key={c.label}
          className={cn(
            c.liveAccent &&
              'border-brand-primary/30 ring-1 ring-brand-primary/10',
          )}
        >
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>{c.label}</CardTitle>
            <c.icon
              className={cn(
                'size-4 text-muted-foreground',
                c.liveAccent && 'animate-spin text-brand-primary',
              )}
              aria-hidden='true'
            />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className='h-8 w-16' />
            ) : (
              <div className='text-2xl font-bold tabular-nums'>
                {c.value ?? '—'}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
