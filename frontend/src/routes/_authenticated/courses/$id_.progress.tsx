/**
 * Route /courses/$id/progress — Progress Monitor (FASE 6.9).
 *
 * Note: TanStack Router uses `$id_.progress` filename convention for a
 * route that is a sibling of `$id` rather than a child (avoids the
 * layout nesting). The URL is `/courses/{id}/progress`.
 */

import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { CourseProgress } from '@/features/course-progress'

const progressSearchSchema = z.object({
  job: z.string().optional().catch(undefined),
})

export const Route = createFileRoute('/_authenticated/courses/$id_/progress')({
  validateSearch: progressSearchSchema,
  component: CourseProgress,
})
