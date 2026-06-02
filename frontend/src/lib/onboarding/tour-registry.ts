/**
 * F10 tour-registry — mappa URL pattern → page tour starter.
 *
 * ─── Design intent (impeccable) ──────────────────────────────────────
 * Singolo punto di estensione per i tour: aggiungo un nuovo tour =
 * registro qui (pathPattern + starter function) e bona. Niente import
 * sparsi per ogni pagina nel HelpButton: il registro e` self-contained.
 *
 * Pattern matching: l'URL viene confrontato con `pathPattern` come prefix.
 * Il primo match (ordine dell'array) vince. Per le pagine dinamiche
 * (es. `/courses/{id}/studio`) uso wildcard regex implicit (la parte fissa
 * basta come prefix per le pagine canoniche).
 */

import type { Driver } from 'driver.js'

import { resetTour } from './driver-config'
import { startDashboardTour } from './tours/dashboard'
import { startCoursesListTour } from './tours/courses-list'
import { startCourseStudioTour } from './tours/course-studio'
import { startSkeletonReviewTour } from './tours/skeleton-review'
import { startWizardTour } from './tours/wizard'
import { startCourseDetailTour } from './tours/course-detail'
import { startRegulationsTour } from './tours/regulations'
import { startAdminTour } from './tours/admin'
import { startAdminCatalogTour } from './tours/admin-catalog'
import { startAdminImagesTour } from './tours/admin-images'
import { startAdminDiagramsTour } from './tours/admin-diagrams'

/** Tour starter signature: returns the Driver (so caller may inspect/destroy). */
export type TourStarter = () => Driver | null

export interface TourRegistryEntry {
  /** Identificatore univoco usato per localStorage. */
  pageId: string
  /** URL pattern (prefix). Ordine importante: il primo match vince. */
  pathPattern: RegExp
  /** Avvia il tour della pagina e ritorna l'istanza driver. */
  start: TourStarter
  /** Etichetta umana mostrata se si volesse listare i tour disponibili. */
  label: string
}

/**
 * Registry tour. **L'ordine conta**: i pattern piu` specifici devono venire
 * PRIMA dei piu` generici (es. `/courses/.../studio` PRIMA di `/courses/.+`).
 */
export const TOUR_REGISTRY: TourRegistryEntry[] = [
  {
    pageId: 'course-studio',
    pathPattern: /^\/courses\/[^/]+\/studio/,
    start: startCourseStudioTour,
    label: 'Course Studio',
  },
  {
    pageId: 'skeleton-review',
    // Skeleton review e` /courses/{id} con status=skeleton_pending — match URL stessa.
    // Decidiamo runtime se mostrare skeleton vs course detail tour: vedi note in
    // tours/skeleton-review.ts (no-op se non in skeleton_pending).
    pathPattern: /^\/courses\/[^/]+\/skeleton/,
    start: startSkeletonReviewTour,
    label: 'Revisione struttura',
  },
  {
    pageId: 'course-detail',
    pathPattern: /^\/courses\/[^/]+$/,
    start: startCourseDetailTour,
    label: 'Dettaglio corso',
  },
  {
    pageId: 'courses-wizard',
    pathPattern: /^\/courses\/new/,
    start: startWizardTour,
    label: 'Wizard nuovo corso',
  },
  {
    pageId: 'courses-list',
    pathPattern: /^\/courses\/?$/,
    start: startCoursesListTour,
    label: 'Elenco corsi',
  },
  {
    pageId: 'regulations',
    pathPattern: /^\/regulations/,
    start: startRegulationsTour,
    label: 'Normative',
  },
  {
    pageId: 'admin-catalog',
    pathPattern: /^\/admin\/catalog/,
    start: startAdminCatalogTour,
    label: 'Catalogo corsi',
  },
  {
    pageId: 'admin-images',
    pathPattern: /^\/admin\/images/,
    start: startAdminImagesTour,
    label: 'Image library',
  },
  {
    pageId: 'admin-diagrams',
    pathPattern: /^\/admin\/diagrams/,
    start: startAdminDiagramsTour,
    label: 'Diagram catalog',
  },
  {
    pageId: 'admin',
    pathPattern: /^\/admin\/?$/,
    start: startAdminTour,
    label: 'Pannello admin',
  },
  {
    pageId: 'dashboard',
    pathPattern: /^\/(dashboard)?$/,
    start: startDashboardTour,
    label: 'Dashboard',
  },
]

/** Trova la entry del registry che match con il path corrente. */
export function findTourForPath(pathname: string): TourRegistryEntry | null {
  for (const entry of TOUR_REGISTRY) {
    if (entry.pathPattern.test(pathname)) return entry
  }
  return null
}

/**
 * Restart-tour API: reset flag localStorage + relaunch tour. Usato dal
 * bottone `?` topbar — l'utente forza il revisit anche se ha gia` "completato".
 */
export function restartTourForPath(pathname: string): boolean {
  const entry = findTourForPath(pathname)
  if (!entry) return false
  resetTour(entry.pageId)
  entry.start()
  return true
}
