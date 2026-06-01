/**
 * Course Studio — `/courses/{id}/studio` (FASE 8-11, real PDF preview live).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: editor in-app slide-per-slide. L'operatore naviga le slide, vede
 *   l'anteprima fedele (SlideViewer), modifica testo/quiz (SlideEditor),
 *   ascolta la voce (AudioPlayer), cambia immagine (ImagePicker), e rigenera
 *   il PPTX quando ha finito (RebuildBanner).
 * Tone: 3 colonne tipo IDE — sidebar lista slide (sx), viewer+audio (centro),
 *   editor (dx). Brand C.F.P. Montessori.
 * Constraints: REI-1 riusa shadcn; react-query per /slides; nessun tab.
 */

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'

import { api, ApiError, type StudioSlide } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { SlideViewer } from './components/slide-viewer'
import { SlideEditor } from './components/slide-editor'
import { AudioPlayer } from './components/audio-player'
import { ImagePicker } from './components/image-picker'
import { RegenerateDialog } from './components/regenerate-dialog'
import { RebuildBanner } from './components/rebuild-banner'
import { SlideActions } from './components/slide-actions'
import { SkeletonReview } from './components/skeleton-review'
import {
  QualityBadge,
  QualityIssuesPanel,
  QualityIssuesSummary,
} from './components/quality-badge'
import { ChatPanel } from './components/chat-panel'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { MessageCircle, ShieldCheck } from 'lucide-react'
import { useQualityChecks, getSlideMaxSeverity } from '@/hooks/use-quality-checks'

function slideTypeLabel(t: string): string {
  const map: Record<string, string> = {
    TITLE: 'Titolo',
    CONTENT_TEXT: 'Contenuto',
    CONTENT_IMAGE: 'Immagine',
    DIAGRAM: 'Diagramma',
    QUIZ: 'Quiz',
    CASE_STUDY: 'Caso',
    RECAP: 'Riepilogo',
    CLOSING: 'Chiusura',
  }
  return map[t] ?? t
}

