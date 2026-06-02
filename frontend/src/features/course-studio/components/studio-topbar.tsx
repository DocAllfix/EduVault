/**
 * StudioTopBar — F-STUDIO-UX Step 1 (2026-06-01).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Topbar = cockpit slim 48px sticky. Sinistra = "dove sei" (breadcrumb modulo
 * + posizione slide). Centro = stato qualita` come pills compatte (clic =
 * filtra le slide problematiche). Destra = azioni (audio play mini /
 * dirty indicator / rebuild). NO H1 "Course Studio" — il titolo della slide
 * vive dentro il canvas. NO banner permanenti che rubano viewport.
 *
 * Pattern di riferimento: Tome / Pitch / Gamma — top-bar funzionale alta 48px,
 * tutto resta visibile in viewport laptop standard (1280x800).
 *
 * Sostituisce: <RebuildBanner> (~80px) + <QualityIssuesSummary> (~48px) + H1
 * Course Studio (~70px) + spazio Header secondario. Recupero ~200px verticali
 * per la slide preview.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Sparkles,
  Volume2,
  VolumeX,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  api,
  tokenStorage,
  type QualityIssuesResponse,
  type StudioSlide,
} from '@/lib/api'
import { useAudioNarration } from '@/stores/audio-narration-store'
import { usePptxPrecache } from '@/hooks/use-pptx-precache'

export interface StudioTopBarProps {
  courseId: string
  selected: StudioSlide
  pos: number
  total: number
  goPrev: () => void
  goNext: () => void
  onBack: () => void
  qualityData: QualityIssuesResponse | undefined
  filterActive: boolean
  onFilterToggle: () => void
}

export function StudioTopBar({
  courseId,
  selected,
  pos,
  total,
  goPrev,
  goNext,
  onBack,
  qualityData,
  filterActive,
  onFilterToggle,
}: StudioTopBarProps) {
  const qc = useQueryClient()

  // F-NEXT Fase 2 (2026-06-02): pre-cache PPTX in background dopo Rigenera.
  // Hook polling che attende cambio `last_rebuilt_at` e scarica il PPTX nuovo,
  // salvandolo in IndexedDB. Cosi` quando l'utente naviga a una slide subito
  // dopo il rebuild, PptxCanvasRenderer trova il blob in cache → zero loading.
  const precache = usePptxPrecache(courseId)

  // ─── Rebuild + Download mutations ──────────────────────────────────────
  const rebuildMut = useMutation({
    mutationFn: () => api.rebuildCourse(courseId),
    onSuccess: () => {
      toast.success(
        'Rigenerazione avviata. PPTX e PDF pronti a breve; la narrazione vocale viene rigenerata in background (2-10 min).',
      )
      // Snapshot del token PRIMA del rebuild → il hook polla per cambio token.
      const previousToken =
        qc.getQueryData<{ last_rebuilt_at?: string | null }>([
          'course-detail',
          courseId,
        ])?.last_rebuilt_at ?? null
      precache.triggerPrecache(previousToken)
      qc.invalidateQueries({ queryKey: ['course-slides', courseId] })
      qc.invalidateQueries({ queryKey: ['course', courseId] })
      qc.invalidateQueries({ queryKey: ['courses'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
    onError: () => toast.error('Avvio rigenerazione fallito'),
  })

  const downloadMut = useMutation({
    mutationFn: async () => {
      const blob = await api.downloadCourse(courseId, 'pptx')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `corso_${courseId}.pptx`
      a.click()
      URL.revokeObjectURL(url)
    },
    onError: () => toast.error('Download fallito'),
  })

  // ─── Quality counters (compact pills) ──────────────────────────────────
  const errors = qualityData?.by_severity.error ?? 0
  const warnings = qualityData?.by_severity.warning ?? 0
  const infos = qualityData?.by_severity.info ?? 0
  const uniqueProblematic = qualityData
    ? new Set(
        qualityData.issues.map(
          (i: { slide_index: number }) => i.slide_index,
        ),
      ).size
    : 0
  const hasQuality = (errors + warnings + infos) > 0

  return (
    <TooltipProvider delayDuration={200}>
      <header className="bg-background/92 supports-[backdrop-filter]:bg-background/75 sticky top-0 z-30 flex h-12 items-center gap-3 border-b px-3 backdrop-blur">
        {/* ─── Left: back + breadcrumb ─── */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={onBack}
              aria-label="Torna al dettaglio corso"
              className="size-8 shrink-0"
            >
              <ArrowLeft className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Torna al dettaglio corso</TooltipContent>
        </Tooltip>
        <div className="flex min-w-0 items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0 tabular-nums">
            M{(selected.module_index ?? 0) + 1}
          </span>
          <span className="text-border" aria-hidden="true">
            ·
          </span>
          <span className="text-foreground font-medium truncate">
            {selected.title || 'Slide senza titolo'}
          </span>
        </div>

        {/* ─── Center spacer + quality pills ─── */}
        <div className="ml-auto flex shrink-0 items-center gap-2">
          {hasQuality && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={onFilterToggle}
                  data-tour="studio-quality-badge"
                  className={
                    'flex h-7 items-center gap-1.5 rounded-md border px-2 text-xs transition-colors ' +
                    (filterActive
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border hover:bg-muted')
                  }
                  aria-label={
                    filterActive
                      ? 'Mostra tutte le slide'
                      : 'Filtra slide problematiche'
                  }
                >
                  {filterActive ? (
                    <AlertTriangle className="size-3.5 text-amber-500" />
                  ) : (
                    <Filter className="size-3.5" />
                  )}
                  <span className="tabular-nums">{uniqueProblematic}</span>
                  {errors > 0 && (
                    <Badge
                      variant="destructive"
                      className="h-4 px-1 text-[9px] font-semibold leading-none"
                    >
                      {errors}
                    </Badge>
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent>
                {filterActive ? 'Mostra tutte le slide' : (
                  <>
                    {uniqueProblematic}{' '}
                    {uniqueProblematic === 1 ? 'slide richiede' : 'slide richiedono'}{' '}
                    attenzione · {errors} errori · {warnings} warning
                  </>
                )}
              </TooltipContent>
            </Tooltip>
          )}

          {/* ─── Audio mini-player (toggle + play if available) ─── */}
          <TopbarAudioControls
            courseId={courseId}
            slideIndex={selected.index}
            moduleIndex={selected.module_index}
          />

          {/* ─── Navigation ─── */}
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={goPrev}
                  disabled={pos <= 0}
                  aria-label="Slide precedente"
                  className="size-8"
                >
                  <ChevronLeft className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>← Slide precedente</TooltipContent>
            </Tooltip>
            <span className="text-muted-foreground tabular-nums select-none px-1 text-xs">
              {pos + 1}/{total}
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={goNext}
                  disabled={pos < 0 || pos >= total - 1}
                  aria-label="Slide successiva"
                  className="size-8"
                >
                  <ChevronRight className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Slide successiva →</TooltipContent>
            </Tooltip>
          </div>

          {/* ─── Rebuild + Download ─── */}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                size="sm"
                variant="default"
                disabled={rebuildMut.isPending}
                data-tour="studio-rigenera"
                className="h-8 px-2.5 text-xs gap-1.5"
              >
                {rebuildMut.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="size-3.5" />
                )}
                Rigenera
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle className="flex items-center gap-2">
                  <AlertTriangle
                    className="text-amber-600 size-5"
                    aria-hidden="true"
                  />
                  Rigenerare PPTX, PDF e audio?
                </AlertDialogTitle>
                <AlertDialogDescription>
                  La rigenerazione ricostruisce PPTX, PDF e narrazione vocale
                  <strong> dai contenuti correnti del corso nel sistema</strong>.
                  Se hai modificato manualmente il PPTX in PowerPoint e lo hai
                  ricaricato come versione definitiva, quelle modifiche manuali
                  <strong> verranno sovrascritte</strong>. Procedi solo se vuoi
                  applicare le modifiche fatte qui in Course Studio.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Annulla</AlertDialogCancel>
                <AlertDialogAction onClick={() => rebuildMut.mutate()}>
                  Sì, rigenera tutto
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => downloadMut.mutate()}
                disabled={downloadMut.isPending}
                aria-label="Scarica PPTX"
                className="size-8"
              >
                {downloadMut.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Download className="size-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Scarica PPTX</TooltipContent>
          </Tooltip>
        </div>
      </header>
    </TooltipProvider>
  )
}

