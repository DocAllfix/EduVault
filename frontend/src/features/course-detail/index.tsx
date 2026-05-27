/**
 * Course Detail — `/courses/{id}` (BP §10).
 *
 * ─── Design intent (frontend-design, point 1) ──────────────────────────────
 * Purpose: post-generation reference page. Operator opens to download
 *   artifacts, reviewer opens to certify, anyone can audit the citation
 *   provenance (normative_fingerprint).
 * Tone: Linear issue detail — info block at top, download grid right
 *   below, fingerprint as a collapsible list at the bottom. No tabs.
 * Constraints: REI-1 reuse Card/Button/Collapsible; REI-5 reuse
 *   `CoursesRowActions` download function (DRY: same blob+filename
 *   logic as the dashboard table actions); BP §10: certify is admin+
 *   reviewer only and requires status='completed'.
 * Differentiation: fingerprint normativo come collapsible che mostra
 *   refs + chunk_count + generated_at: l'AI cita davvero, non inventa
 *   (BP §00). Visibilità della provenance è il deliverable di valore.
 *
 * ─── Impeccable self-audit (point 4) — see SELF-AUDIT at end of file.
 */

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import {
  ArrowLeft,
  ChevronDown,
  FileText,
  Headphones,
  Loader2,
  Pencil,
  Presentation,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, type DownloadFormat } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { CourseStatusBadge } from '@/features/dashboard/components/course-status-badge'
import { tokenStorage } from '@/lib/api'

