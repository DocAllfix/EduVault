/** F10 Admin Images tour — 3 step. */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="images-summary"]',
    popover: {
      title: 'Stato library',
      description:
        'Totale immagini, breakdown per source (Wikimedia, ISO7010, manual_upload), top usage. Il motore di ricerca preferisce immagini library a Pexels/web.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="images-filters"]',
    popover: {
      title: 'Filtri source/license',
      description:
        'Filtra per source (provenienza) e license (CC-BY, CC0, Public Domain). Search cerca su tag.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="images-table"]',
    popover: {
      title: 'Grid immagini',
      description:
        'Thumbnail, tags, license e usage_count per ogni immagine. Hover mostra license chip. Bottone upload in alto per aggiungere manualmente.',
      side: 'top',
      align: 'center',
    },
  },
]

export function startAdminImagesTour(): Driver {
  const tour = buildTour('admin-images', steps)
  tour.drive()
  return tour
}
