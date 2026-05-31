/**
 * Nexus EduVault — WebSocket client for job progress (BP §08.8).
 *
 * Channel cascade (see `docs/POLLING_FALLBACK.md`):
 *
 *   1. WebSocket primary — `wss://<host>/ws/jobs/{job_id}?token=<jwt>`
 *      Server streams `JobProgress` JSON once per second.
 *      Closes naturally when `status ∈ TERMINAL_STATES`.
 *
 *   2. Polling REST fallback — `GET /api/courses/{course_id}` every 30s
 *      Activated automatically when the WS fails to open or closes with
 *      an error code (excluding clean closures and auth/ownership codes
 *      4001/4003/4004 which mean retrying is pointless).
 *
 * The polled REST endpoint (`/api/courses/{id}`) doesn't expose job-level
 * fields directly — we map `CourseDetail.status` to a JobProgress shape so
 * callers see one unified type regardless of which channel fired.
 *
 * REI-13: WS URL is derived from `VITE_API_URL` (http→ws, https→wss).
 * No hardcoded host.
 */

import { api, API_BASE, type CourseDetail } from './api'

// ─────────────────────────── Types ─────────────────────────────────────

/**
 * Server-emitted progress frame (BP §08.8 / `app/api/websocket.py`).
 * Matches the SELECT in `get_job_progress()`. All fields except `status`
 * can be null because the row is INSERTed with just status='queued'.
 */
export interface JobProgress {
  status: JobStatus
  progress_percent?: number | null
  current_step?: string | null
  error_message?: string | null
}

/**
 * Job lifecycle states. `TERMINAL_STATES` below is the canonical set —
 * mirror of `frozenset` in `app/api/websocket.py`. Keep in sync.
 */
export type JobStatus =
  | 'queued'
  | 'research'
  | 'skeleton_pending'   // research done, waiting for user approval (D3 D-186)
  | 'content'
  | 'building'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'not_found'
  // Frontend-only: emitted when the polling layer maps a course status
  // (`archived`) that doesn't exist on the job side.
  | 'archived'

export const TERMINAL_STATES: ReadonlySet<JobStatus> = new Set<JobStatus>([
  'completed',
  'failed',
  'cancelled',
  'archived',
  // skeleton_pending: terminal from the JOB perspective (user must approve);
  // CourseProgress UI shows a "Revisiona scheletro" CTA instead of spinner.
  'skeleton_pending',
])

/** Reasons we exposed why a watcher closed. Useful for UI debugging. */
export type WatchCloseReason =
  | 'terminal' // status reached a TERMINAL_STATES value
  | 'unauthorized' // ws code 4001 (invalid/expired token) — no point retrying
  | 'forbidden' // ws code 4003 (ownership denied)
  | 'not_found' // ws code 4004 (job id unknown)
  | 'user_aborted' // caller invoked the returned `close()` handle
  | 'fallback_failed' // both WS and polling gave up

export interface WatchJobOptions {
  /** Called for every progress frame (both WS and polling). */
  onProgress: (p: JobProgress) => void
  /** Called once when status reaches a terminal value. */
  onComplete?: (p: JobProgress) => void
  /** Called for unrecoverable failures (auth, network, etc.). */
  onError?: (err: WatchJobError) => void
  /**
   * Course id is required for the polling fallback (`GET
   * /api/courses/{id}`). The WS path uses `jobId`; if you genuinely don't
   * have a `courseId` (rare) pass undefined and the fallback is disabled.
   */
  courseId?: string
  /** Override JWT used in the WS query string. Default: localStorage access token. */
  token?: string
  /** Polling interval in ms. Default 30000 (BP §10.3, see POLLING_FALLBACK.md). */
  pollIntervalMs?: number
  /**
   * Max WS reconnect attempts before switching to polling. Default 2.
   * Each attempt waits `2^n × 1000` ms (1s, 2s).
   */
  maxWsReconnects?: number
}

export class WatchJobError extends Error {
  reason: WatchCloseReason
  cause?: unknown

  constructor(reason: WatchCloseReason, message: string, cause?: unknown) {
    super(message)
    this.name = 'WatchJobError'
    this.reason = reason
    this.cause = cause
  }
}

