/** F10 Regulations tour — 3 step. */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="regulations-upload"]',
    popover: {
      title: 'Carica una nuova normativa',
      description:
        'Upload PDF normativo (decreti, accordi Stato-Regioni, regolamenti CE). Il sistema lo parsa, classifica i chunks e crea embedding per il retrieval.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="regulations-list"]',
    popover: {
      title: 'Normative disponibili',
      description:
        'Ogni riga mostra normativa, regione (nazionale/europea), tipo, numero chunks ingeriti. Clicca per dettaglio + corsi compatibili.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="regulations-compatible-courses"]',
    popover: {
      title: 'Corsi compatibili',
      description:
        'Per una normativa selezionata, vedi quali corsi del catalog la usano e il loro coverage_score. Badge: generabile / corpus_thin / no_coverage.',
      side: 'left',
      align: 'start',
    },
  },
]

export function startRegulationsTour(): Driver {
  const tour = buildTour('regulations', steps)
  tour.drive()
  return tour
}
