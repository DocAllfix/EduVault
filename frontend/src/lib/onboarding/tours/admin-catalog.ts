/** F10 Admin Catalog tour — 4 step. */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="catalog-summary"]',
    popover: {
      title: 'Stato del catalog',
      description:
        'Totale catalog entries, approvati e pending. Solo gli approvati sono generabili dal wizard.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="catalog-filters"]',
    popover: {
      title: 'Filtri rapidi',
      description:
        'Filtra per target (lavoratori / preposti / RSPP / ecc.) o per stato approval. La ricerca cerca su slug e titolo.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="catalog-table"]',
    popover: {
      title: 'Tabella catalog',
      description:
        'Ogni riga ha checkbox per bulk approve, badge stato e bottoni Approva/Revoca. Clicca su una riga per vedere i moduli dettagliati.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="catalog-bulk-approve"]',
    popover: {
      title: 'Bulk approve',
      description:
        'Seleziona righe con checkbox e approva tutte insieme. Utile dopo una review di importazione catalog scrapata.',
      side: 'left',
      align: 'end',
    },
  },
]

export function startAdminCatalogTour(): Driver {
  const tour = buildTour('admin-catalog', steps)
  tour.drive()
  return tour
}
