/** F10 Courses Wizard tour — 4 step (step wizard sono già evidenti, tour breve). */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="wizard-stepper"]',
    popover: {
      title: 'Wizard 6 step',
      description:
        'Crea un corso in 6 passi: tipo, durata, normative, branding, anteprima skeleton, conferma. Puoi tornare indietro per modificare.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="wizard-course-type"]',
    popover: {
      title: 'Tipo di corso',
      description:
        'Scegli dal catalog approvato dei tipi di corso (es. Antincendio L1, Primo Soccorso B/C, RLS). Solo i catalog approvati sono disponibili.',
      side: 'right',
      align: 'start',
    },
  },
  {
    element: '[data-tour="wizard-summary"]',
    popover: {
      title: 'Anteprima e conferma',
      description:
        'Prima di lanciare la generazione vedrai un riepilogo della struttura attesa. La pipeline genera prima lo skeleton (per revisione), poi le slide.',
      side: 'top',
      align: 'center',
    },
  },
  {
    element: '[data-tour="wizard-submit"]',
    popover: {
      title: 'Avvia generazione',
      description:
        'Il sistema avvia la pipeline: research (recupero chunk normativi) → skeleton → content (slide) → audio. Sarai redirezzato alla pagina di progresso.',
      side: 'left',
      align: 'end',
    },
  },
]

export function startWizardTour(): Driver {
  const tour = buildTour('courses-wizard', steps)
  tour.drive()
  return tour
}
