/**
 * Phase machine for the Progress Monitor.
 *
 * Maps the backend `generation_jobs.status` + `current_step` signals
 * (BP §08.8 / app/services/generation_service.py + production_builder.py)
 * to the 5 user-visible phases asked by the prompt.
 *
 * Backend status sequence:
 *   queued → research → content → building → completed | failed | cancelled
 *
 * `current_step` is emitted only during the build phase by
 * ProductionBuilder.build():
 *   87 "Generazione PPTX..."           → composition phase
 *   92 "Validazione PPTX..."           → composition phase
 *   95 "Generazione PDF dispensa..."   → pdf phase
 *   96 "Generazione narrazione audio..." → audio phase
 *
 * Outside build (queued/research/content), `current_step` is NULL — we
 * derive the phase from `status` alone.
 */

import { FileSearch, FileText, Headphones, Presentation, Sparkles } from 'lucide-react'
import type { JobProgress, JobStatus } from '@/lib/ws'

export type PhaseKey = 'research' | 'content' | 'compose' | 'pdf' | 'audio'

export type PhaseSpec = {
  key: PhaseKey
  label: string
  icon: React.ComponentType<{ className?: string }>
  /** Percent range owned by this phase on the global 0-100 bar. */
  range: [number, number]
}

// Five named phases in the order the user will see them.
export const PHASES: PhaseSpec[] = [
  { key: 'research', label: 'Ricerca normativa', icon: FileSearch, range: [0, 40] },
  { key: 'content', label: 'Generazione contenuti', icon: Sparkles, range: [40, 86] },
  { key: 'compose', label: 'Composizione PPTX', icon: Presentation, range: [86, 94] },
  { key: 'pdf', label: 'Generazione PDF', icon: FileText, range: [94, 96] },
  { key: 'audio', label: 'Narrazione audio', icon: Headphones, range: [96, 100] },
]

/**
 * Derive which phase is currently active from a `JobProgress` frame.
 * Returns the phase index (0-4) or -1 if the job is terminal.
 */
export function deriveCurrentPhase(p: JobProgress | null): number {
  if (!p) return 0
  // Terminal states: nothing is "current" anymore.
  if (p.status === 'completed' || p.status === 'failed' || p.status === 'cancelled') {
    return -1
  }
  // Status-driven phases (queued/research/content/building).
  const s: JobStatus = p.status
  if (s === 'queued' || s === 'research') return 0
  if (s === 'content') return 1
  if (s === 'building') {
    // Within build, current_step text is the finer-grained signal.
    const step = (p.current_step ?? '').toLowerCase()
    if (step.includes('narrazione')) return 4
    if (step.includes('pdf')) return 3
    // Default during build = composition (covers PPTX gen + validation).
    return 2
  }
  // Unknown status (e.g. archived from polling fallback) — keep first phase.
  return 0
}

/**
 * Did this phase complete? True when the current job phase index is
 * greater than this phase's index, OR when the job reached 'completed'
 * status.
 */
export function isPhaseDone(
  phaseIdx: number,
  current: number,
  p: JobProgress | null,
): boolean {
  if (p?.status === 'completed') return true
  if (current === -1) return false
  return phaseIdx < current
}