export function CourseStudio() {
  const { id } = useParams({ from: '/_authenticated/courses/$id_/studio' })
  const navigate = useNavigate()
  const [selectedIdx, setSelectedIdx] = useState(0)
  // F4 D9: stato filtro sidebar (mostra solo slide con issue)
  const [filterProblematic, setFilterProblematic] = useState(false)

  // D3: a course in `skeleton_pending` has no slides yet — it shows the
  // skeleton review gate instead of the slide IDE. Cheap status query first.
  const courseQ = useQuery({
    queryKey: ['course-detail', id] as const,
    queryFn: () => api.getCourse(id),
  })
  const isSkeletonPending = courseQ.data?.status === 'skeleton_pending'

  const slidesQ = useQuery({
    queryKey: ['course-slides', id] as const,
    queryFn: () => api.getCourseSlides(id),
    enabled: !isSkeletonPending, // don't 409 on a skeleton-pending course
  })

  // F4: quality issues lookup (compute on-the-fly via backend slide_quality_service)
  const qualityQ = useQualityChecks(id, !isSkeletonPending && !slidesQ.isLoading)

  const allSlides: StudioSlide[] = slidesQ.data?.slides ?? []
  // Apply filter problematic if enabled
  const slides: StudioSlide[] = filterProblematic
    ? allSlides.filter((s) => getSlideMaxSeverity(qualityQ.data, s.index) !== null)
    : allSlides
  const selected = slides.find((s) => s.index === selectedIdx) ?? slides[0] ?? allSlides[0]
  const pos = selected ? slides.findIndex((s) => s.index === selected.index) : -1
  const goPrev = () => {
    if (pos > 0) setSelectedIdx(slides[pos - 1].index)
  }
  const goNext = () => {
    if (pos >= 0 && pos < slides.length - 1) setSelectedIdx(slides[pos + 1].index)
  }

  // Navigazione orizzontale stile PowerPoint: frecce ← → da tastiera.
  // Ignora se il focus è in un campo editabile (l'editor di destra).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      const tag = t?.tagName
      if (
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        t?.isContentEditable
      )
        return
      if (e.key === 'ArrowLeft') goPrev()
      else if (e.key === 'ArrowRight') goNext()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  // D3 gate: skeleton-pending course → review UI instead of the slide IDE.
  if (isSkeletonPending) {
    return (
      <>
        <Header>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate({ to: '/courses/$id', params: { id } })}
          >
            <ArrowLeft className="mr-2 h-4 w-4" /> Dettaglio corso
          </Button>
          <div className="ml-auto flex items-center gap-2">
            <ThemeSwitch />
            <ProfileDropdown />
          </div>
        </Header>
        <Main>
          <SkeletonReview
            courseId={id}
            onApproved={() =>
              navigate({ to: '/courses/$id', params: { id } })
            }
          />
        </Main>
      </>
    )
  }

  return (
    <>
      <Header>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate({ to: '/courses/$id', params: { id } })}
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> Dettaglio corso
        </Button>
        <div className="ml-auto flex items-center gap-2">
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>

      <Main>
        <h1 className="mb-4 text-2xl font-bold tracking-tight">Course Studio</h1>

        {slidesQ.isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="aspect-video w-full" />
          </div>
        )}

        {slidesQ.isError && (
          <div className="border-border rounded-lg border p-6 text-center">
            <p className="text-muted-foreground">
              {slidesQ.error instanceof ApiError && slidesQ.error.status === 409
                ? 'Questo corso non ha ancora slide editabili. Genera prima il corso.'
                : 'Impossibile caricare le slide.'}
            </p>
          </div>
        )}

        {!slidesQ.isLoading && !slidesQ.isError && selected && (
          <>
            {/* Banner rigenera + scarica (sempre visibile: l'utente rigenera
                quando ha finito di modificare) */}
            <div className="mb-4">
              <RebuildBanner courseId={id} />
            </div>

            {/* F4 D9 summary issue: visibile solo se ci sono issue */}
            <QualityIssuesSummary
              data={qualityQ.data}
              filterActive={filterProblematic}
              onFilterToggle={() => setFilterProblematic(!filterProblematic)}
            />

            {/* Grid 3-colonne responsive (analista 2026-05-31):
                - Default (>=1280 xl): 220px / 1fr / 360px — center ampio, sidebar+
                  right comodi per i primary buttons (Rigenera/Salva).
                - Su breakpoint stretti (<1280): sidebar 180px / 1fr / 320px,
                  ancora 3-col funzionali ma piu' compatti. Center column
                  resta sempre flexible (min 0).
                - Su <1024 (lg): scendiamo a 2-col stack: sidebar 200px + center
                  (editor in tab sotto), right rail in fondo.
                Calibrato sulla viewport interna effettiva del Main (~726px su
                screen 1040 con app sidebar 250px). */}
            <div className="grid grid-cols-[180px_minmax(0,1fr)_320px] gap-3 xl:grid-cols-[220px_minmax(0,1fr)_360px] xl:gap-4">
              {/* ─── Sidebar: toolbar azioni + lista slide ─── */}
              <aside className="flex h-[calc(100vh-16rem)] min-w-0 flex-col gap-2">
                <SlideActions
                  courseId={id}
                  selected={selected}
                  onSelectIndex={setSelectedIdx}
                />
                <div className="border-border flex-1 space-y-1 overflow-y-auto rounded-lg border p-2">
                {slides.map((s) => (
                  <button
                    key={s.index}
                    onClick={() => setSelectedIdx(s.index)}
                    className={cn(
                      'flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left transition-colors',
                      s.index === selectedIdx
                        ? 'bg-primary/10 text-primary ring-1 ring-primary/30'
                        : 'hover:bg-muted',
                    )}
                  >
                    <span className="flex items-center gap-2 text-sm font-medium leading-tight">
                      <QualityBadge data={qualityQ.data} slideIndex={s.index} />
                      <span className="tabular-nums text-xs opacity-70">
                        {s.index + 1}
                      </span>
                      <span>{slideTypeLabel(s.slide_type)}</span>
                    </span>
                    <span className="text-muted-foreground line-clamp-2 text-xs leading-snug">
                      {s.title}
                    </span>
                  </button>
                ))}
                </div>
              </aside>

              {/* ─── Center: nav orizzontale + viewer + audio ─── */}
              <section className="flex min-w-0 flex-col gap-3">
                <div className="flex items-center justify-between gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goPrev}
                    disabled={pos <= 0}
                    aria-label="Slide precedente"
                  >
                    <ChevronLeft className="mr-1 size-4" /> Precedente
                  </Button>
                  <span className="text-muted-foreground shrink-0 whitespace-nowrap text-sm tabular-nums">
                    Slide <span className="text-foreground font-semibold">{pos + 1}</span> di {slides.length}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goNext}
                    disabled={pos < 0 || pos >= slides.length - 1}
                    aria-label="Slide successiva"
                  >
                    Successiva <ChevronRight className="ml-1 size-4" />
                  </Button>
                </div>
                <SlideViewer
                  slide={selected}
                  total={slides.length}
                  courseId={id}
                  key={`${id}-${selected.index}`}
                />
                <AudioPlayer
                  courseId={id}
                  slideIndex={selected.index}
                  moduleIndex={selected.module_index}
                />
              </section>

              {/* ─── Right rail: editor + Tabs (Quality | Chat) + AI regen + image picker ─── */}
              <aside className="border-border h-[calc(100vh-16rem)] space-y-4 overflow-y-auto rounded-lg border p-4">
                <h2 className="text-sm font-semibold tracking-wide uppercase">
                  Modifica slide {selected.index + 1}
                </h2>
                <SlideEditor courseId={id} slide={selected} />
                {/* F4+F6 Tabs Quality/Chat (vast-hopping post-MVP 2026-05-31) */}
                <Tabs defaultValue="quality">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="quality" className="gap-1.5 text-xs">
                      <ShieldCheck className="size-3.5" />
                      Qualità
                    </TabsTrigger>
                    <TabsTrigger value="chat" className="gap-1.5 text-xs">
                      <MessageCircle className="size-3.5" />
                      Chat AI
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="quality" className="mt-3">
                    <QualityIssuesPanel
                      courseId={id}
                      slideIndex={selected.index}
                      data={qualityQ.data}
                      slideType={selected.slide_type}
                    />
                  </TabsContent>
                  <TabsContent
                    value="chat"
                    className="mt-3 flex h-[480px] flex-col"
                  >
                    <ChatPanel courseId={id} slideIndex={selected.index} />
                  </TabsContent>
                </Tabs>
                <div className="border-border space-y-2 border-t pt-4">
                  <RegenerateDialog courseId={id} slide={selected} />
                  {(selected.slide_type === 'CONTENT_IMAGE' ||
                    selected.slide_type === 'DIAGRAM') && (
                    <ImagePicker courseId={id} slide={selected} />
                  )}
                </div>
              </aside>
            </div>
          </>
        )}
      </Main>
    </>
  )
}
