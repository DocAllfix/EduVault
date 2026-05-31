/**
 * Route /admin/catalog — F1 catalog review (D8 vast-hopping, 2026-05-31).
 */

import { createFileRoute } from '@tanstack/react-router'
import { CatalogReview } from '@/features/admin/catalog-review'

export const Route = createFileRoute('/_authenticated/admin/catalog')({
  component: CatalogReview,
})
