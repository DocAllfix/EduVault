/**
 * F10 Dashboard tour — 4 step:
 *  1. cards metriche
 *  2. tabella corsi recenti
 *  3. CTA "Nuovo corso"
 *  4. sidebar navigazione
 *
 * Note: i selettori CSS sono il contratto fragile col DOM. Marker preferiti:
 * `data-tour="..."` attribute che potremmo aggiungere agli elementi target
 * della dashboard in un commit successivo (Step 9 polish). Per ora cerco
 * elementi gia` esistenti (header h1, primo pulsante CTA, sidebar).
 */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="dashboard-stats"]',
    popover: {
      title: 'Le metriche del progetto',
      description:
        'Qui vedi a colpo d’occhio quanti corsi e normative hai in piattaforma, le ore totali di formazione generate e i corsi con modifiche pendenti.',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="dashboard-recent-courses"]',
    popover: {
      title: 'Corsi recenti',
      description:
        'Gli ultimi 5 corsi generati. Clicca una riga per aprire il dettaglio del corso e scaricare PPTX/PDF/Audio.',
      side: 'top',
      align: 'start',
    },
  },
  {
    element: '[data-tour="dashboard-new-course"]',
    popover: {
      title: 'Crea un nuovo corso',
      description:
        'Avvia il wizard di generazione: scegli tipo di corso, durata, normative di riferimento. Il sistema produce skeleton, slide, audio e PDF dispensa.',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    element: '[data-tour="app-sidebar"]',
    popover: {
      title: 'Navigazione laterale',
      description:
        'Da qui accedi a Corsi, Normative e (se sei admin) al pannello amministrazione. Puoi collassare la sidebar dal trigger in alto a sinistra.',
      side: 'right',
      align: 'start',
    },
  },
]

export function startDashboardTour(): Driver {
  const tour = buildTour('dashboard', steps)
  tour.drive()
  return tour
}
