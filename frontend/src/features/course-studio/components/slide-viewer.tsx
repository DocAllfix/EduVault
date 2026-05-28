/**
 * SlideViewer — renders the real PDF page as the slide preview (FASE 9, post-fix #150).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: anteprima fedele 16:9 della slide selezionata, una per SlideType,
 *   così l'operatore vede in-app cosa diventerà il PPTX senza scaricarlo.
 * Tone: brand C.F.P. Montessori — barra primary #C82E6E in alto, badge verde
 *   #769E2E per RECAP, layout pulito Linear-like.
 * Constraints: REI-1 riusa solo primitive Tailwind/shadcn; aspect-video per
 *   il 16:9; nessun overflow (i constraints FASE 1 garantiscono il fit).
 */

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { api, type StudioSlide } from '@/lib/api'

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
      <div className="flex h-full flex-col p-8 pt-10">{children}</div>
      {footer && (
        <div className="text-muted-foreground absolute inset-x-0 bottom-0 flex items-center justify-between px-8 py-2 text-xs">
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
}: {
  slide: StudioSlide
  total: number
  courseId?: string
}) {
  // Try the real PDF render first; only fall back to the schematic preview
  // when the backend can't serve a PNG (no PDF on disk yet / load error).
  const [pdfFailed, setPdfFailed] = useState(false)
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
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <h1 className="text-foreground text-4xl font-bold tracking-tight">
              {slide.title}
            </h1>
            {slide.normative_ref && slide.normative_ref !== '—' && (
              <p className="text-muted-foreground mt-4 text-lg">
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
            <span className="bg-brand-secondary mb-2 inline-block w-fit rounded px-2 py-0.5 text-xs font-bold tracking-wide text-white uppercase">
              Riepilogo
            </span>
          )}
          <h2 className="text-foreground mb-4 text-2xl font-semibold">
            {slide.title}
          </h2>
          <ul className="text-foreground space-y-2 text-base">
            {slideBulletText(slide).map((line, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-primary">•</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </SlideFrame>
      )

    case 'CONTENT_IMAGE':
      return (
        <SlideFrame footer={footer}>
          <h2 className="text-foreground mb-4 text-2xl font-semibold">
            {slide.title}
          </h2>
          <div className="flex flex-1 gap-6">
            <ul className="text-foreground flex-[3] space-y-2 text-base">
              {slideBulletText(slide).map((line, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-primary">•</span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
            <div className="border-border bg-muted flex flex-[2] items-center justify-center rounded-lg border">
              {slide.image.query_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={slide.image.query_url}
                  alt={slide.image.query ?? ''}
                  className="h-full w-full rounded-lg object-contain"
                />
              ) : (
                <span className="text-muted-foreground px-4 text-center text-sm">
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
          <h2 className="text-foreground mb-2 text-xl font-semibold">
            {slide.title}
          </h2>
          <div className="border-border bg-muted flex flex-1 items-center justify-center rounded-lg border">
            {slide.image.diagram_code ? (
              <div
                className="h-full w-full p-4"
                // SVG già sanitizzato lato server (sanitize_svg). In preview
                // mostriamo il codice come testo per sicurezza XSS frontend.
              >
                <span className="text-muted-foreground text-xs">
                  [ diagramma SVG generato — visibile nel PPTX ]
                </span>
              </div>
            ) : (
              <span className="text-muted-foreground text-sm">[ diagramma ]</span>
            )}
          </div>
          <p className="text-muted-foreground mt-2 text-center text-sm italic">
            {slideBulletText(slide)[0] ?? ''}
          </p>
        </SlideFrame>
      )

    case 'QUIZ':
      return (
        <SlideFrame footer={footer}>
          <h2 className="text-foreground mb-6 text-2xl font-semibold">
            {slide.title}
          </h2>
          <div className="space-y-3">
            {(slide.quiz_options ?? []).map((opt, i) => {
              const letter = String.fromCharCode(65 + i)
              const correct = slide.quiz_correct === i
              return (
                <div
                  key={i}
                  className={cn(
                    'flex items-center gap-3 rounded-md border px-4 py-2',
                    correct
                      ? 'border-brand-secondary bg-brand-secondary/10'
                      : 'border-border',
                  )}
                >
                  <span className="text-primary font-bold">{letter}.</span>
                  <span className="text-foreground">{opt}</span>
                  {correct && (
                    <span className="text-brand-secondary ml-auto font-bold">✓</span>
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
          <span className="bg-primary mb-2 inline-block w-fit rounded px-2 py-0.5 text-xs font-bold tracking-wide text-white uppercase">
            Caso Studio
          </span>
          <h2 className="text-foreground mb-4 text-xl font-semibold">
            {slide.title}
          </h2>
          <div className="grid flex-1 grid-cols-3 gap-4">
            {labels.map((label, i) => (
              <div
                key={label}
                className="border-primary bg-muted rounded-md border-l-4 p-3"
              >
                <p className="text-muted-foreground mb-1 text-xs font-bold uppercase">
                  {label}
                </p>
                <p className="text-foreground text-sm">{sections[i] ?? ''}</p>
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
            <h1 className="text-foreground text-5xl font-bold">{slide.title}</h1>
            <p className="text-muted-foreground mt-4 text-base italic">
              Formazione Globale — C.F.P. Montessori
            </p>
          </div>
        </SlideFrame>
      )

    default:
      return (
        <SlideFrame footer={footer}>
          <h2 className="text-foreground text-2xl font-semibold">{slide.title}</h2>
          <p className="text-foreground mt-4">{slide.body ?? ''}</p>
        </SlideFrame>
      )
  }
}
