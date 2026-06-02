/**
 * usePptxPrecache — F-NEXT Fase 2 (2026-06-02).
 *
 * Hook che pre-scarica il PPTX in background DOPO una Rigenera, e lo salva in
 * IndexedDB cache (riusa lib `pptx-cache`). Quando l'utente naviga al
 * Course Studio dopo il rebuild, PptxCanvasRenderer trova subito il blob in
 * cache → zero loading spinner.
 *
 * Pattern:
 *  1. Quando `rebuildTriggered` cambia da false a true, parte il polling
 *  2. Poll `api.getCourse(courseId)` ogni 5s
 *  3. Quando `data.last_rebuilt_at` ≠ `previousToken` (cioe` il backend ha
 *     finito di ricostruire il PPTX) → fetch del nuovo PPTX (~15-25MB)
 *  4. setCached(courseId + newToken, blob)
 *  5. Stop polling, reset rebuildTriggered → false
 *
 * Timeout: 3 minuti totali. Se non rileviamo cambio token nel tempo,
 * abbandoniamo silenziosamente (utente vedra` loading normale al primo
 * apri-studio successivo).
 *
 * Errori (download/cache write) sono catturati silently: best-effort.
 */

import { useEffect, useRef, useState } from 'react'

import { api } from '@/lib/api'
import { buildCacheKey, setCached } from '@/lib/pptx-cache'

const POLL_INTERVAL_MS = 5000
const MAX_POLL_DURATION_MS = 3 * 60 * 1000

export interface UsePptxPrecacheResult {
  /** True quando il polling sta cercando un nuovo rebuild_token. */
  isPolling: boolean
  /** True quando stiamo scaricando il PPTX nuovo (post-detection). */
  isFetching: boolean
  /** True quando l'ultimo precache e` riuscito (cache valida pronta). */
  isReady: boolean
  /** Trigger esterno: chiama questa quando rebuildMut.onSuccess fires. */
  triggerPrecache: (previousToken: string | null | undefined) => void
}

export function usePptxPrecache(courseId: string): UsePptxPrecacheResult {
  const [isPolling, setIsPolling] = useState(false)
  const [isFetching, setIsFetching] = useState(false)
  const [isReady, setIsReady] = useState(false)
  const cancelRef = useRef<{ cancelled: boolean }>({ cancelled: false })

  // Cleanup su unmount (non lasciare promise in volo)
  useEffect(() => {
    return () => {
      cancelRef.current.cancelled = true
    }
  }, [])

  const triggerPrecache = (
    previousToken: string | null | undefined,
  ) => {
    const ref = cancelRef.current
    setIsPolling(true)
    setIsReady(false)
    const startedAt = Date.now()
    const tick = async (): Promise<void> => {
      if (ref.cancelled) return
      if (Date.now() - startedAt > MAX_POLL_DURATION_MS) {
        setIsPolling(false)
        return
      }
      try {
        const course = await api.getCourse(courseId)
        if (ref.cancelled) return
        const newToken = course.last_rebuilt_at ?? null
        if (newToken && newToken !== previousToken) {
          // Detected nuovo rebuild_token → scarica e cache.
          setIsPolling(false)
          setIsFetching(true)
          try {
            const blob = await api.downloadCourse(courseId, 'pptx')
            if (ref.cancelled) return
            await setCached(buildCacheKey(courseId, newToken), blob)
            setIsReady(true)
          } catch {
            // best-effort: errore download/cache non bloccante per UX.
          } finally {
            if (!ref.cancelled) setIsFetching(false)
          }
          return
        }
      } catch {
        // ignora errori network del polling, riprova al prossimo tick
      }
      setTimeout(tick, POLL_INTERVAL_MS)
    }
    void tick()
  }

  return { isPolling, isFetching, isReady, triggerPrecache }
}
