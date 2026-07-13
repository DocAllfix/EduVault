/**
 * SlideViewer — renders the real PDF page as the slide preview (FASE 9, post-fix #150).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: anteprima fedele 16:9 della slide selezionata, una per SlideType,
 *   così l'operatore vede in-app cosa diventerà il PPTX senza scaricarlo.
 * Tone: brand EduVault — barra primary #C82E6E in alto, badge verde
 *   #769E2E per RECAP, layout pulito Linear-like.
 * Constraints: REI-1 riusa solo primitive Tailwind/shadcn; aspect-video per
 *   il 16:9; nessun overflow (i constraints FASE 1 garantiscono il fit).
 */

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { api, type StudioSlide } from '@/lib/api'
import { PptxCanvasRenderer } from './pptx-canvas-renderer'

function bulletLines(body: string | null | undefined): string[] {
  // Backend may emit body=null with a separate `bullets: string[]` array
  // (the strict SlideContent shape). Guard against both: if body is empty,
  // the caller passes bullets joined elsewhere — return [] here.
  if (!body) return []
  return body
    .split('\n')
    .map((b) => b.trim())
    .filter(Boolean)
}

function slideBulletText(slide: StudioSlide): string[] {
  // Prefer body (string with \n) when populated; otherwise fall back to the
  // structured bullets array that ships alongside it.
  if (slide.body && slide.body.trim()) return bulletLines(slide.body)
  const arr = (slide as unknown as { bullets?: string[] }).bullets
  return Array.isArray(arr) ? arr.filter((b) => b && b.trim()) : []
}

function SlideFrame({
  children,
  footer,
}: {
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <div className="bg-card text-card-foreground border-border relative aspect-video w-full overflow-hidden rounded-lg border shadow-sm">
      {/* Brand bar */}
      <div className="bg-primary absolute inset-x-0 top-0 h-2" />
      {/* Padding scalato per non far overflow del contenuto sulla card aspect-video
          quando il viewer e' in column centrale stretta (~520px). pt-8 lascia
          spazio sotto la brand-bar; pb-10 spazio per il footer assoluto. */}
      <div className="flex h-full min-h-0 flex-col px-6 pt-8 pb-10 sm:px-7">
        {children}
      </div>
      {footer && (
        <div className="text-muted-foreground border-border/40 absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 border-t bg-card/60 px-6 py-1.5 text-[10px] backdrop-blur sm:px-7">
          {footer}
        </div>
      )}
    </div>
  )
}

/** Primary viewer: shows the REAL rendered PDF page so the operator sees
 *  exactly what they'll get in the PPTX (layout, brand, images, diagrams).
 *  Falls back to the schematic React layout if the PNG can't be fetched
 *  (e.g. course never rebuilt, PDF missing, network error). */
function PdfPagePreview({
  courseId,
  slide,
  total,
  onError,
}: {
  courseId: string
  slide: StudioSlide
  total: number
  onError: () => void
}) {
  // Token authenticated URL (the <img> tag doesn't send Authorization headers,
  // same approach used by AudioPlayer for the MP3 stream).
  const token =
    typeof window !== 'undefined'
      ? localStorage.getItem('nexus.accessToken')
      : null
  const base = api.slidePreviewUrl(courseId, slide.index)
  const src = token ? `${base}?token=${encodeURIComponent(token)}` : base

  return (
    <div className='border-border relative aspect-video w-full overflow-hidden rounded-lg border bg-white shadow-sm'>
      <img
        src={src}
        alt={`Anteprima slide ${slide.index + 1}: ${slide.title ?? ''}`}
        className='h-full w-full object-contain'
        onError={onError}
      />
      <div className='text-muted-foreground absolute inset-x-0 bottom-0 flex items-center justify-between bg-white/85 px-4 py-1.5 text-xs backdrop-blur-sm'>
        <span className='truncate'>{slide.normative_ref || '—'}</span>
        <span className='tabular-nums'>
          {slide.index + 1} / {total}
        </span>
      </div>
    </div>
  )
}

