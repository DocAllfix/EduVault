/**
 * F11 (2026-06-02) — Global jobs watcher hook.
 *
 * Montato una sola volta nel `__root.tsx`. Ogni 4s itera i job attivi
 * nello store e ne aggiorna lo stato via REST. Quando un job termina:
 *  - rimuove dallo store
 *  - lancia toast.success cliccabile → naviga a /courses/{id}/studio
 *  - (best-effort) notifica push browser nativa per backup cross-tab
 *
 * Architettura semplice: setInterval globale + Promise.all sui job.
 * Non usa TanStack Query perche` lo store sopravvive cross-route e il
 * lifecycle del QueryClient ci complicherebbe la persistenza.
 *
 * Failure modes gestiti:
 *  - Network blip: log + retry al prossimo tick (no rimozione)
 *  - 403/404 sul job: rimuovi dallo store (corso archiviato/cancellato)
 *  - Timeout 20 min: rimuovi + toast.warning ("Operazione troppo lunga,
 *    controlla manualmente"). Evita job orfani che pollano per sempre.
 *
 * Notifica browser: requestPermission UNA volta al primo addJob via
 * registerNotificationPermissionPrompt (non bloccante). Se utente
 * rifiuta, si ricade sul solo toast in-app.
 */

import { useEffect, useRef } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import {
  useJobsStore,
  jobKindLabel,
  jobKindCompletedLabel,
  type ActiveJob,
} from '@/stores/jobs-store'

const POLL_INTERVAL_MS = 4_000
const MAX_JOB_AGE_MS = 20 * 60 * 1000 // 20 min — soft timeout safety net

/**
 * Decide se un job è terminato in base ai dati ricevuti dal REST.
 *  - generation: status terminal nel job_progress
 *  - rebuild: status del corso torna a 'completed' dopo essere stato 'generating'
 *  - audio_rebuild: audio_manifest_path popolato sul corso
 */
type WatcherProbeResult =
  | { kind: 'still_running'; progress?: number | null; step?: string | null }
  | { kind: 'completed' }
  | { kind: 'failed'; error?: string | null }
  | { kind: 'gone' } // 404/403 → rimuovi e basta

async function probeJob(job: ActiveJob): Promise<WatcherProbeResult> {
  try {
    if (job.kind === 'generation' && job.jobId) {
      const j = await api.getJobProgress(job.jobId)
      if (j.status === 'completed') return { kind: 'completed' }
      if (j.status === 'failed' || j.status === 'cancelled')
        return { kind: 'failed', error: j.error_message ?? null }
      return {
        kind: 'still_running',
        progress: j.progress_percent ?? null,
        step: j.current_step ?? null,
      }
    }
    // rebuild / audio_rebuild / generation senza jobId → fallback su getCourse
    const c = await api.getCourse(job.courseId)
    if (job.kind === 'audio_rebuild') {
      // Pronto quando audio_manifest_path è popolato
      if (c.audio_manifest_path) return { kind: 'completed' }
      return { kind: 'still_running' }
    }
    // generation senza jobId + rebuild → guardiamo status
    if (c.status === 'completed' || c.status === 'certified')
      return { kind: 'completed' }
    if (c.status === 'failed') return { kind: 'failed' }
    return { kind: 'still_running' }
  } catch (err) {
    const apiErr = err as { status?: number }
    if (apiErr.status === 403 || apiErr.status === 404) {
      return { kind: 'gone' }
    }
    // Network blip → still_running (retry al prossimo tick)
    return { kind: 'still_running' }
  }
}

/**
 * Best-effort notifica push del sistema (cross-tab).
 * Silenzioso se permission non concesso o se browser non supporta.
 */
function tryNativeNotify(title: string, body: string, courseId: string): void {
  if (typeof window === 'undefined') return
  if (typeof Notification === 'undefined') return
  if (Notification.permission !== 'granted') return
  try {
    const n = new Notification(title, {
      body,
      icon: '/brand/favicon-180.png',
      tag: `eduvault-job-${courseId}`, // sostituisce notif vecchie per stesso corso
    })
    n.onclick = () => {
      window.focus()
      window.location.href = `/courses/${courseId}/studio`
      n.close()
    }
  } catch {
    // silently ignore (e.g. Notification permission revoked between checks)
  }
}

export function useJobsWatcher(): void {
  const jobs = useJobsStore((s) => s.jobs)
  const updateJob = useJobsStore((s) => s.updateJob)
  const removeJob = useJobsStore((s) => s.removeJob)
  const navigate = useNavigate()

  // Ref to current jobs to avoid re-running setInterval on every job change
  const jobsRef = useRef(jobs)
  jobsRef.current = jobs

  useEffect(() => {
    const tick = async () => {
      const current = jobsRef.current
      if (current.length === 0) return
      await Promise.all(
        current.map(async (job) => {
          // Timeout safety: se un job e` la' da >20min e ancora "running",
          // probabilmente è bloccato; lo rimuoviamo (l'utente può rilanciare).
          if (Date.now() - job.startedAt > MAX_JOB_AGE_MS) {
            removeJob(job.courseId, job.kind)
            toast.warning(
              `${jobKindLabel(job.kind)} di "${job.courseTitle}" non risponde da più di 20 minuti. Controlla manualmente la scheda corso.`,
              { duration: 8000 },
            )
            return
          }
          const result = await probeJob(job)
          if (result.kind === 'still_running') {
            updateJob(job.courseId, job.kind, {
              progressPercent: result.progress ?? job.progressPercent,
              currentStep: result.step ?? job.currentStep,
            })
            return
          }
          if (result.kind === 'gone') {
            removeJob(job.courseId, job.kind)
            return
          }
          // completed / failed → rimuovi + notifica
          removeJob(job.courseId, job.kind)
          if (result.kind === 'completed') {
            const title = `${job.courseTitle} — ${jobKindCompletedLabel(job.kind)}`
            const body = 'Tocca per aprire il Course Studio.'
            toast.success(title, {
              description: body,
              duration: 10000,
              action: {
                label: 'Apri Studio',
                onClick: () =>
                  navigate({
                    to: '/courses/$id/studio',
                    params: { id: job.courseId },
                  }),
              },
            })
            tryNativeNotify(title, body, job.courseId)
          } else {
            // failed
            toast.error(
              `${jobKindLabel(job.kind)} di "${job.courseTitle}" non riuscita.`,
              {
                description: result.error ?? 'Riprova dalla scheda del corso.',
                duration: 10000,
              },
            )
          }
        }),
      )
    }
    // First tick after a short delay (non bloccare il mount)
    const initial = window.setTimeout(tick, 1500)
    const id = window.setInterval(tick, POLL_INTERVAL_MS)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}

/**
 * Chiamare una volta quando l'utente fa un'azione che aggiunge un job
 * (es. click Rigenera/Genera audio). Non blocca: se l'utente rifiuta,
 * si ricade sul toast in-app.
 */
export function requestNotificationPermissionOnce(): void {
  if (typeof window === 'undefined') return
  if (typeof Notification === 'undefined') return
  if (Notification.permission === 'default') {
    try {
      void Notification.requestPermission()
    } catch {
      // safari < 16 throws; silently ignore
    }
  }
}