/** Handle returned by `connectToJob`. Call `.close()` to stop watching. */
export interface WatchHandle {
  close: () => void
  /** Last frame seen — useful for UI initialization after reconnect. */
  getLastProgress: () => JobProgress | null
}

// ─────────────────────────── URL helpers ───────────────────────────────

function buildWsUrl(jobId: string, token: string): string {
  // Map http(s) → ws(s) preserving host:port.
  const wsBase = API_BASE.replace(/^http(s?):\/\//, (_m, s) => `ws${s}://`)
  // jobId is a UUID — encodeURIComponent is defensive but cheap.
  return `${wsBase}/ws/jobs/${encodeURIComponent(jobId)}?token=${encodeURIComponent(token)}`
}

/**
 * Map a `CourseDetail.status` (`generating | completed | failed | archived
 * | certified`) onto a `JobProgress` so polling and WS share a callback
 * signature. The mapping is intentionally lossy:
 *   - `generating` → `building` (the closest non-terminal job state)
 *   - `certified` → `completed` (downstream of the job)
 *   - `archived`  → `archived` (terminal, ends polling)
 * Callers needing finer granularity should switch to WS while the job is
 * still in `_ACTIVE_JOB_STATES` and fall back to polling only after.
 */
function courseStatusToJobProgress(course: CourseDetail): JobProgress {
  const cs = course.status
  let status: JobStatus
  switch (cs) {
    case 'completed':
    case 'certified':
      status = 'completed'
      break
    case 'failed':
      status = 'failed'
      break
    case 'archived':
      status = 'archived'
      break
    case 'skeleton_pending':
      // Research done, awaiting human approval (D3 D-186). Terminal from
      // the job perspective: the polling layer can stop and the UI will
      // surface a "Revisiona scheletro" CTA.
      status = 'skeleton_pending'
      break
    case 'generating':
    default:
      status = 'building'
      break
  }
  return { status, progress_percent: null, current_step: null, error_message: null }
}

// ─────────────────────────── Polling fallback ──────────────────────────

interface PollingState {
  timer: number | null
  cancelled: boolean
}

function startPolling(
  courseId: string,
  intervalMs: number,
  onProgress: (p: JobProgress) => void,
  onComplete: ((p: JobProgress) => void) | undefined,
  onError: ((err: WatchJobError) => void) | undefined,
  setLast: (p: JobProgress) => void,
): PollingState {
  const state: PollingState = { timer: null, cancelled: false }

  const tick = async () => {
    if (state.cancelled) return
    try {
      const course = await api.getCourse(courseId)
      if (state.cancelled) return
      const frame = courseStatusToJobProgress(course)
      setLast(frame)
      onProgress(frame)
      if (TERMINAL_STATES.has(frame.status)) {
        onComplete?.(frame)
        return // stop scheduling
      }
    } catch (err) {
      if (state.cancelled) return
      // Single network blip → log via onError but keep polling. Hard
      // give-up only if /api/courses/{id} returns 404 (course gone) or
      // 403 (ownership lost) — both terminal from the watcher's view.
      const apiErr = err as { status?: number; message?: string }
      if (apiErr.status === 404 || apiErr.status === 403) {
        onError?.(
          new WatchJobError(
            apiErr.status === 404 ? 'not_found' : 'forbidden',
            apiErr.message ?? 'Polling stopped',
            err,
          ),
        )
        return
      }
      // Transient → just keep going.
    }
    state.timer = window.setTimeout(tick, intervalMs)
  }

  // First poll runs immediately so UIs get a frame within < intervalMs.
  state.timer = window.setTimeout(tick, 0)
  return state
}

function stopPolling(state: PollingState | null): void {
  if (!state) return
  state.cancelled = true
  if (state.timer !== null) {
    window.clearTimeout(state.timer)
    state.timer = null
  }
}

// ─────────────────────────── Public API ────────────────────────────────

/**
 * Connect to a generation job's progress stream.
 *
 * Behaviour:
 *   - Opens WS to `/ws/jobs/{jobId}?token=...`.
 *   - On any incoming message → `onProgress`.
 *   - On terminal status → `onComplete` + clean close.
 *   - On 4001/4003/4004 close → `onError` (retrying won't help).
 *   - On any other close/error → retry up to `maxWsReconnects` with
 *     exponential backoff, then switch to polling fallback.
 *
 * Returns a `WatchHandle`; call `.close()` to stop the watcher (cancels
 * both WS and polling). Idempotent.
 */
export function connectToJob(jobId: string, opts: WatchJobOptions): WatchHandle {
  const token =
    opts.token ??
    (typeof window !== 'undefined'
      ? window.localStorage.getItem('nexus.accessToken')
      : null)
  const pollIntervalMs = opts.pollIntervalMs ?? 30_000
  const maxReconnects = opts.maxWsReconnects ?? 2

  let lastProgress: JobProgress | null = null
  let ws: WebSocket | null = null
  let polling: PollingState | null = null
  let attempt = 0
  let userClosed = false

  const setLast = (p: JobProgress) => {
    lastProgress = p
  }

  const cleanup = (): void => {
    if (ws) {
      try {
        ws.close()
      } catch {
        /* ignore */
      }
      ws = null
    }
    stopPolling(polling)
    polling = null
  }

  const switchToPolling = (): void => {
    cleanup()
    if (userClosed) return
    if (!opts.courseId) {
      opts.onError?.(
        new WatchJobError(
          'fallback_failed',
          'WS unavailable and no courseId provided for polling fallback',
        ),
      )
      return
    }
    polling = startPolling(
      opts.courseId,
      pollIntervalMs,
      opts.onProgress,
      opts.onComplete,
      opts.onError,
      setLast,
    )
  }

  const openWs = (): void => {
    if (userClosed) return
    if (!token) {
      // No auth token → WS will close 4001 immediately. Skip the round-
      // trip and go straight to polling (which uses Bearer header — same
      // failure mode but produces a clearer 401 message).
      switchToPolling()
      return
    }
    try {
      ws = new WebSocket(buildWsUrl(jobId, token))
    } catch (err) {
      // Constructor only throws on malformed URL — unrecoverable.
      opts.onError?.(
        new WatchJobError('fallback_failed', 'WebSocket constructor failed', err),
      )
      return
    }

    ws.onmessage = (ev: MessageEvent) => {
      try {
        const frame = JSON.parse(String(ev.data)) as JobProgress
        setLast(frame)
        opts.onProgress(frame)
        if (TERMINAL_STATES.has(frame.status)) {
          opts.onComplete?.(frame)
          // Server will close on its own; we don't await it.
        }
      } catch (err) {
        // Bad frame — log but stay connected (server might send another).
        opts.onError?.(
          new WatchJobError('fallback_failed', 'Malformed WS frame', err),
        )
      }
    }

    ws.onerror = () => {
      // `onerror` fires before `onclose` — we let `onclose` handle the
      // reconnect decision (it has the close code).
    }

    ws.onclose = (ev: CloseEvent) => {
      if (userClosed) return
      ws = null

      // Auth/ownership close codes — retrying is pointless.
      if (ev.code === 4001) {
        opts.onError?.(
          new WatchJobError('unauthorized', ev.reason || 'Invalid or expired token'),
        )
        return
      }
      if (ev.code === 4003) {
        opts.onError?.(
          new WatchJobError('forbidden', ev.reason || 'Ownership denied'),
        )
        return
      }
      if (ev.code === 4004) {
        opts.onError?.(
          new WatchJobError('not_found', ev.reason || 'Job not found'),
        )
        return
      }

      // Clean closures (1000 = normal, 1001 = going away) AFTER we saw a
      // terminal status → we're done.
      if (
        (ev.code === 1000 || ev.code === 1001) &&
        lastProgress &&
        TERMINAL_STATES.has(lastProgress.status)
      ) {
        return
      }

      // Otherwise: transient. Retry with backoff, then polling.
      attempt += 1
      if (attempt <= maxReconnects) {
        const delay = 2 ** (attempt - 1) * 1000 // 1s, 2s, 4s, ...
        window.setTimeout(openWs, delay)
      } else {
        switchToPolling()
      }
    }
  }

  openWs()

  return {
    close: () => {
      userClosed = true
      cleanup()
    },
    getLastProgress: () => lastProgress,
  }
}

// Convenience re-export for callers who only need the WS module.
export { API_BASE } from './api'
