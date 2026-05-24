/**
 * Course status badge.
 *
 * Maps `CourseSummary.status` to a coloured pill. Five states; the
 * `generating` one has a pulsing dot + spinning icon to signal live
 * activity (Linear.app pattern — `delete-course-dialog` doesn't compete
 * for attention because nothing else on the row animates).
 *
 * Colours chosen to be semantically obvious AND respect the C.F.P.
 * Montessori palette:
 *   - generating → amber (in-progress universal)
 *   - completed  → blue   (BP §10 "completed" is post-pipeline, pre-cert)
 *   - certified  → brand secondary green #769E2E (REI-11 brand use)
 *   - failed     → destructive red (theme token)
 *   - archived   → muted grey
 *
 * We avoid hardcoded Tailwind colour classes where a theme token exists
 * (border, foreground, destructive). Brand-green uses `bg-brand-secondary`
 * defined in `theme.css` @theme inline (FASE 6.3).
 */

import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  courseStatuses,
  type CourseStatusValue,
} from '../data/courses-meta'

type CourseStatusBadgeProps = {
  status: string
  className?: string
}

// Tailwind classes are STATIC strings (no template interpolation) so
// Tailwind v4's content scanner can find them. Don't refactor to
// dynamic class construction — it'll silently strip them in prod build.
const STATUS_CLASS: Record<CourseStatusValue, string> = {
  generating:
    'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-600/40 dark:bg-amber-950/40 dark:text-amber-200',
  completed:
    'border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-600/40 dark:bg-blue-950/40 dark:text-blue-200',
  certified:
    'border-brand-secondary/40 bg-brand-secondary/10 text-brand-secondary dark:border-brand-secondary/40 dark:bg-brand-secondary/20 dark:text-brand-secondary',
  failed:
    'border-red-300 bg-red-50 text-red-800 dark:border-red-600/40 dark:bg-red-950/40 dark:text-red-200',
  archived:
    'border-border bg-muted text-muted-foreground',
}

export function CourseStatusBadge({ status, className }: CourseStatusBadgeProps) {
  const meta = courseStatuses.find((s) => s.value === status)
  if (!meta) {
    // Defensive: backend evolves, new statuses may appear before frontend.
    // Show the raw value muted so QA notices instead of getting nothing.
    return (
      <Badge variant='outline' className={cn('font-mono', className)}>
        {status}
      </Badge>
    )
  }
  const Icon = meta.icon
  const isGenerating = meta.value === 'generating'
  return (
    <Badge
      variant='outline'
      className={cn(STATUS_CLASS[meta.value], className)}
    >
      {isGenerating ? (
        <Loader2 className='animate-spin' aria-hidden='true' />
      ) : (
        <Icon aria-hidden='true' />
      )}
      <span>{meta.label}</span>
      {isGenerating && (
        // Pulsing dot AFTER the label reinforces "live" without crowding
        // the icon. `motion-reduce` respects user a11y prefs.
        <span
          className='ms-1 inline-block size-1.5 rounded-full bg-amber-500 motion-safe:animate-pulse'
          aria-hidden='true'
        />
      )}
    </Badge>
  )
}
