/**
 * F10 Course Studio tour — 6 step (pagina più feature-densa):
 *  1. SlideRail accordion (sidebar moduli)
 *  2. Preview canvas centrale
 *  3. Right rail "CONTENUTO SLIDE"
 *  4. Right rail "STRUMENTI AI"
 *  5. TopBar — Rigenera + Download
 *  6. Quality badge + filtri
 */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="studio-sliderail"]',
    popover: {
      title: 'Naviga le slide per modulo',
      description:
        'I moduli del corso sono in accordion: aprine uno per vedere le sue slide. Clicca una slide per aprirla nel canvas centrale. Puoi anche trascinare le slide per riordinarle.',
      side: 'right',
      align: 'start',
    },
  },
  {
    element: '[data-tour="studio-canvas"]',
    popover: {
      title: 'Anteprima fedele PPTX',
      description:
        'Vedi esattamente come saranno le slide scaricabili: testo, immagini, diagrammi e quiz. L\'anteprima è renderizzata nel browser dal PPTX reale, non da una preview testuale.',
      side: 'bottom',
      align: 'center',
    },
  },
  {
    element: '[data-tour="studio-editor"]',
    popover: {
      title: 'Modifica contenuto slide',
      description:
        'Edita titolo, bullets, note relatore e riferimento normativo. Le modifiche vengono salvate in DB; per vedere il PPTX aggiornato premi "Rigenera" in alto.',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: '[data-tour="studio-ai-tools"]',
    popover: {
      title: 'Strumenti AI',
      description:
        'Qualità: segnala slide problematiche (image_placeholder, quiz_no_options, ecc.). Chat AI: chiedi all\'AI di riformulare bullets, espandere note o trasformare in quiz.',
      side: 'left',
      align: 'start',
    },
  },
  {
    element: '[data-tour="studio-rigenera"]',
    popover: {
      title: 'Rigenera + Scarica',
      description:
        '"Rigenera" ricostruisce PPTX/PDF/Audio dalle modifiche correnti. Quando il corso è completato puoi scaricarlo dal pulsante a fianco (PPTX, PDF dispensa, ZIP con audio).',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    element: '[data-tour="studio-quality-badge"]',
    popover: {
      title: 'Filtra slide problematiche',
      description:
        'Il badge rosso conta le slide con almeno un problema. Clicca per filtrare la sidebar e vedere solo quelle.',
      side: 'bottom',
      align: 'end',
    },
  },
]

export function startCourseStudioTour(): Driver {
  const tour = buildTour('course-studio', steps)
  tour.drive()
  return tour
}
