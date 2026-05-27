/**
 * Static metadata for the Dashboard courses list.
 *
 * - `courseStatuses`: matches the runtime values written by the backend
 *   (`generation_service.py` + `certify_course` + soft-delete route).
 *   Source: `app/api/routes/courses.py` + `app/services/generation_service.py`.
 *   Five terminal-or-progress states user-visible:
 *      generating, completed, failed, archived, certified.
 *
 * - `courseTargets`: matches `TargetType` in `app/models/core.py`
 *   (`discente`, `formatore` — REI-5, no invention).
 *
 * `course_type` is intentionally NOT hardcoded here: it comes from the
 * dynamic COURSE_CATALOG (`api.getCatalog()`). The filter on type uses
 * free-text search instead of a faceted enum, until 6.8 (wizard) ships
 * a real catalog browser.
 */

import {
  CheckCircle2,
  Loader2,
  XCircle,
  Archive,
  ShieldCheck,
} from 'lucide-react'

export type CourseStatusValue =
  | 'generating'
  | 'completed'
  | 'certified'
  | 'failed'
  | 'archived'

export const courseStatuses: {
  value: CourseStatusValue
  label: string
  icon: React.ComponentType<{ className?: string }>
}[] = [
  { value: 'generating', label: 'In generazione', icon: Loader2 },
  { value: 'completed', label: 'Completato', icon: CheckCircle2 },
  { value: 'certified', label: 'Certificato', icon: ShieldCheck },
  { value: 'failed', label: 'Fallito', icon: XCircle },
  { value: 'archived', label: 'Archiviato', icon: Archive },
]

export type CourseTargetValue = 'discente' | 'formatore'

export const courseTargets: {
  value: CourseTargetValue
  label: string
}[] = [
  { value: 'discente', label: 'Discente' },
  { value: 'formatore', label: 'Formatore' },
]
