/** F10 Admin Diagrams tour — 2 step. */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="diagrams-grid"]',
    popover: {
      title: 'Catalogo template diagram',
      description:
        '15 template SVG curati (flow, pyramid, fishbone, swimlane, ecc.). Ogni card mostra preview + slot disponibili + usage count nei corsi.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="diagrams-card"]',
    popover: {
      title: 'Dettagli template',
      description:
        'Hover su una card per vedere i nomi slot (label_1..label_N) e max_chars. Più slot = diagramma più complesso. Il motore sceglie il template più adatto via heuristic.',
      side: 'right',
      align: 'start',
    },
  },
]

export function startAdminDiagramsTour(): Driver {
  const tour = buildTour('admin-diagrams', steps)
  tour.drive()
  return tour
}
