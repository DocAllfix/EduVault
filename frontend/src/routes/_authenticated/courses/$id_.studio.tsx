/**
 * Route /courses/$id/studio — Course Studio (FASE 8 vast-hopping-sketch).
 *
 * Sibling di $id (convenzione $id_.studio) → URL /courses/{id}/studio.
 */

import { createFileRoute } from '@tanstack/react-router'
import { CourseStudio } from '@/features/course-studio'

export const Route = createFileRoute('/_authenticated/courses/$id_/studio')({
  component: CourseStudio,
})