export function SlideViewer({
  slide,
  total,
  courseId,
  rebuildToken,
  globalSlideIndex,
}: {
  slide: StudioSlide
  total: number
  courseId?: string
  /** Token cache PPTX (last_rebuilt_at). F-STUDIO-UX Step 4. */
  rebuildToken?: string | null
  /**
   * Posizione globale 0-based della slide nel deck completo (allineata
   * all'indicizzazione PPTX). Diversa da `slide.index` che e` module-relative.
   * F-STUDIO-UX Step 4 (2026-06-02).
   */
  globalSlideIndex?: number
}) {
  // F-STUDIO-UX Step 4 (2026-06-02): try-order rendering.
  //  1) PptxCanvasRenderer client-side (fedele al PPTX scaricabile)
  //     -> usato se rebuildToken disponibile (corso rebuilt almeno una volta)
  //  2) PdfPagePreview server PNG (legacy, PDF dispensa testo-only)
  //  3) Schematic React fallback (se ne` PPTX ne` PDF disponibile)
  const [pptxFailed, setPptxFailed] = useState(false)
  const [pdfFailed, setPdfFailed] = useState(false)

  if (
    courseId &&
    rebuildToken &&
    typeof globalSlideIndex === 'number' &&
    globalSlideIndex >= 0 &&
    !pptxFailed
  ) {
    return (
      <PptxCanvasRenderer
        courseId={courseId}
        slideIndex={globalSlideIndex}
        rebuildToken={rebuildToken}
        onFallback={() => setPptxFailed(true)}
      />
    )
  }

  if (courseId && !pdfFailed) {
    return (
      <PdfPagePreview
        courseId={courseId}
        slide={slide}
        total={total}
        onError={() => setPdfFailed(true)}
      />
    )
  }

  const footer = (
    <>
      <span>{slide.normative_ref || '—'}</span>
      <span>
        {slide.index + 1} / {total}
      </span>
    </>
  )

  switch (slide.slide_type) {
    case 'TITLE':
      return (
        <SlideFrame>
          <div className="flex flex-1 flex-col items-center justify-center px-4 text-center">
            <h1 className="text-foreground line-clamp-3 text-2xl font-bold leading-tight tracking-tight md:text-3xl">
              {slide.title}
            </h1>
            {slide.normative_ref && slide.normative_ref !== '—' && (
              <p className="text-muted-foreground mt-3 line-clamp-2 text-sm md:text-base">
                {slide.normative_ref}
              </p>
            )}
          </div>
        </SlideFrame>
      )

    case 'CONTENT_TEXT':
    case 'RECAP':
      return (
        <SlideFrame footer={footer}>
          {slide.slide_type === 'RECAP' && (
            <span className="bg-brand-secondary mb-2 inline-block w-fit rounded px-2 py-0.5 text-[10px] font-bold tracking-wide text-white uppercase">
              Riepilogo
            </span>
          )}
          <h2 className="text-foreground mb-3 line-clamp-2 text-lg font-semibold leading-tight tracking-tight md:text-xl">
            {slide.title}
          </h2>
          <ul className="text-foreground min-h-0 flex-1 space-y-1.5 overflow-hidden text-sm leading-snug">
            {slideBulletText(slide).slice(0, 6).map((line, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-primary mt-0.5 shrink-0">•</span>
                <span className="line-clamp-2">{line}</span>
              </li>
            ))}
          </ul>
        </SlideFrame>
      )

    case 'CONTENT_IMAGE':
      return (
        <SlideFrame footer={footer}>
          <h2 className="text-foreground mb-3 line-clamp-2 text-lg font-semibold leading-tight tracking-tight md:text-xl">
            {slide.title}
          </h2>
          <div className="flex min-h-0 flex-1 gap-4">
            <ul className="text-foreground min-h-0 flex-[3] space-y-1.5 overflow-hidden text-sm leading-snug">
              {slideBulletText(slide).slice(0, 6).map((line, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-primary mt-0.5 shrink-0">•</span>
                  <span className="line-clamp-2">{line}</span>
                </li>
              ))}
            </ul>
            <div className="border-border bg-muted flex flex-[2] items-center justify-center overflow-hidden rounded-lg border">
              {slide.image.query_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={slide.image.query_url}
                  alt={slide.image.query ?? ''}
                  className="h-full w-full rounded-lg object-cover"
                />
              ) : (
                <span className="text-muted-foreground px-3 text-center text-xs">
                  [ {slide.image.query ?? 'immagine'} ]
                </span>
              )}
            </div>
          </div>
        </SlideFrame>
      )

    case 'DIAGRAM':
      return (
        <SlideFrame footer={footer}>
          <h2 className="text-foreground mb-2 line-clamp-2 text-lg font-semibold leading-tight md:text-xl">
            {slide.title}
          </h2>
          <div className="border-border bg-muted flex min-h-0 flex-1 items-center justify-center rounded-lg border">
            {slide.image.diagram_code ? (
              <div className="h-full w-full p-3">
                <span className="text-muted-foreground text-xs">
                  [ diagramma SVG generato — visibile nel PPTX ]
                </span>
              </div>
            ) : (
              <span className="text-muted-foreground text-xs">[ diagramma ]</span>
            )}
          </div>
          <p className="text-muted-foreground mt-2 line-clamp-1 text-center text-xs italic">
            {slideBulletText(slide)[0] ?? ''}
          </p>
        </SlideFrame>
      )

    case 'QUIZ':
      return (
        <SlideFrame footer={footer}>
          <h2 className="text-foreground mb-3 line-clamp-2 text-lg font-semibold leading-tight md:text-xl">
            {slide.title}
          </h2>
          <div className="min-h-0 flex-1 space-y-1.5 overflow-hidden">
            {(slide.quiz_options ?? []).slice(0, 4).map((opt, i) => {
              const letter = String.fromCharCode(65 + i)
              const correct = slide.quiz_correct === i
              return (
                <div
                  key={i}
                  className={cn(
                    'flex items-start gap-2 rounded-md border px-3 py-1.5 text-sm leading-snug',
                    correct
                      ? 'border-brand-secondary bg-brand-secondary/10'
                      : 'border-border',
                  )}
                >
                  <span className="text-primary mt-0.5 shrink-0 font-bold">
                    {letter}.
                  </span>
                  <span className="text-foreground line-clamp-2 flex-1">{opt}</span>
                  {correct && (
                    <span className="text-brand-secondary mt-0.5 shrink-0 font-bold">
                      ✓
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </SlideFrame>
      )

    case 'CASE_STUDY': {
      const sections = (slide.body ?? '').split('---').map((s) => s.trim())
      const labels = ['Situazione', 'Azione', 'Risultato']
      return (
        <SlideFrame footer={footer}>
          <span className="bg-primary mb-1.5 inline-block w-fit rounded px-2 py-0.5 text-[10px] font-bold tracking-wide text-white uppercase">
            Caso Studio
          </span>
          <h2 className="text-foreground mb-3 line-clamp-2 text-lg font-semibold leading-tight md:text-xl">
            {slide.title}
          </h2>
          <div className="grid min-h-0 flex-1 grid-cols-3 gap-2.5">
            {labels.map((label, i) => (
              <div
                key={label}
                className="border-primary bg-muted overflow-hidden rounded-md border-l-4 p-2.5"
              >
                <p className="text-muted-foreground mb-1 text-[10px] font-bold uppercase">
                  {label}
                </p>
                <p className="text-foreground line-clamp-6 text-xs leading-snug">
                  {sections[i] ?? ''}
                </p>
              </div>
            ))}
          </div>
        </SlideFrame>
      )
    }

    case 'CLOSING':
      return (
        <SlideFrame>
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <h1 className="text-foreground text-4xl font-bold leading-tight md:text-5xl">
              {slide.title}
            </h1>
            <p className="text-muted-foreground mt-4 text-base italic">
              EduVault — Formazione professionale
            </p>
          </div>
        </SlideFrame>
      )

    default:
      return (
        <SlideFrame footer={footer}>
          <h2 className="text-foreground line-clamp-2 text-xl font-semibold leading-tight">
            {slide.title}
          </h2>
          <p className="text-foreground mt-3 line-clamp-6 text-sm">
            {slide.body ?? ''}
          </p>
        </SlideFrame>
      )
  }
}
