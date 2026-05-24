/**
 * Route /regulations — Regulations knowledge base (FASE 6.9).
 */

import { createFileRoute } from '@tanstack/react-router'
import { Regulations } from '@/features/regulations'

export const Route = createFileRoute('/_authenticated/regulations/')({
  component: Regulations,
})
