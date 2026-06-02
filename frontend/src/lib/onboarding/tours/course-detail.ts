/** F10 Course Detail tour — 3 step. */

import type { Driver, DriveStep } from 'driver.js'
import { buildTour } from '../driver-config'

const steps: DriveStep[] = [
  {
    element: '[data-tour="course-detail-downloads"]',
    popover: {
      title: 'Scarica il corso',
      description:
        'PPTX, PDF dispensa, ZIP completo (slide + audio + immagini). I download richiedono che il corso sia in stato "completed".',
      side: 'bottom',
      align: 'start',
    },
  },
  {
    element: '[data-tour="course-detail-studio-button"]',
    popover: {
      title: 'Apri in Course Studio',
      description:
        'Course Studio ti permette di modificare slide, audio, immagini, rivedere problemi di qualità e rigenerare il corso.',
      side: 'bottom',
      align: 'end',
    },
  },
  {
    element: '[data-tour="course-detail-tabs"]',
    popover: {
      title: 'Storico generazione',
      description:
        'Vedi log della pipeline, citazioni normative, metriche per modulo. Utile per audit della qualità del corso.',
      side: 'top',
      align: 'center',
    },
  },
]

export function startCourseDetailTour(): Driver {
  const tour = buildTour('course-detail', steps)
  tour.drive()
  return tour
}
