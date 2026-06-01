/**
 * PptxCanvasRenderer — F-STUDIO-UX Step 4 (2026-06-02).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Renderizza una singola slide del PPTX scaricabile come DOM HTML/SVG
 * direttamente nel browser, usando `@aiden0z/pptx-renderer` (Apache 2.0).
 *
 * Strategia:
 *  1. Scarica il PPTX intero del corso UNA volta via api.downloadCourse(id, 'pptx')
 *     e lo persiste in IndexedDB (chiave courseId + rebuildToken).
 *  2. Carica il file via PptxViewer.open() in render-mode 'slide'.
 *  3. Naviga alle slide via goToSlide(index) — zero round-trip backend.
 *
 * Vantaggi vs preview PNG backend:
 *  - 100% fedele al PPTX scaricabile (immagini, diagrammi, layout, font)
 *  - Backend zero carico (no soffice, no OOM Railway, no PNG cache disk)
 *  - Cambio slide <50ms (vs 5-10s cold-start soffice)
 *  - Funziona offline dopo primo download
 *
 * Fallback: se download/parse/render fallisce, chiama onFallback() e il
 * caller (SlideViewer) mostra il PNG backend legacy.
 *
 * Pattern download-then-cache:
 *   - useQuery con TanStack chiama api.downloadCourse() solo se cache mancante
 *   - IndexedDB persiste cross-tab e cross-session
 *   - rebuild_token invalida automaticamente la cache stale
 *
 * NB: edit del testo via SlideEditor → DB → cache PPTX resta valida finche`
 * utente non clicca Rigenera (D-213). Il viewer mostra la versione PRE-edit
 * finche` rebuild_token non cambia.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'

import { api } from '@/lib/api'
import {
  buildCacheKey,
  getCached,
  pruneStaleVersions,
  setCached,
} from '@/lib/pptx-cache'

export interface PptxCanvasRendererProps {
  courseId: string
  /** Indice slide 0-based (allineato all'indicizzazione PPTX builder). */
  slideIndex: number
  /**
   * Token che identifica univocamente la versione del PPTX. Cambia quando
   * `courses.last_rebuilt_at` cambia. Usato come parte della cache key:
   * versioni diverse non si sovrappongono, cache stale auto-evicted.
   *
   * Tipicamente Unix timestamp di `last_rebuilt_at` (vedi backend
   * courses.py:963-964).
   */
  rebuildToken: string
  /**
   * Chiamato quando il rendering client-side fallisce in modo irrecoverable
   * (download timeout, PPTX corrotto, libreria throw). Il caller mostra
   * un fallback (es. PNG backend).
   */
  onFallback?: (reason: string) => void
}

/**
 * Renderizza la slide N del PPTX client-side. Aspect 16:9.
 */
export function PptxCanvasRenderer({
  courseId,
  slideIndex,
  rebuildToken,
  onFallback,
}: PptxCanvasRendererProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  // PptxViewer instance kept across re-renders.
  // Using `any` to avoid bundling type at module init (lazy-loaded library).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const viewerRef = useRef<any>(null)
  const [viewerReady, setViewerReady] = useState(false)
  const [lastError, setLastError] = useState<string | null>(null)

  const cacheKey = useMemo(
    () => buildCacheKey(courseId, rebuildToken),
    [courseId, rebuildToken],
  )

  // ── Step 1: ensure we have the PPTX Blob (cache or download) ───────────
  const pptxQ = useQuery<Blob, Error>({
    queryKey: ['pptx-blob', cacheKey] as const,
    queryFn: async () => {
      // Prune versioni stale di questo corso (rebuild_token diverso).
      await pruneStaleVersions(courseId, rebuildToken)
      const cached = await getCached(cacheKey)
      if (cached) return cached.blob
      // Cache miss: scarica il PPTX intero.
      const blob = await api.downloadCourse(courseId, 'pptx')
      // Salva in cache (fire-and-forget, eventual consistency e` ok)
      void setCached(cacheKey, blob)
      return blob
    },
    // PPTX e` immutabile per il dato `rebuildToken` → cache infinita.
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    retry: 1,
  })

  // ── Step 2: load PPTX nel viewer una volta (NON re-load on slide change)
  useEffect(() => {
    if (!pptxQ.data || !containerRef.current) return
    const container = containerRef.current
    let cancelled = false

    ;(async () => {
      try {
        const { PptxViewer } = await import('@aiden0z/pptx-renderer')
        if (cancelled) return
        // Cleanup previous viewer if any
        if (viewerRef.current) {
          try {
            container.innerHTML = ''
          } catch {
            // noop
          }
        }
        const viewer = new PptxViewer(container, {
          fitMode: 'contain',
          onSlideError: (_idx, err) => {
            // eslint-disable-next-line no-console
            console.warn('pptx slide error', err)
          },
        })
        const arrayBuf = await pptxQ.data!.arrayBuffer()
        await viewer.open(arrayBuf, { renderMode: 'slide' })
        if (cancelled) {
          // ignore: container will be cleared by next mount
          return
        }
        viewerRef.current = viewer
        setViewerReady(true)
        // Naviga subito alla slide corrente.
        try {
          await viewer.goToSlide(slideIndex)
        } catch {
          // se index out of range, resta su slide 0
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        setLastError(msg)
        onFallback?.(msg)
      }
    })()

    return () => {
      cancelled = true
    }
    // viewer e` re-creato solo se cambia il PPTX (cacheKey).
    // slideIndex e` gestito da un useEffect separato (goToSlide).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pptxQ.data])

  // ── Step 3: cambio slide via goToSlide (zero re-load) ────────────────
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || !viewerReady) return
    void viewer.goToSlide(slideIndex).catch((err: unknown) => {
      // eslint-disable-next-line no-console
      console.warn('goToSlide failed', err)
    })
  }, [slideIndex, viewerReady])

  // ── Fallback su errore ─────────────────────────────────────────────────
  if (lastError) {
    return (
      <div className='border-border bg-muted/30 text-muted-foreground flex aspect-video w-full items-center justify-center rounded-lg border text-xs italic'>
        Anteprima non disponibile (errore renderer).
      </div>
    )
  }

  // ── Loading skeleton durante primo download ────────────────────────────
  if (pptxQ.isLoading) {
    return (
      <div className='border-border bg-muted/30 text-muted-foreground flex aspect-video w-full items-center justify-center gap-2 rounded-lg border text-xs italic'>
        <Loader2 className='size-4 animate-spin' />
        Scaricamento anteprima…
      </div>
    )
  }

  if (pptxQ.isError) {
    // Lancia fallback al PNG backend.
    if (onFallback) onFallback('download failed')
    return null
  }

  return (
    <div
      ref={containerRef}
      className='border-border relative aspect-video w-full overflow-hidden rounded-lg border bg-white shadow-sm'
      aria-label='Anteprima PPTX fedele'
    />
  )
}
