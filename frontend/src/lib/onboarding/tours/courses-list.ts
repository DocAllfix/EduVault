/**
 * F10 Courses list tour — 3 step:
 *  1. filtri stato corso
 *  2. CTA "Nuovo corso"
 *  3. riga corso → click apre dettaglio
 */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="courses-filters"]',
    popover: {
      title: 'Filtra per stato',
      description:
        'Filtra i corsi per stato: in generazione, completati, archiviati. Lo stato `skeleton_pending` indica un corso in attesa di approvazione struttura.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="courses-new-button"]',
    popover: {
      title: 'Nuovo corso',
      description:
        'Apre il wizard di creazione: scegli tipo corso dal catalog, durata, normative, branding. Il sistema avvia la pipeline di generazione completa.',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    element: '[data-tour="courses-table"]',
    popover: {
      title: 'Elenco corsi',
      description:
        'Clicca una riga per aprire Course Studio (editing slide, audio, immagini, qualità). Il badge in colonna stato ti dice se il corso è scaricabile.',
      side: 'top',
      align: 'center',
    },
  },
]

export function startCoursesListTour(): Driver {
  const tour = buildTour('courses-list', steps)
  tour.drive()
  return tour
}
