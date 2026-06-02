/**
 * F10 Skeleton Review tour — 4 step:
 *  1. moduli + voci skeleton
 *  2. edit inline voce (sub_topic + retrieval_query)
 *  3. F3.AI actions per voce (Rephrase / Operational / Alternatives)
 *  4. bottone "Approva struttura" — fire content phase
 */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="skeleton-modules"]',
    popover: {
      title: 'Struttura proposta dall’AI',
      description:
        'Ogni modulo ha 6-10 sotto-temi (voci skeleton) generati dall\'AI dal corpus normativo. Puoi rivedere, modificare, riordinare prima della generazione finale.',
      side: 'right',
      align: 'start',
    },
  },
  {
    element: '[data-tour="skeleton-voice-edit"]',
    popover: {
      title: 'Modifica una voce',
      description:
        'Cambia il sub_topic (cosa tratta la voce) e la retrieval_query (cosa cercare nel corpus). Usa ↑/↓ per riordinare, ❌ per rimuovere (min 6 voci).',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: '[data-tour="skeleton-ai-actions"]',
    popover: {
      title: 'Azioni AI per voce',
      description:
        'Rephrase: riformula la voce. Operativo: trasforma in azione concreta. Alternative: 3 varianti per sostituirla. "Chiedi all\'AI" sopra il modulo permette edit free-text di tutte le voci insieme.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="skeleton-approve"]',
    popover: {
      title: 'Approva e genera',
      description:
        'Una volta confermata la struttura, "Approva struttura" avvia la fase content (generazione slide + audio + immagini). Da qui non si torna indietro: rivedi bene prima di confermare.',
      side: 'bottom',
      align: 'end',
    },
  },
]

export function startSkeletonReviewTour(): Driver {
  const tour = buildTour('skeleton-review', steps)
  tour.drive()
  return tour
}
