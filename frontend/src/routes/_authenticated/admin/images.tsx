/**
 * Route /admin/images — Step B image library upload+audit (2026-05-31).
 */
import { createFileRoute } from '@tanstack/react-router'
import { ImageLibraryAdmin } from '@/features/admin/images'

export const Route = createFileRoute('/_authenticated/admin/images')({
  component: ImageLibraryAdmin,
})
