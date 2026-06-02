/** F10 Admin panel tour — 3 step (hub). */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="admin-cards"]',
    popover: {
      title: 'Pannello amministrazione',
      description:
        'Da qui accedi alla gestione catalog corsi, image library, diagram catalog. Le 3 card sotto ti portano alle pagine specifiche.',
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="admin-catalog-card"]',
    popover: {
      title: 'Catalogo corsi',
      description:
        'Approva/revoca i tipi corso disponibili. Senza approval esplicita, un course_type NON è generabile via wizard.',
      side: 'right',
      align: 'center',
    },
  },
  {
    element: '[data-tour="admin-images-card"]',
    popover: {
      title: 'Image library',
      description:
        'Carica/audit le immagini disponibili per le slide. Le immagini con license curata (CC-BY, CC0, ISO 7010) sono preferite dal motore di ricerca.',
      side: 'top',
      align: 'center',
    },
  },
]

export function startAdminTour(): Driver {
  const tour = buildTour('admin', steps)
  tour.drive()
  return tour
}
