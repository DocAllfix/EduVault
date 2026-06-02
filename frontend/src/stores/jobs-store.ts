/**
 * F11 (2026-06-02) — Active jobs store (Zustand + localStorage persistence).
 *
 * ─── Design intent ────────────────────────────────────────────────────────
 * Centralizza i "lavori in corso" per il corso (generation pipeline,
 * rebuild full, audio rebuild) in modo che siano visibili cross-page
 * (Dashboard, Catalogo, Course Studio, ecc.).
 *
 * Pattern di consumo:
 *  - addJob() → al click su "Rigenera"/"Genera audio"/wizard submit
 *  - useJobsWatcher (vedi hook dedicato) → poll periodico in background
 *    su `GET /api/jobs/{id}/progress` (se ho jobId) o `GET /api/courses/{id}`
 *    (fallback) e aggiorna `last_progress`. Quando job termina, lancia
 *    toast.success + notifica push browser (opt-in) + rimuove dallo store.
 *  - JobsBadge in sidebar → indicatore visivo persistente (spinner + count)
 *
 * Persistence: localStorage cosi` jobs sopravvivono a F5/cambio tab.
 * Quando l'utente torna, lo store ha gli stessi job + il watcher riparte.
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export type JobKind = 'generation' | 'rebuild' | 'audio_rebuild'

export interface ActiveJob {
  /** UUID del corso a cui il job è legato (per navigate). */
  courseId: string
  /** Titolo del corso, per i toast/notifiche. */
  courseTitle: string
  /** Tipo di job (per testo notifiche differente). */
  kind: JobKind
  /**
   * UUID del generation_job (se disponibile). Solo `kind='generation'`
   * lo riceve dal wizard. Rebuild/audio_rebuild non hanno un job_id
   * dedicato — il watcher cade su `getCourse()` per loro.
   */
  jobId?: string
  /** Epoch ms — usato per timeout dei watcher (auto-fail dopo 20 min). */
  startedAt: number
  /** Ultimo % progress (0-100), aggiornato dal watcher. */
  progressPercent?: number | null
  /** Ultimo step testuale (es. "Generazione contenuti"). */
  currentStep?: string | null
}

interface JobsStore {
  jobs: ActiveJob[]
  addJob: (job: Omit<ActiveJob, 'startedAt'>) => void
  updateJob: (
    courseId: string,
    kind: JobKind,
    patch: Partial<ActiveJob>,
  ) => void
  removeJob: (courseId: string, kind: JobKind) => void
  /** Util: trova un job specifico (courseId + kind). */
  getJob: (courseId: string, kind: JobKind) => ActiveJob | undefined
}

export const useJobsStore = create<JobsStore>()(
  persist(
    (set, get) => ({
      jobs: [],
      addJob: (job) =>
        set((state) => {
          // Dedup: se esiste gia` lo stesso (courseId+kind), aggiorna
          // startedAt invece di duplicare.
          const existing = state.jobs.find(
            (j) => j.courseId === job.courseId && j.kind === job.kind,
          )
          if (existing) {
            return {
              jobs: state.jobs.map((j) =>
                j === existing ? { ...j, ...job, startedAt: Date.now() } : j,
              ),
            }
          }
          return {
            jobs: [...state.jobs, { ...job, startedAt: Date.now() }],
          }
        }),
      updateJob: (courseId, kind, patch) =>
        set((state) => ({
          jobs: state.jobs.map((j) =>
            j.courseId === courseId && j.kind === kind ? { ...j, ...patch } : j,
          ),
        })),
      removeJob: (courseId, kind) =>
        set((state) => ({
          jobs: state.jobs.filter(
            (j) => !(j.courseId === courseId && j.kind === kind),
          ),
        })),
      getJob: (courseId, kind) =>
        get().jobs.find((j) => j.courseId === courseId && j.kind === kind),
    }),
    {
      name: 'eduvault-active-jobs',
      storage: createJSONStorage(() => localStorage),
      // Migrazione safe: se uno schema futuro cambia, droppa jobs vecchi.
      version: 1,
    },
  ),
)

/** Helper: testi UI coerenti per kind. */
export function jobKindLabel(kind: JobKind): string {
  switch (kind) {
    case 'generation':
      return 'Generazione'
    case 'rebuild':
      return 'Rigenerazione'
    case 'audio_rebuild':
      return 'Generazione audio'
  }
}

export function jobKindCompletedLabel(kind: JobKind): string {
  switch (kind) {
    case 'generation':
      return 'generato'
    case 'rebuild':
      return 'rigenerato'
    case 'audio_rebuild':
      return 'audio pronto'
  }
}
