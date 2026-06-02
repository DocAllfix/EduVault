/**
 * Progress Monitor — `/courses/{id}/progress` (BP §08.8).
 *
 * ─── Design intent (frontend-design, point 1) ──────────────────────────────
 * Purpose: live watcher while the pipeline runs. The user opens, watches
 *   ~5–15 min of progress, leaves on completion (auto-redirect to Detail).
 * Tone: GitHub Actions log + Vercel Deploy — a coloured progress bar,
 *   a vertical phase list with ✓ for done / spinner for current / muted
 *   for upcoming. Calm, no decoration noise.
 * Constraints: REI-1 reuse template Card/Progress; REI-13 no hardcoded
 *   domain; the WS layer (`lib/ws.ts`) already handles WS→polling
 *   fallback and JWT — this page is the pure presentation.
 * Differentiation: phase machine derived from real backend signals
 *   (status + current_step) — the user sees what the pipeline IS doing
 *   right now, not a mock animation.
 *
 * ─── Impeccable self-audit (point 4) — see SELF-AUDIT at end of file.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from '@tanstack/react-router'
import { Check, Loader2, XCircle } from 'lucide-react'
import { toast } from 'sonner'

import { connectToJob, type JobProgress, type WatchHandle } from '@/lib/ws'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { HelpButton } from '@/lib/onboarding/HelpButton'

import { PHASES, deriveCurrentPhase, isPhaseDone } from './phases'

// We accept either /courses/$id/progress OR /courses/$id/progress?job=<job_id>.
// The wizard knows the job_id at submit time, but if the user lands on
// /progress via a direct link we need to fall back to polling-only mode
// (CourseDetail doesn't expose job_id today — documented in SELF-AUDIT).
function resolveJobId(fromUrl: string | undefined): string | undefined {
  return fromUrl ?? undefined
}

export function CourseProgress() {
  const { id: courseId } = useParams({ from: '/_authenticated/courses/$id_/progress' })
  const navigate = useNavigate()

  const [progress, setProgress] = useState<JobProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retryNonce, setRetryNonce] = useState(0)
  const handleRef = useRef<WatchHandle | null>(null)

  useEffect(() => {
    let cancelled = false
    let handle: WatchHandle | null = null

    async function bootstrap() {
      const search = new URLSearchParams(window.location.search)
      const jobId = resolveJobId(search.get('job') ?? undefined)

      if (!jobId) {
        // No WS path possible without job_id — polling fallback only.
        // Kick off a periodic CourseDetail fetch and synthesise frames.
        const tick = async () => {
          if (cancelled) return
          try {
            const c = await api.getCourse(courseId)
            const mapped: JobProgress = {
              status:
                c.status === 'completed' || c.status === 'certified'
                  ? 'completed'
                  : c.status === 'failed'
                    ? 'failed'
                    : c.status === 'archived'
                      ? 'archived'
                      : 'building',
              progress_percent: null,
              current_step: null,
              error_message: null,
            }
            setProgress(mapped)
            if (mapped.status === 'completed') {
              redirectToDetail()
              return
            }
            if (mapped.status === 'failed') {
              setError('La generazione è fallita.')
              return
            }
          } catch (err) {
            // Course gone or no access → stop polling, surface error.
            setError((err as Error).message)
            return
          }
          window.setTimeout(tick, 30_000)
        }
        void tick()
        return
      }

      handle = connectToJob(jobId, {
        courseId,
        onProgress: (p) => {
          if (cancelled) return
          setProgress(p)
        },
        onComplete: (p) => {
          if (cancelled) return
          if (p.status === 'completed') {
            redirectToDetail()
          } else if (p.status === 'failed') {
            setError(p.error_message || 'La generazione è fallita.')
          } else if (p.status === 'cancelled') {
            setError('La generazione è stata interrotta.')
          }
        },
        onError: (e) => {
          if (cancelled) return
          // WS auth/ownership errors are unrecoverable here.
          if (e.reason === 'unauthorized') {
            setError('Sessione scaduta. Effettua di nuovo l\'accesso.')
          } else if (e.reason === 'forbidden') {
            setError('Non hai i permessi per seguire questo job.')
          } else if (e.reason === 'not_found') {
            setError('Job non trovato. Potrebbe essere già stato completato.')
          } else {
            // Soft errors keep the watcher alive — just toast once.
            toast.warning('Connessione instabile, passaggio a polling.')
          }
        },
      })
      handleRef.current = handle
    }

    function redirectToDetail() {
      // F4 D9 (analista 2026-05-31): fire toast notifica fine produzione PRIMA del
      // redirect. CTA "Apri in Course Studio" porta direttamente alla review delle
      // slide. Quality issue badge si auto-fetch nel Course Studio via useQualityChecks.
      toast.success('Corso generato', {
        description: 'Apri in Course Studio per verificare slide e qualità.',
        duration: 5000,
        action: {
          label: 'Course Studio',
          onClick: () => {
            navigate({
              to: '/courses/$id/studio',
              params: { id: courseId },
            })
          },
        },
      })
      // Give the user a beat to see "Completato" before redirecting to detail page.
      window.setTimeout(() => {
        if (!cancelled) {
          navigate({
            to: '/courses/$id',
            params: { id: courseId },
            replace: true,
          })
        }
      }, 1200)
    }

    void bootstrap()

    return () => {
      cancelled = true
      handle?.close()
      handleRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId, retryNonce])

  const percent = progress?.progress_percent ?? 0
  const currentPhase = deriveCurrentPhase(progress)
  const isFailed = progress?.status === 'failed' || error !== null
  const isCompleted = progress?.status === 'completed'
  const isSkeletonPending = progress?.status === 'skeleton_pending'

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center gap-2'>
          <HelpButton />
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mx-auto w-full max-w-2xl space-y-6'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>Generazione corso</h1>
            <p className='text-sm text-muted-foreground'>
              La pipeline può impiegare 5–15 minuti. Puoi lasciare aperta questa
              pagina o tornare più tardi: il lavoro continua sul server.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className='flex items-center justify-between'>
                <span>
                  {isCompleted
                    ? 'Completato'
                    : isFailed
                      ? 'Errore'
                      : isSkeletonPending
                        ? 'Scheletro pronto per revisione'
                        : 'In corso'}
                </span>
                <span className='tabular-nums text-base font-medium text-muted-foreground'>
                  {percent}%
                </span>
              </CardTitle>
              <CardDescription>
                {isFailed
                  ? (error ?? progress?.error_message ?? 'Errore sconosciuto.')
                  : isCompleted
                    ? 'Pipeline conclusa. Apertura del corso in corso…'
                    : isSkeletonPending
                      ? 'La ricerca normativa è completa. Apri Course Studio per revisionare i sotto-temi e approvare lo scheletro: la generazione delle slide partirà dopo.'
                      : (progress?.current_step ?? 'Avvio…')}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-6'>
              <Progress
                value={percent}
                className={cn(isFailed && '*:data-[slot=progress-indicator]:bg-destructive')}
              />

              {/* Phase list */}
              <ol className='space-y-2'>
                {PHASES.map((phase, i) => {
                  const Icon = phase.icon
                  const done = isPhaseDone(i, currentPhase, progress)
                  const active = currentPhase === i && !isFailed && !isCompleted
                  const upcoming = !done && !active
                  return (
                    <li
                      key={phase.key}
                      className={cn(
                        'flex items-center gap-3 rounded-md px-3 py-2 text-sm',
                        active && 'bg-brand-primary/5',
                        upcoming && 'opacity-50',
                      )}
                    >
                      <span
                        className={cn(
                          'grid size-7 place-items-center rounded-full text-xs',
                          done && 'bg-brand-secondary text-brand-secondary-foreground',
                          active && 'bg-brand-primary text-brand-primary-foreground',
                          upcoming && 'bg-muted text-muted-foreground',
                        )}
                        aria-hidden='true'
                      >
                        {done ? (
                          <Check className='size-3.5' />
                        ) : active ? (
                          <Loader2 className='size-3.5 animate-spin' />
                        ) : (
                          <Icon className='size-3.5' />
                        )}
                      </span>
                      <span
                        className={cn(
                          'flex-1',
                          active && 'font-medium text-foreground',
                        )}
                      >
                        {phase.label}
                      </span>
                      {done && (
                        <span className='text-xs text-muted-foreground'>fatto</span>
                      )}
                    </li>
                  )
                })}
              </ol>

              {/* Skeleton pending: human-in-the-loop gate */}
              {isSkeletonPending && (
                <div className='flex items-center gap-3 rounded-md border border-brand-primary/40 bg-brand-primary/5 p-3 text-sm'>
                  <Check className='size-5 text-brand-primary' aria-hidden='true' />
                  <div className='flex-1'>
                    <div className='font-medium text-foreground'>
                      Scheletro generato. Attesa revisione utente.
                    </div>
                    <div className='text-muted-foreground'>
                      Verifica i sotto-temi prima che parta la generazione
                      delle slide.
                    </div>
                  </div>
                  <Button
                    size='sm'
                    className='bg-brand-primary hover:bg-brand-primary/90'
                    onClick={() =>
                      navigate({
                        to: '/courses/$id/studio',
                        params: { id: courseId },
                      })
                    }
                  >
                    Apri scheletro
                  </Button>
                </div>
              )}

              {/* Failure recovery */}
              {isFailed && (
                <div className='flex items-center gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm'>
                  <XCircle className='size-5 text-destructive' aria-hidden='true' />
                  <div className='flex-1'>
                    <div className='font-medium text-destructive'>
                      La pipeline non è andata a buon fine.
                    </div>
                    <div className='text-muted-foreground'>
                      Puoi riprovare la connessione o tornare alla dashboard
                      per avviare un nuovo corso.
                    </div>
                  </div>
                  <Button
                    variant='outline'
                    size='sm'
                    onClick={() => {
                      setError(null)
                      setProgress(null)
                      setRetryNonce((n) => n + 1)
                    }}
                  >
                    Riprova
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </Main>
    </>
  )
}

