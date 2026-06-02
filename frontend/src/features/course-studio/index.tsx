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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'

import { useSidebar } from '@/components/ui/sidebar'

import { api, ApiError, type StudioSlide } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { HelpButton } from '@/lib/onboarding/HelpButton'
import { JobsBadge } from '@/components/jobs-badge'
import { OnboardingBanner } from '@/lib/onboarding/OnboardingBanner'
import { startCourseStudioTour } from '@/lib/onboarding/tours/course-studio'
import { SlideViewer } from './components/slide-viewer'
import { SlideEditor } from './components/slide-editor'
import { ImagePicker } from './components/image-picker'
import { RegenerateDialog } from './components/regenerate-dialog'
import { SkeletonReview } from './components/skeleton-review'
import { SlideRail } from './components/slide-rail'
import { StudioTopBar } from './components/studio-topbar'
import { QualityIssuesPanel } from './components/quality-badge'
import { ChatPanel } from './components/chat-panel'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { MessageCircle, ShieldCheck } from 'lucide-react'
import { useQualityChecks, getSlideMaxSeverity } from '@/hooks/use-quality-checks'

export function CourseStudio() {
  const { id } = useParams({ from: '/_authenticated/courses/$id_/studio' })
  const navigate = useNavigate()
  const [selectedIdx, setSelectedIdx] = useState(0)
  // F4 D9: stato filtro sidebar (mostra solo slide con issue)
  const [filterProblematic, setFilterProblematic] = useState(false)

  // F-STUDIO-UX Step 2 (2026-06-02): la sidebar globale (Dashboard / Normative
  // / Admin) ruba 220px che il Course Studio puo` dedicare alla slide preview.
  // Auto-collapse all'ingresso, ripristino stato all'uscita. Il bottone
  // "Toggle Sidebar" nell'header shadcn-admin resta funzionante per overrride
  // manuale.
  const { setOpen, open: sidebarWasOpen } = useSidebar()
  useEffect(() => {
    const wasOpen = sidebarWasOpen
    setOpen(false)
    return () => {
      if (wasOpen) setOpen(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
  // F10 bugfix 2026-06-02 (D-228): `selectedIdx` ora rappresenta l'indice
  // GLOBALE nell'array allSlides (0..N-1), NON `slide.index` che e`
  // module-relative (riparte da 0 ad ogni modulo). Con il vecchio approccio
  // `slides.find(s => s.index === selectedIdx)` cliccare M2-slide-3 ritornava
  // M1-slide-3 (primo match). Ora uso `allSlides[selectedIdx]` come selettore
  // robusto + filtro problematic re-mappato all'indice globale corrispondente.
  const selected =
    (filterProblematic
      ? slides.find(
          (s) =>
            allSlides.findIndex(
              (x) =>
                x.index === s.index && x.module_index === s.module_index,
            ) === selectedIdx,
        ) ?? slides[0]
      : allSlides[selectedIdx]) ??
    slides[0] ??
    allSlides[0]
  // `pos` = posizione della slide selezionata dentro `slides` (filtered o no)
  const pos = selected
    ? slides.findIndex(
        (s) =>
          s.index === selected.index &&
          s.module_index === selected.module_index,
      )
    : -1
  // Helper: data una slide qualsiasi, ritorna il suo indice globale nell'array allSlides
  const globalIndexOf = (s: StudioSlide): number =>
    allSlides.findIndex(
      (x) => x.index === s.index && x.module_index === s.module_index,
    )
  const goPrev = () => {
    if (pos > 0) setSelectedIdx(globalIndexOf(slides[pos - 1]))
  }
  const goNext = () => {
    if (pos >= 0 && pos < slides.length - 1) {
      setSelectedIdx(globalIndexOf(slides[pos + 1]))
    }
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
      else if (e.key === ' ' || e.code === 'Space') {
        // F-STUDIO-UX Step 3 (2026-06-02): spacebar = play/pause audio
        // della slide corrente. Emette evento custom intercettato da
        // TopbarAudioControls (StudioTopBar) per togglare l'<audio>.
        // preventDefault evita lo scroll-down default del browser.
        e.preventDefault()
        window.dispatchEvent(new CustomEvent('studio-audio-toggle'))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  // F-NEXT Fase 1 (2026-06-02): DnD riordino intra-modulo via @dnd-kit.
  // Backend `move_slide` scambia 1 posizione adiacente per chiamata, quindi
  // riordinare da pos N a pos M richiede |M-N| chiamate sequenziali.
  // Optimistic update sulla cache TanStack per UX istantanea, rollback
  // ed evento di refetch finale in caso di errore.
  const qc = useQueryClient()
  const reorderMut = useMutation({
    mutationFn: async ({
      fromGlobal,
      toGlobal,
    }: {
      fromGlobal: number
      toGlobal: number
    }) => {
      if (fromGlobal === toGlobal) return
      const steps = Math.abs(toGlobal - fromGlobal)
      const direction: 'up' | 'down' =
        toGlobal < fromGlobal ? 'up' : 'down'
      // L'API backend usa slide.index module-relative come param URL: ci serve
      // pesare la slide corrente DOPO ogni move, perche` _reindex cambia gli
      // indici. Approccio semplice: usa l'array TanStack come fonte di verita`
      // intermedia + rilegge slide.index dopo ogni move.
      let workingSlides: StudioSlide[] =
        qc.getQueryData<{ slides: StudioSlide[] }>(['course-slides', id])
          ?.slides ?? []
      for (let i = 0; i < steps; i++) {
        const currentPosGlobal =
          direction === 'up' ? fromGlobal - i : fromGlobal + i
        const movingSlide = workingSlides[currentPosGlobal]
        if (!movingSlide) break
        const updated = await api.moveSlide(
          id,
          movingSlide.index,
          direction,
        )
        workingSlides = updated
      }
      return workingSlides
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['course-slides', id] })
      qc.invalidateQueries({ queryKey: ['course-detail', id] })
    },
    onError: (err) => {
      toast.error(
        err instanceof Error
          ? `Riordino fallito: ${err.message}`
          : 'Riordino fallito',
      )
      qc.invalidateQueries({ queryKey: ['course-slides', id] })
    },
  })

  const handleReorder = (fromPosGlobal: number, toPosGlobal: number) => {
    if (fromPosGlobal === toPosGlobal) return
    const from = slides[fromPosGlobal]
    const to = slides[toPosGlobal]
    if (!from || !to) return
    if (from.module_index !== to.module_index) {
      toast.warning(
        'Riordino tra moduli diversi non supportato. Sposta solo dentro lo stesso modulo.',
      )
      return
    }
    // Aggiorna selectedIdx se la slide selezionata stessa e` stata mossa
    // (il suo index potrebbe cambiare dopo backend rebuild).
    reorderMut.mutate({ fromGlobal: fromPosGlobal, toGlobal: toPosGlobal })
  }

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
            <JobsBadge />
            <HelpButton />
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
      {/* F-STUDIO-UX Step 1 (2026-06-01): StudioTopBar 48px sostituisce Header
          esterno + H1 "Course Studio" + RebuildBanner + QualityIssuesSummary.
          Audio mini-controls integrati nella topbar (era box sotto preview). */}
      {!slidesQ.isLoading && !slidesQ.isError && selected ? (
        <StudioTopBar
          courseId={id}
          selected={selected}
          pos={pos}
          total={slides.length}
          goPrev={goPrev}
          goNext={goNext}
          onBack={() => navigate({ to: '/courses/$id', params: { id } })}
          qualityData={qualityQ.data}
          filterActive={filterProblematic}
          onFilterToggle={() => setFilterProblematic(!filterProblematic)}
          audioReady={Boolean(courseQ.data?.audio_manifest_path)}
          courseTitle={courseQ.data?.title}
        />
      ) : (
        <Header>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate({ to: '/courses/$id', params: { id } })}
          >
            <ArrowLeft className="mr-2 h-4 w-4" /> Dettaglio corso
          </Button>
          <div className="ml-auto flex items-center gap-2">
            <JobsBadge />
            <HelpButton />
            <ThemeSwitch />
            <ProfileDropdown />
          </div>
        </Header>
      )}

      <Main>
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
            <OnboardingBanner
              pageId='course-studio'
              title='Modifica le slide del tuo corso'
              body='Naviga i moduli a sinistra, vedi l’anteprima fedele al centro, edita testo e usa gli strumenti AI a destra. Fai il tour per scoprire tutto in 6 passaggi.'
              onStartTour={() => startCourseStudioTour()}
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
            {/* F-STUDIO-UX Step 2 (2026-06-02): sidebar slim 56px (era 220px)
                + auto-collapse sidebar globale per dare ~165px in piu` al canvas.
                Pattern Tome/Pitch/Gamma: icon + numero + dot quality, info
                completa via Tooltip hover. */}
            <div className="grid grid-cols-[224px_minmax(0,1fr)_320px] gap-3 xl:grid-cols-[240px_minmax(0,1fr)_360px] xl:gap-4">
              <div data-tour="studio-sliderail">
                <SlideRail
                  slides={slides}
                  allSlides={allSlides}
                  selectedIdx={selectedIdx}
                  onSelect={setSelectedIdx}
                  qualityData={qualityQ.data}
                  onReorder={handleReorder}
                />
              </div>

              {/* ─── Center: viewer (nav + audio sono nel TopBar) ─── */}
              <section className="flex min-w-0 flex-col gap-3" data-tour="studio-canvas">
                <SlideViewer
                  slide={selected}
                  total={slides.length}
                  courseId={id}
                  rebuildToken={courseQ.data?.last_rebuilt_at ?? null}
                  globalSlideIndex={globalIndexOf(selected)}
                  key={`${id}-${selected.module_index}-${selected.index}`}
                />
              </section>

              {/* ─── Right rail (F-STUDIO-UX Step 5 2026-06-02): 2 sezioni
                  distinte con Separator + label di sezione.
                  - Sopra: "Contenuto slide" (editor testo puro)
                  - Sotto: "Strumenti AI" (Tabs Quality/Chat + Regenerate + ImagePicker) */}
              <aside className="border-border h-[calc(100vh-7rem)] overflow-y-auto rounded-lg border p-4">
                {/* ─── Sezione 1: Contenuto slide (editor testo) ─── */}
                <section aria-label="Contenuto slide" data-tour="studio-editor">
                  <h3 className="text-muted-foreground text-[11px] font-semibold uppercase tracking-wider mb-3">
                    Contenuto slide #{(pos + 1)}
                  </h3>
                  <SlideEditor courseId={id} slide={selected} />
                </section>

                <Separator className="my-5" />

                {/* ─── Sezione 2: Strumenti AI ─── */}
                <section aria-label="Strumenti AI" data-tour="studio-ai-tools">
                  <h3 className="text-muted-foreground text-[11px] font-semibold uppercase tracking-wider mb-3">
                    Strumenti AI
                  </h3>
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
                      className="mt-3 flex h-[420px] flex-col"
                    >
                      <ChatPanel courseId={id} slideIndex={selected.index} />
                    </TabsContent>
                  </Tabs>
                  <div className="mt-4 space-y-2">
                    <RegenerateDialog courseId={id} slide={selected} />
                    {(selected.slide_type === 'CONTENT_IMAGE' ||
                      selected.slide_type === 'DIAGRAM') && (
                      <ImagePicker
                        courseId={id}
                        slide={selected}
                        courseTitle={courseQ.data?.title}
                      />
                    )}
                  </div>
                </section>
              </aside>
            </div>
          </>
        )}
      </Main>
    </>
  )
}
