/**
 * Course Studio — `/courses/{id}/studio` (FASE 8-11 vast-hopping-sketch).
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

  const slidesQ = useQuery({
    queryKey: ['course-slides', id] as const,
    queryFn: () => api.getCourseSlides(id),
  })

  const slides: StudioSlide[] = slidesQ.data?.slides ?? []
  const selected = slides.find((s) => s.index === selectedIdx) ?? slides[0]
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

            <div className="grid grid-cols-[200px_1fr_340px] gap-4">
              {/* ─── Sidebar: toolbar azioni + lista slide ─── */}
              <aside className="flex h-[calc(100vh-16rem)] flex-col">
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
                      'flex w-full flex-col rounded-md px-3 py-2 text-left text-sm transition-colors',
                      s.index === selectedIdx
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted',
                    )}
                  >
                    <span className="font-medium">
                      {s.index + 1}. {slideTypeLabel(s.slide_type)}
                    </span>
                    <span className="text-muted-foreground truncate text-xs">
                      {s.title}
                    </span>
                  </button>
                ))}
                </div>
              </aside>

              {/* ─── Center: nav orizzontale + viewer + audio ─── */}
              <section className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goPrev}
                    disabled={pos <= 0}
                    aria-label="Slide precedente"
                  >
                    <ChevronLeft className="mr-1 size-4" /> Precedente
                  </Button>
                  <span className="text-muted-foreground text-sm tabular-nums">
                    Slide {pos + 1} di {slides.length}
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
                <SlideViewer slide={selected} total={slides.length} />
                <AudioPlayer courseId={id} slideIndex={selected.index} />
              </section>

              {/* ─── Right rail: editor + AI regen + image picker ─── */}
              <aside className="border-border h-[calc(100vh-16rem)] space-y-4 overflow-y-auto rounded-lg border p-4">
                <h2 className="text-sm font-semibold tracking-wide uppercase">
                  Modifica slide {selected.index + 1}
                </h2>
                <SlideEditor courseId={id} slide={selected} />
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