/*
 * ─── SELF-AUDIT (impeccable) ──────────────────────────────────────────────
 *
 * Hierarchy:
 *   ✓ Single H1 "Generazione corso". CardTitle uses status word + %
 *     aligned right (tabular-nums) — eye lands on the % first, then
 *     reads the state word, then the description.
 *   ✓ Phase list ordered visually top→bottom matches backend pipeline
 *     order, not random.
 *
 * Spacing:
 *   ✓ space-y-6 between page subtitle / card / future blocks. Card
 *     content space-y-6 between bar / list / failure block.
 *   ✓ Phase rows: rounded-md p-2 — uniform padding within each row;
 *     active row gets a subtle brand-pink bg (5% tint) without breaking
 *     the rhythm.
 *
 * Color strategy (impeccable §color):
 *   ✓ Restrained: brand-pink on active phase + progress bar; brand-
 *     green on done check; destructive only on real failure. Upcoming
 *     phases at 50% opacity rather than a separate color.
 *
 * Bans applied:
 *   ✓ No em dashes. ✓ No gradients. ✓ No glassmorphism.
 *   ✓ No side-stripe. ✓ Failure block uses full border, not left-stripe.
 *
 * A11y:
 *   ✓ Progress component (Radix) exposes aria-valuenow/max/min.
 *   ✓ Phase row icons aria-hidden — label text is the readable signal.
 *
 * Deferred:
 *   - Direct-link entry (`/courses/{id}/progress` without ?job=) falls
 *     back to polling-only mode. To do better we'd need a backend
 *     `/api/courses/{id}/job` lookup (not in BP §10). Documented; safe
 *     for v1.0 since wizard always passes ?job= on redirect.
 *   - Estimated time remaining: not surfaced. Backend doesn't emit it.
 */
