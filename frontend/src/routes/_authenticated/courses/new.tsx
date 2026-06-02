/**
 * Route /courses/new — Course wizard (FASE 6.8).
 *
 * F11 Issue 3 (D-229): accetta query param opzionale `?course_type=<slug>`
 * per pre-selezionare il tipo allo step 1, usato quando l'utente arriva
 * dalla pagina /catalog cliccando "Crea corso da questo".
 */

import { createFileRoute } from '@tanstack/react-router'
import { CoursesWizard } from '@/features/courses-wizard'

interface NewCourseSearch {
  course_type?: string
}

export const Route = createFileRoute('/_authenticated/courses/new')({
  validateSearch: (search: Record<string, unknown>): NewCourseSearch => ({
    course_type:
      typeof search.course_type === 'string' ? search.course_type : undefined,
  }),
  component: CoursesWizard,
})
