/**
 * Route /courses/$id — Course Detail (FASE 6.9).
 */

import { createFileRoute } from '@tanstack/react-router'
import { CourseDetail } from '@/features/course-detail'

export const Route = createFileRoute('/_authenticated/courses/$id')({
  component: CourseDetail,
})
