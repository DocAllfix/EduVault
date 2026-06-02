/**
 * F11 (2026-06-02) — JobsBadge: indicatore sidebar dei job attivi.
 *
 * ─── Design intent ────────────────────────────────────────────────────────
 * Piccolo bottone-pill nella topbar globale (accanto a ThemeSwitch).
 * Quando ci sono job attivi:
 *   - mostra spinner + count totale
 *   - click → popover con lista job con progress per ciascuno e CTA
 *     "Apri Studio" → naviga
 * Quando zero job: si nasconde (no UI noise).
 *
 * Pattern visivo coerente con HelpButton F10: ghost variant, size icon.
 */

import { Loader2 } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Progress } from '@/components/ui/progress'
import {
  useJobsStore,
  jobKindLabel,
  type ActiveJob,
} from '@/stores/jobs-store'

function elapsedLabel(startedAt: number): string {
  const sec = Math.floor((Date.now() - startedAt) / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  return `${min} min`
}

function JobRow({
  job,
  onOpen,
}: {
  job: ActiveJob
  onOpen: (courseId: string) => void
}) {
  const pct = job.progressPercent ?? null
  return (
    <div className='border-border bg-card/40 flex flex-col gap-2 rounded-md border p-2.5'>
      <div className='flex items-start justify-between gap-2'>
        <div className='min-w-0 flex-1'>
          <p className='line-clamp-1 text-sm font-medium leading-tight'>
            {job.courseTitle}
          </p>
          <p className='text-muted-foreground text-xs'>
            {jobKindLabel(job.kind)}
            {job.currentStep ? ` · ${job.currentStep}` : ''}
          </p>
        </div>
        <span className='text-muted-foreground shrink-0 text-[10px] tabular-nums'>
          {elapsedLabel(job.startedAt)}
        </span>
      </div>
      {pct !== null && pct >= 0 ? (
        <div className='flex items-center gap-2'>
          <Progress value={pct} className='h-1.5 flex-1' />
          <span className='text-muted-foreground text-[10px] tabular-nums w-8 text-right'>
            {Math.round(pct)}%
          </span>
        </div>
      ) : (
        <div className='flex items-center gap-1.5'>
          <Loader2 className='text-muted-foreground size-3 animate-spin' />
          <span className='text-muted-foreground text-[10px]'>In corso…</span>
        </div>
      )}
      <Button
        variant='ghost'
        size='sm'
        className='h-6 self-end px-2 text-[11px]'
        onClick={() => onOpen(job.courseId)}
      >
        Apri Studio
      </Button>
    </div>
  )
}

export function JobsBadge() {
  const jobs = useJobsStore((s) => s.jobs)
  const navigate = useNavigate()
  if (jobs.length === 0) return null

  function handleOpen(courseId: string) {
    navigate({ to: '/courses/$id/studio', params: { id: courseId } })
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant='ghost'
          size='sm'
          aria-label={`${jobs.length} ${jobs.length === 1 ? 'lavoro' : 'lavori'} in corso`}
          className='text-brand-primary hover:text-brand-primary hover:bg-brand-primary/10 h-8 gap-1.5 px-2 text-xs'
        >
          <Loader2 className='size-3.5 animate-spin' />
          <span className='tabular-nums'>{jobs.length}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align='end' className='w-80 p-2'>
        <div className='text-muted-foreground mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider'>
          Lavori in corso ({jobs.length})
        </div>
        <div className='space-y-2'>
          {jobs.map((job) => (
            <JobRow
              key={`${job.courseId}-${job.kind}`}
              job={job}
              onOpen={handleOpen}
            />
          ))}
        </div>
        <p className='text-muted-foreground mt-2 px-1 text-[10px]'>
          Riceverai una notifica quando ognuno finisce.
        </p>
      </PopoverContent>
    </Popover>
  )
}
