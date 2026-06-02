/**
 * F10 onboarding — driver.js config base CFP Montessori-branded.
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Tour spotlight calmo, B2B, brand discreto. NESSUNA animazione esuberante:
 * questo non e` un onboarding consumer-gamification (Notion/Linear) ma
 * uno strumento professionale (Stripe Dashboard). L'utente del cliente CFP
 * sta lavorando, gli stiamo solo facendo "vedere" cosa puo` fare.
 *
 * Pattern: spotlight ring brand-primary (#C82E6E) sottile + popover shadcn-style
 * (background var(--popover), border var(--border)). Niente overlay nero
 * fullscreen (e` distraente) — uso un overlay molto leggero che NON oscura
 * tutto, solo de-enfatizza il resto.
 *
 * NB: driver.js usa CSS custom (`driver-popover-*`, `driverPopoverArrow`, ecc.)
 * — le override sono in `driver-overrides.css` (importato in main.tsx).
 */

import { driver as createDriver, type Driver } from 'driver.js'
import type { Config, DriverHook, DriveStep, PopoverDOM } from 'driver.js'

/**
 * Costanti localStorage per tracciare i tour completati per pagina.
 * Pattern: chiave per pagina → boolean (true se completato/saltato).
 *
 * Vantaggio vs DB column: zero round-trip backend, zero migration, no
 * sync issue cross-device — il signal "ho gia` visto questo tour" e` per
 * sua natura locale (un utente che cambia browser/dispositivo lo rivedra`,
 * cosa preferibile a "non lo vede mai piu` perche` 6 mesi fa l'ha visto
 * sull'altro PC").
 */
export const TOUR_STORAGE_KEY_PREFIX = 'eduvault-tour-completed:'
export const BANNER_STORAGE_KEY_PREFIX = 'eduvault-banner-seen:'

export function tourStorageKey(pageId: string): string {
  return `${TOUR_STORAGE_KEY_PREFIX}${pageId}`
}

export function bannerStorageKey(pageId: string): string {
  return `${BANNER_STORAGE_KEY_PREFIX}${pageId}`
}

export function isTourCompleted(pageId: string): boolean {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(tourStorageKey(pageId)) === '1'
}

export function markTourCompleted(pageId: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(tourStorageKey(pageId), '1')
}

export function resetTour(pageId: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(tourStorageKey(pageId))
}

export function isBannerSeen(pageId: string): boolean {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(bannerStorageKey(pageId)) === '1'
}

export function markBannerSeen(pageId: string): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(bannerStorageKey(pageId), '1')
}

/**
 * Config baseline condivisa da tutti i tour.
 *
 * - `allowClose: true` — utente puo` chiudere con Esc o X (B2B respect)
 * - `showProgress: true` — "1/4" in basso aiuta a percepire la fine
 * - `showButtons` — Prev/Next/Close, NO "Done" custom (driver.js gestisce
 *   automaticamente il bottone finale)
 * - `nextBtnText`/`prevBtnText`/`doneBtnText` in italiano (REI-7: l'UI utente
 *   parla italiano, solo il codice e` in inglese)
 * - `disableActiveInteraction: true` — l'utente NON puo` cliccare sull'elemento
 *   evidenziato durante il tour (evita doppio-flusso confuso). Eccezione:
 *   se uno step ha `disableActiveInteraction: false`, viene rispettato.
 * - `smoothScroll: true` — auto-scroll per portare in viewport l'elemento.
 */
export const BASE_DRIVER_CONFIG: Partial<Config> = {
  showProgress: true,
  allowClose: true,
  smoothScroll: true,
  disableActiveInteraction: true,
  stagePadding: 8,
  stageRadius: 8,
  popoverClass: 'eduvault-popover',
  overlayColor: 'rgb(15 23 42 / 0.55)',
  nextBtnText: 'Avanti →',
  prevBtnText: '← Indietro',
  doneBtnText: 'Fatto',
  // F10 bugfix 2026-06-02: driver.js v1.4 ha rotto il default click su X.
  // L'attributo `allowClose: true` mostra la X ma NON la wira automatica al
  // destroy(). Devo registrare onCloseClick esplicito che chiama .destroy().
  onCloseClick: (_el, _step, opts) => {
    opts.driver.destroy()
  },
}

/**
 * Factory: crea un driver.js instance con la config baseline + steps custom.
 *
 * `pageId` viene usato per marcare il tour come completato in localStorage
 * quando l'utente raggiunge l'ultimo step (o chiude esplicitamente).
 *
 * Pattern: chi chiama (es. hook `useTour`) puo` aggiungere `onDestroyed`
 * custom via `extraConfig.onDestroyed` se necessario.
 */
export function buildTour(
  pageId: string,
  steps: DriveStep[],
  extraConfig?: Partial<Config>,
): Driver {
  const onDestroyStarted: DriverHook = (element, step, opts) => {
    // Any close (Esc / X / completion) marks the tour as seen so we
    // don't pester the user every page reload. If they really want to
    // revisit it, they can click the "?" in the topbar to reset+restart.
    markTourCompleted(pageId)
    if (extraConfig?.onDestroyStarted) {
      extraConfig.onDestroyStarted(element, step, opts)
    }
  }
  return createDriver({
    ...BASE_DRIVER_CONFIG,
    ...extraConfig,
    steps,
    onDestroyStarted,
  })
}

/** Helper popover style applier (usato in step.onPopoverRender per branding) */
export function applyBrandedPopover(popover: PopoverDOM): void {
  if (popover.title) {
    popover.title.style.fontWeight = '600'
    popover.title.style.fontSize = '0.9375rem'
    popover.title.style.letterSpacing = '-0.01em'
  }
  if (popover.description) {
    popover.description.style.fontSize = '0.8125rem'
    popover.description.style.lineHeight = '1.5'
    popover.description.style.marginTop = '0.5rem'
  }
}