/**
 * Mini audio player nel topbar. Sostituisce <AudioPlayer> sotto la preview.
 * - Switch on/off narrazione globale
 * - Play/Pause della slide corrente (se ha audio)
 * - Badge "Azure" su provider premium
 * - Spacebar = toggle play (Step 3 wire global keyboard handler)
 */
function TopbarAudioControls({
  courseId,
  slideIndex,
  moduleIndex,
}: {
  courseId: string
  slideIndex: number
  moduleIndex?: number | null
}) {
  const { enabled, toggle } = useAudioNarration()
  const [playing, setPlaying] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [provider, setProvider] = useState<'edge' | 'azure' | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const token = tokenStorage.getAccess()
  const baseUrl = api.slideAudioUrl(
    courseId,
    slideIndex,
    moduleIndex ?? undefined,
  )
  const src = token
    ? `${baseUrl}${baseUrl.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
    : baseUrl

  // Reset stato al cambio slide
  useEffect(() => {
    setPlaying(false)
    setHasError(false)
    setProvider(null)
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
  }, [src])

  // Probe provider (audio/{idx}/info) lazy — solo se narrazione enabled
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api
      .getSlideAudioInfo(courseId, slideIndex, moduleIndex ?? undefined)
      .then((info) => {
        if (!cancelled) setProvider(info.provider)
      })
      .catch(() => {
        if (!cancelled) {
          setProvider(null)
          setHasError(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [courseId, slideIndex, moduleIndex, enabled])

  const togglePlay = () => {
    if (!audioRef.current) return
    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.play().catch(() => setHasError(true))
    }
  }

  // F-STUDIO-UX Step 3 (2026-06-02): listener spacebar globale (vedi
  // course-studio/index.tsx). L'evento custom 'studio-audio-toggle' viene
  // dispatchato quando l'utente preme Space fuori da un input editabile.
  useEffect(() => {
    if (!enabled || hasError) return
    const onToggle = () => togglePlay()
    window.addEventListener('studio-audio-toggle', onToggle)
    return () => window.removeEventListener('studio-audio-toggle', onToggle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, hasError, playing])

  return (
    <div className="border-border flex h-8 items-center gap-1 rounded-md border px-1.5">
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={toggle}
            className="text-muted-foreground hover:text-foreground inline-flex size-6 items-center justify-center"
            aria-pressed={enabled}
            aria-label={
              enabled ? 'Disattiva narrazione' : 'Attiva narrazione'
            }
          >
            {enabled ? (
              <Volume2 className="size-3.5" />
            ) : (
              <VolumeX className="size-3.5" />
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent>
          Narrazione {enabled ? 'attiva' : 'disattivata'}
        </TooltipContent>
      </Tooltip>

      {enabled && !hasError && (
        <>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={togglePlay}
                className="text-foreground hover:bg-muted inline-flex size-6 items-center justify-center rounded"
                aria-label={playing ? 'Pausa' : 'Riproduci'}
              >
                {playing ? (
                  <Pause className="size-3.5" />
                ) : (
                  <Play className="size-3.5" />
                )}
              </button>
            </TooltipTrigger>
            <TooltipContent>Play / Pause (Spazio)</TooltipContent>
          </Tooltip>
          {provider === 'azure' && (
            <Badge
              variant="outline"
              className="border-brand-secondary/40 bg-brand-secondary/10 text-brand-secondary h-5 gap-0.5 px-1 font-mono text-[9px]"
            >
              <Sparkles className="size-2.5" />
              Azure
            </Badge>
          )}
          <audio
            ref={audioRef}
            src={src}
            preload="none"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onError={() => setHasError(true)}
            className="hidden"
          />
        </>
      )}
      {enabled && hasError && (
        <span
          className="text-muted-foreground px-1 text-[10px] italic"
          title="Slide senza narrazione o audio in elaborazione"
        >
          —
        </span>
      )}
    </div>
  )
}
