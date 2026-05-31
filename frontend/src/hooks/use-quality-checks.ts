/**
 * F4 D9 — useQualityChecks hook (analista sign-off 2026-05-31)
 *
 * TanStack Query wrapper su GET /api/courses/{id}/quality-issues.
 *
 * Strategia caching:
 *   - staleTime: 30s (cliente edita slide → quality cambia, invalida a edit)
 *   - refetchOnWindowFocus: true (cliente riapre browser → fresh check)
 *   - Polling NO (compute on-the-fly server-side, evita carico inutile)
 *
 * Invalidate via queryClient.invalidateQueries({queryKey: ['quality-issues', id]})
 * dopo edit slide (patch_slide) o rigenera (regenerate_slide) o rebuild_course.
 */

import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'

import { api, type QualityIssue, type QualityIssuesResponse } from '@/lib/api'

export function useQualityChecks(
  courseId: string,
  enabled: boolean = true,
): UseQueryResult<QualityIssuesResponse> {
  return useQuery({
    queryKey: ['quality-issues', courseId] as const,
    queryFn: () => api.getQualityIssues(courseId),
    enabled,
    staleTime: 30_000, // 30s
    refetchOnWindowFocus: true,
  })
}

/**
 * Helper: invalida cache quality dopo edit/rigenera/rebuild.
 * Usage: const inv = useInvalidateQualityChecks(courseId); inv()
 */
export function useInvalidateQualityChecks(courseId: string): () => void {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['quality-issues', courseId] })
  }
}

/**
 * Helper: estrae issues per una specifica slide (badge sidebar lookup).
 */
export function getSlideIssues(
  data: QualityIssuesResponse | undefined,
  slideIndex: number,
): QualityIssue[] {
  if (!data?.issues) return []
  return data.issues.filter((iss) => iss.slide_index === slideIndex)
}

/**
 * Helper: severita` massima per una specifica slide ('error' | 'warning' | 'info' | null).
 * Usato per colore badge (rosso/arancione/blu).
 */
export function getSlideMaxSeverity(
  data: QualityIssuesResponse | undefined,
  slideIndex: number,
): 'error' | 'warning' | 'info' | null {
  const issues = getSlideIssues(data, slideIndex)
  if (issues.length === 0) return null
  if (issues.some((i) => i.severity === 'error')) return 'error'
  if (issues.some((i) => i.severity === 'warning')) return 'warning'
  return 'info'
}
