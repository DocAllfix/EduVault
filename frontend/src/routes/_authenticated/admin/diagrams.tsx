/**
 * Route /admin/diagrams — Step C diagrams catalog viewer (2026-05-31).
 */
import { createFileRoute } from '@tanstack/react-router'
import { DiagramsCatalogAdmin } from '@/features/admin/diagrams'

export const Route = createFileRoute('/_authenticated/admin/diagrams')({
  component: DiagramsCatalogAdmin,
})
