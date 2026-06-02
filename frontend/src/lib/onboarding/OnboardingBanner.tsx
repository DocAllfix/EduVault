/**
 * F10 OnboardingBanner — banner slim contestuale "Stripe Dashboard"-style.
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Compatto, sotto la topbar, max 3 righe testo. Compare la PRIMA volta che
 * l'utente entra in una pagina; persiste in localStorage che "l'ha visto"
 * (chiave per pagina, no DB column). Si chiude con la X o cliccando "Fai il tour"
 * (che lancia il tour della pagina). Una volta chiuso, non riappare piu`.
 *
 * Pattern visivo: card shadcn `bg-card` + `border-border` + icona Info brand-primary
 * a sx + testo body + 2 azioni a dx (Tour + X).
 *
 * Vincolo REI-1: zero design from scratch. Riusa Card + Button shadcn-admin gia`
 * presenti. Niente nuove dep, niente animation libs.
 */

import { useEffect, useState } from 'react'
import { Sparkles, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { bannerStorageKey, markBannerSeen } from './driver-config'

export interface OnboardingBannerProps {
  /** Identificatore univoco della pagina (es. "dashboard", "course-studio"). */
  pageId: string
  /** Titolo bold (1 riga). */
  title: string
  /** Testo body 1-2 righe. Tieni breve. */
  body: string
  /**
   * Callback invocato quando l'utente clicca "Fai il tour".
   * Tipicamente parte un driver.js tour. Optional: se omesso, il bottone
   * "Tour" non appare e resta solo la X di chiusura.
   */
  onStartTour?: () => void
}

/**
 * Banner slim onboarding contestuale. Use case tipico:
 *
 *     <OnboardingBanner
 *       pageId="dashboard"
 *       title="Benvenuto nella dashboard"
 *       body="Vedi metriche, corsi recenti e accedi alle azioni rapide."
 *       onStartTour={() => startDashboardTour()}
 *     />
 *
 * Render-cycle: al mount controlla localStorage. Se gia` visto → return null
 * (no render = no flash). Altrimenti mostra il banner. Click X o Tour →
 * `markBannerSeen` + unmount via state.
 */
export function OnboardingBanner({
  pageId,
  title,
  body,
  onStartTour,
}: OnboardingBannerProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    // Check al mount: se NON ancora visto, mostra.
    if (typeof window === 'undefined') return
    const seen = window.localStorage.getItem(bannerStorageKey(pageId)) === '1'
    if (!seen) setVisible(true)
  }, [pageId])

  if (!visible) return null

  const dismiss = () => {
    markBannerSeen(pageId)
    setVisible(false)
  }

  const handleTour = () => {
    markBannerSeen(pageId)
    setVisible(false)
    onStartTour?.()
  }

  return (
    <div
      role='status'
      aria-live='polite'
      className='border-border bg-card text-card-foreground mb-4 flex items-start gap-3 rounded-lg border px-4 py-3 shadow-sm'
    >
      <Sparkles
        className='text-brand-primary mt-0.5 size-4 shrink-0'
        aria-hidden='true'
      />
      <div className='min-w-0 flex-1'>
        <p className='text-sm font-semibold leading-tight'>{title}</p>
        <p className='text-muted-foreground mt-1 text-xs leading-relaxed'>
          {body}
        </p>
      </div>
      <div className='flex shrink-0 items-center gap-1.5'>
        {onStartTour ? (
          <Button
            size='sm'
            variant='outline'
            className='h-7 px-2.5 text-xs'
            onClick={handleTour}
          >
            Fai il tour
          </Button>
        ) : null}
        <button
          type='button'
          onClick={dismiss}
          className='text-muted-foreground hover:bg-accent hover:text-foreground rounded-md p-1 transition-colors'
          aria-label='Chiudi banner di benvenuto'
        >
          <X className='size-3.5' />
        </button>
      </div>
    </div>
  )
}