function getRoleFromToken(): string | undefined {
  const tok = tokenStorage.getAccess()
  if (!tok) return undefined
  try {
    const p = tok.split('.')[1]
    const padded = p + '==='.slice((p.length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return (JSON.parse(json) as { role?: string }).role
  } catch {
    return undefined
  }
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: 'long',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

const DOWNLOADS: { format: DownloadFormat; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { format: 'pptx', label: 'PPTX', icon: Presentation },
  { format: 'pdf', label: 'PDF', icon: FileText },
  { format: 'audio', label: 'Audio (ZIP)', icon: Headphones },
]

// FIX #31 MOSSA 3 (2026-05-27): audio TTS spostato in background dopo
// pipeline. Il corso può essere `status=completed` con `audio_manifest_path`
// ancora NULL (audio in elaborazione bg, 2-3 min). Il polling qui sotto
// rileva quando arriva. Timeout duro 12 min: oltre, l'utente vede "audio
// non disponibile" invece di uno spinner infinito (caso fallimento bg
// silenzioso — non distinguibile da "in corso" senza migration apposita).
// FIX #32 (analista review 12 + #R-audio-fe-timeout-4h-only chiuso):
// 5→12 min copre corsi 8h (Preposti ~644 slide × 1.5s / sem=6 ≈ 167s
// audio bg + overhead = ~4-5 min totali, ma su Railway con concorrenza
// può salire fino a 8-10 min). 12 min dà margine sicuro senza spinner
// fastidiosi a 4h tipici (che completano in 3 min). Cost: 0 — il polling
// si arresta appena audio_manifest_path appare.
const AUDIO_POLL_INTERVAL_MS = 5_000  // 5s tra un check e il successivo
const AUDIO_POLL_TIMEOUT_MS = 12 * 60_000  // 12 min totali di attesa (copre 8h)

export function CourseDetail() {
  const { id } = useParams({ from: '/_authenticated/courses/$id' })
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const role = getRoleFromToken()
  const [downloadingFmt, setDownloadingFmt] = useState<DownloadFormat | null>(null)
  const [certifying, setCertifying] = useState(false)
  const [deleting, setDeleting] = useState(false)
  // FIX #31 MOSSA 3: timestamp inizio polling audio + flag timeout scaduto
  const [audioPollStart] = useState<number>(() => Date.now())
  const [audioTimedOut, setAudioTimedOut] = useState(false)

  const courseQ = useQuery({
    queryKey: ['course', id] as const,
    queryFn: () => api.getCourse(id),
    // FIX #31 MOSSA 3: polling automatico quando il corso è completed ma
    // l'audio manifest non è ancora pronto (= bg task in elaborazione).
    // Stop polling se: status non completed, OR audio già pronto, OR
    // timeout 5 min superato.
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      const isCompleted = data.status === 'completed' || data.status === 'certified'
      const audioReady = Boolean(data.audio_manifest_path)
      const elapsed = Date.now() - audioPollStart
      if (!isCompleted) return false  // ancora in generation: lascio WS
      if (audioReady) return false  // audio arrivato: stop polling
      if (elapsed >= AUDIO_POLL_TIMEOUT_MS) {
        if (!audioTimedOut) setAudioTimedOut(true)
        return false  // timeout 5 min: stop
      }
      return AUDIO_POLL_INTERVAL_MS  // continua a pollare
    },
  })

  async function handleDownload(fmt: DownloadFormat, title: string) {
    setDownloadingFmt(fmt)
    try {
      const blob = await api.downloadCourse(id, fmt)
      const safeTitle = title.replace(/[^\w\-]+/g, '_').slice(0, 60) || id
      const ext = fmt === 'audio' ? 'zip' : fmt
      triggerBlobDownload(blob, `${safeTitle}.${ext}`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Download non riuscito.')
    } finally {
      setDownloadingFmt(null)
    }
  }

  async function handleCertify() {
    setCertifying(true)
    try {
      await api.certifyCourse(id)
      toast.success('Corso certificato (livello L2).')
      await queryClient.invalidateQueries({ queryKey: ['course', id] })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Certificazione non riuscita.')
    } finally {
      setCertifying(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Archiviare questo corso? L\'azione non è reversibile dall\'interfaccia.')) {
      return
    }
    setDeleting(true)
    try {
      await api.deleteCourse(id)
      toast.success('Corso archiviato.')
      navigate({ to: '/dashboard', replace: true })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Archiviazione non riuscita.')
    } finally {
      setDeleting(false)
    }
  }

  const course = courseQ.data
  const downloadable = course?.status === 'completed' || course?.status === 'certified'
  const canCertify =
    course?.status === 'completed' &&
    (role === 'admin' || role === 'reviewer')
  const canDelete = course && course.status !== 'archived'

  const fingerprint = course?.normative_fingerprint as
    | { refs?: string[]; chunk_count?: number; generated_at?: string }
    | undefined

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center gap-2'>
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mx-auto w-full max-w-3xl space-y-6'>
          <Button variant='ghost' size='sm' onClick={() => navigate({ to: '/dashboard' })}>
            <ArrowLeft aria-hidden='true' /> Dashboard
          </Button>

          {courseQ.isLoading ? (
            <div className='space-y-4'>
              <Skeleton className='h-8 w-2/3' />
              <Skeleton className='h-4 w-1/2' />
              <Skeleton className='h-40 w-full' />
            </div>
          ) : courseQ.isError || !course ? (
            <Card>
              <CardHeader>
                <CardTitle>Corso non trovato</CardTitle>
                <CardDescription>
                  {courseQ.error instanceof ApiError
                    ? courseQ.error.message
                    : 'Errore di caricamento.'}
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <>
              {/* Info card */}
              <div>
                <div className='mb-2 flex flex-wrap items-start justify-between gap-3'>
                  <h1 className='text-2xl font-bold tracking-tight'>{course.title}</h1>
                  <CourseStatusBadge status={course.status} />
                </div>
                <p className='text-sm text-muted-foreground'>
                  {course.course_type} · {course.target === 'discente' ? 'Discente' : 'Formatore'} ·{' '}
                  {course.duration_hours} h · {course.region}
                </p>
                <p className='mt-1 text-xs text-muted-foreground'>
                  Creato il {dateFmt.format(new Date(course.created_at))}
                </p>
              </div>

              {/* Downloads */}
              <Card>
                <CardHeader>
                  <CardTitle className='text-lg'>Artefatti</CardTitle>
                  <CardDescription>
                    {downloadable
                      ? 'Scarica gli output generati dalla pipeline.'
                      : 'I download saranno disponibili al termine della generazione.'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className='grid gap-3 sm:grid-cols-3'>
                    {DOWNLOADS.map((d) => {
                      const Icon = d.icon
                      const busy = downloadingFmt === d.format
                      // FIX #31 MOSSA 3: audio è pronto solo quando
                      // course.audio_manifest_path è popolato (background
                      // task completato). Finché è null, mostra "in
                      // elaborazione" — o "non disponibile" se timeout 5 min.
                      const audioReady = Boolean(course.audio_manifest_path)
                      const audioPending =
                        d.format === 'audio' && downloadable && !audioReady
                      const audioFailed = audioPending && audioTimedOut
                      const audioDisabled = d.format === 'audio' && !audioReady
                      return (
                        <Button
                          key={d.format}
                          variant='outline'
                          className='h-auto justify-start gap-3 p-4'
                          disabled={!downloadable || busy || audioDisabled}
                          onClick={() => handleDownload(d.format, course.title)}
                        >
                          {busy ? (
                            <Loader2 className='size-5 animate-spin' aria-hidden='true' />
                          ) : audioPending && !audioFailed ? (
                            <Loader2 className='size-5 animate-spin text-muted-foreground' aria-hidden='true' />
                          ) : (
                            <Icon className='size-5 text-muted-foreground' aria-hidden='true' />
                          )}
                          <div className='flex flex-col items-start text-start'>
                            <span className='font-medium'>{d.label}</span>
                            <span className='text-xs text-muted-foreground'>
                              {d.format === 'pptx' && 'Presentazione PowerPoint'}
                              {d.format === 'pdf' && 'Dispensa stampabile'}
                              {d.format === 'audio' && audioReady && 'Narrazione MP3'}
                              {d.format === 'audio' && !audioReady && !audioFailed && 'In elaborazione…'}
                              {d.format === 'audio' && audioFailed && 'Audio non disponibile'}
                            </span>
                          </div>
                        </Button>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Normative fingerprint */}
              <Card>
                <CardHeader>
                  <CardTitle className='text-lg'>Fingerprint normativo</CardTitle>
                  <CardDescription>
                    Tracciamento delle normative consultate dal Research Agent.
                    Ogni slide è ancorata a chunk reali, non inventati (BP §00).
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!fingerprint?.refs?.length ? (
                    <p className='text-sm text-muted-foreground'>
                      Nessuna citazione registrata per questo corso.
                    </p>
                  ) : (
                    <Collapsible>
                      <CollapsibleTrigger asChild>
                        <Button variant='ghost' className='w-full justify-between'>
                          <span>
                            {fingerprint.refs.length} riferimenti normativi ·{' '}
                            {fingerprint.chunk_count ?? 0} chunk citati
                          </span>
                          <ChevronDown className='size-4 transition-transform data-[state=open]:rotate-180' aria-hidden='true' />
                        </Button>
                      </CollapsibleTrigger>
                      <CollapsibleContent className='CollapsibleContent'>
                        <ul className='mt-3 space-y-1 border-t pt-3 text-sm'>
                          {fingerprint.refs.map((ref) => (
                            <li key={ref} className='font-mono text-xs text-muted-foreground'>
                              {ref}
                            </li>
                          ))}
                        </ul>
                        {fingerprint.generated_at && (
                          <p className='mt-3 text-xs text-muted-foreground'>
                            Generato il {dateFmt.format(new Date(fingerprint.generated_at))}
                          </p>
                        )}
                      </CollapsibleContent>
                    </Collapsible>
                  )}
                </CardContent>
              </Card>

              {/* Actions */}
              <div className={cn('flex flex-wrap items-center justify-between gap-3')}>
                <div className='flex gap-2'>
                  <Button
                    variant='outline'
                    onClick={() =>
                      navigate({ to: '/courses/$id/studio', params: { id } })
                    }
                  >
                    <Pencil aria-hidden='true' /> Apri Studio
                  </Button>
                  {canCertify && (
                    <Button onClick={handleCertify} disabled={certifying}>
                      {certifying ? (
                        <Loader2 className='animate-spin' aria-hidden='true' />
                      ) : (
                        <ShieldCheck aria-hidden='true' />
                      )}
                      Certifica come L2
                    </Button>
                  )}
                </div>
                {canDelete && (
                  <Button
                    variant='ghost'
                    onClick={handleDelete}
                    disabled={deleting}
                    className='text-destructive hover:text-destructive'
                  >
                    {deleting ? (
                      <Loader2 className='animate-spin' aria-hidden='true' />
                    ) : (
                      <Trash2 aria-hidden='true' />
                    )}
                    Archivia
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </Main>
    </>
  )
}

/*
 * ─── SELF-AUDIT (impeccable) ──────────────────────────────────────────────
 *
 * Hierarchy:
 *   ✓ H1 = course title (the document IS the course). Status badge
 *     aligned right balances the visual weight.
 *   ✓ Meta line text-sm, date text-xs muted: three descents.
 *
 * Spacing:
 *   ✓ space-y-6 between back link / info block / downloads / fingerprint /
 *     actions. Same as Progress Monitor for cross-page consistency.
 *   ✓ Downloads grid sm:grid-cols-3 — when wide enough each Button gets
 *     equal width with icon left + 2-line label.
 *
 * Color:
 *   ✓ Restrained: brand only on Certify CTA + status badge variants
 *     inherited from CourseStatusBadge. Destructive text-only on Archive.
 *
 * Bans:
 *   ✓ No em dashes. ✓ No nested cards (info block is plain divs).
 *   ✓ No modal — using native confirm() for delete to avoid pulling in
 *     AlertDialog for one action. (Reviewer feedback welcome: switch to
 *     shadcn AlertDialog in 6.10 if confirm() too brutal.)
 *
 * Provenance focus:
 *   ✓ Fingerprint card has its own block at the bottom, not buried.
 *     Citation provenance is THE differentiator of this product (AI
 *     cites, never invents — BP §00). The Collapsible respects users
 *     who don't care to read 30 refs, while making them one click away.
 */
