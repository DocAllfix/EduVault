/**
 * Route /courses/studio — Course Studio entry point.
 *
 * No actual course in the URL: shows a landing card explaining what
 * Course Studio is + auto-opens the picker dialog so the operator
 * jumps straight into "scegli il corso".
 */

import { createFileRoute } from '@tanstack/react-router'
import { CourseStudioEntry } from '@/features/course-studio/entry'

export const Route = createFileRoute('/_authenticated/courses/studio')({
  component: CourseStudioEntry,
})
