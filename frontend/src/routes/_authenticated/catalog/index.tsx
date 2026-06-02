/**
 * Route /catalog — Catalogo corsi pubblico (browse-only).
 *
 * F11 Issue 3 (D-229): permette agli operatori (non solo admin) di
 * sfogliare i tipi corso disponibili. Mostra solo entries APPROVATE.
 */

import { createFileRoute } from '@tanstack/react-router'
import { CatalogBrowse } from '@/features/catalog-browse'

export const Route = createFileRoute('/_authenticated/catalog/')({
  component: CatalogBrowse,
})
