/**
 * Route /courses/new — Course wizard (FASE 6.8).
 */

import { createFileRoute } from '@tanstack/react-router'
import { CoursesWizard } from '@/features/courses-wizard'

export const Route = createFileRoute('/_authenticated/courses/new')({
  component: CoursesWizard,
})
