/**
 * Nexus EduVault — typed HTTP client (BLUEPRINT v7.0 §10).
 *
 * All endpoints documented in BP §10 are covered. Types come from
 * `types.gen.ts` which is auto-generated from `openapi.json` (FASE 6.4).
 *
 * Auth flow (BP §08):
 *   - `login()` stores access+refresh tokens in `localStorage`.
 *   - Every request injects `Authorization: Bearer <access>` if present.
 *   - On 401 we try `refresh()` once: success → replay the original request;
 *     failure → clear tokens + emit an `auth:logout` window event so the UI
 *     can redirect to /sign-in. We never retry-refresh in a loop.
 *
 * No third-party HTTP library: native `fetch`. The shadcn-admin template
 * already ships `axios`, but we keep the API surface narrow (REI-5: minimum
 * code) and dependency footprint thin — easier to audit, easier to swap.
 *
 * REI-13: base URL is read from `import.meta.env.VITE_API_URL` (default
 * `http://localhost:8000`). No domain is ever hardcoded.
 */

import type { components, paths } from './types.gen'

// ─────────────────────────── Type re-exports ───────────────────────────
//
// All response/request DTOs live in the generated schema. Re-exporting them
// from this module gives callers a single import surface:
//
//     import { api, type CourseRequest, type CourseSummary } from '@/lib/api'

export type CourseRequest = components['schemas']['CourseRequest']
export type CourseResponse = components['schemas']['CourseResponse']
export type CourseSummary = components['schemas']['CourseSummary']
export type CourseDetail = components['schemas']['CourseDetail']
export type CertifyResponse = components['schemas']['CertifyResponse']
export type LoginRequest = components['schemas']['LoginRequest']
export type LoginResponse = components['schemas']['LoginResponse']
export type RefreshRequest = components['schemas']['RefreshRequest']
export type RefreshResponse = components['schemas']['RefreshResponse']
export type UserMe = components['schemas']['UserMe']
export type RegulationSummary = components['schemas']['RegulationSummary']
export type ChunkSummary = components['schemas']['ChunkSummary']
export type UploadResponse = components['schemas']['UploadResponse']
export type BrandPresetSummary = components['schemas']['BrandPresetSummary']
export type MetricsResponse = components['schemas']['MetricsResponse']
export type DashboardStats = components['schemas']['DashboardStats']

/**
 * Download formats accepted by `GET /api/courses/{id}/download/{fmt}`.
 * Matches `_DOWNLOAD_FORMATS` in `app/api/routes/courses.py`.
 */
export type DownloadFormat = 'pptx' | 'pdf' | 'zip' | 'audio'

/**
 * COURSE_CATALOG payload (BP §13). Path `/api/catalog` returns the dict
 * verbatim from `config/catalog_config.py`. OpenAPI type is `Record<string,
 * Record<string, unknown>>` which is intentionally loose — callers should
 * narrow per use site.
 */
export type Catalog = Record<string, Record<string, unknown>>

// ─────────────────────────── Configuration ─────────────────────────────

/**
 * Base URL of the FastAPI backend. Override at build time with
 * `VITE_API_URL`. Trailing slashes are stripped so we can naively
 * concatenate `${API_BASE}/api/...`.
 */
export const API_BASE: string = (
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'
).replace(/\/+$/, '')

const ACCESS_TOKEN_KEY = 'nexus.accessToken'
const REFRESH_TOKEN_KEY = 'nexus.refreshToken'

// ─────────────────────────── Token storage ─────────────────────────────
//
// `localStorage` is XSS-vulnerable. We accept the tradeoff for v1.0 because:
//  (a) the backend is JWT-only (no cookies/CSRF state to defend),
//  (b) the alternative (httpOnly cookies + CSRF tokens) needs backend work
//      that BP §08 does not currently provide,
//  (c) the WebSocket browser API cannot send custom headers and BP §08.8
//      already moves the token into `?token=`, so any storage choice here
//      is mirrored to the WS connect URL.
// Mitigations on the backend: short access TTL (60 min), refresh rotation
// re-checks `is_active`, CSP headers in FASE 7.

export const tokenStorage = {
  getAccess(): string | null {
    if (typeof window === 'undefined') return null
    return window.localStorage.getItem(ACCESS_TOKEN_KEY)
  },
  getRefresh(): string | null {
    if (typeof window === 'undefined') return null
    return window.localStorage.getItem(REFRESH_TOKEN_KEY)
  },
  set(access: string, refresh?: string | null): void {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(ACCESS_TOKEN_KEY, access)
    if (refresh) window.localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear(): void {
    if (typeof window === 'undefined') return
    window.localStorage.removeItem(ACCESS_TOKEN_KEY)
    window.localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

// ─────────────────────────── Error type ────────────────────────────────

/**
 * Thrown for any non-2xx HTTP response. The backend (`HTTPException`)
 * returns `{detail: string | object}`. We surface both the status and a
 * best-effort human message — callers can `instanceof ApiError` to branch
 * on status (e.g. 403 → forbidden screen).
 */
export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function parseErrorMessage(res: Response): Promise<{ msg: string; detail: unknown }> {
  // FastAPI default error shape: { "detail": "..." } or { "detail": [...] }
  // for validation errors. We surface the string if scalar, otherwise the
  // status text — and always pass the raw `detail` for advanced callers.
  try {
    const body = await res.clone().json()
    const detail = (body as { detail?: unknown }).detail
    if (typeof detail === 'string') return { msg: detail, detail }
    if (detail !== undefined) return { msg: res.statusText || 'Request failed', detail }
    return { msg: res.statusText || 'Request failed', detail: body }
  } catch {
    const text = await res.text().catch(() => '')
    return { msg: text || res.statusText || 'Request failed', detail: text }
  }
}

// ─────────────────────────── Refresh logic ─────────────────────────────
//
// One in-flight refresh at a time: if 5 concurrent requests get a 401, only
// the first triggers a refresh; the others await the same promise. Without
// this guard we'd burn 5× refresh tokens (each rotation invalidates the
// previous on the backend? — no, BP §08.3 doesn't rotate refresh, but the
// extra round-trips are still wasted).

let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  const refresh = tokenStorage.getRefresh()
  if (!refresh) return null

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh } satisfies RefreshRequest),
      })
      if (!res.ok) return null
      const data = (await res.json()) as RefreshResponse
      tokenStorage.set(data.access_token, refresh)
      return data.access_token
    } catch {
      return null
    } finally {
      // Always clear so a future 401 can start a fresh attempt.
      // Cleared inside .finally to avoid TOCTOU between resolve and clear.
      setTimeout(() => {
        refreshInFlight = null
      }, 0)
    }
  })()

  return refreshInFlight
}

function emitLogout(): void {
  tokenStorage.clear()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('auth:logout'))
  }
}

// ─────────────────────────── Core request wrapper ──────────────────────

interface RequestOpts {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON body — will be serialized. Mutually exclusive with `formData`. */
  json?: unknown
  /** Multipart body (file uploads). When set, do NOT add Content-Type. */
  formData?: FormData
  /** Query string params. `undefined` values are dropped. */
  query?: Record<string, string | number | boolean | undefined>
  /** Skip auth header even if a token is present (used by login/refresh). */
  noAuth?: boolean
  /**
   * Skip the 401 → refresh-and-retry loop. The refresh call itself sets
   * this to avoid recursion.
   */
  noRetry?: boolean
}

function buildUrl(path: string, query?: RequestOpts['query']): string {
  const url = new URL(`${API_BASE}${path}`)
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
    }
  }
  return url.toString()
}

async function request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const url = buildUrl(path, opts.query)
  const headers = new Headers()
  if (opts.json !== undefined) headers.set('Content-Type', 'application/json')
  if (!opts.noAuth) {
    const access = tokenStorage.getAccess()
    if (access) headers.set('Authorization', `Bearer ${access}`)
  }

  const init: RequestInit = {
    method: opts.method ?? 'GET',
    headers,
  }
  if (opts.json !== undefined) init.body = JSON.stringify(opts.json)
  else if (opts.formData !== undefined) init.body = opts.formData

  let res = await fetch(url, init)

  // 401 → try one refresh, then retry original request once. Never on
  // auth/login (noAuth) or on the refresh call itself (noRetry).
  if (res.status === 401 && !opts.noAuth && !opts.noRetry) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`)
      res = await fetch(url, { ...init, headers })
    } else {
      emitLogout()
    }
  }

  if (!res.ok) {
    const { msg, detail } = await parseErrorMessage(res)
    throw new ApiError(res.status, msg, detail)
  }

  // 204 No Content → return undefined as T.
  if (res.status === 204) return undefined as T
  // Empty body but 2xx (rare): try JSON, fall back to undefined.
  const text = await res.text()
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    return text as unknown as T
  }
}

// ─────────────────────────── Auth ──────────────────────────────────────

async function login(email: string, password: string): Promise<LoginResponse> {
  const body: LoginRequest = { email, password }
  const data = await request<LoginResponse>('/api/auth/login', {
    method: 'POST',
    json: body,
    noAuth: true,
  })
  tokenStorage.set(data.access_token, data.refresh_token)
  return data
}

async function refresh(refreshToken: string): Promise<RefreshResponse> {
  // Public surface for manual refresh (callers normally don't need it —
  // the 401 interceptor handles refresh transparently).
  const body: RefreshRequest = { refresh_token: refreshToken }
  const data = await request<RefreshResponse>('/api/auth/refresh', {
    method: 'POST',
    json: body,
    noAuth: true,
    noRetry: true,
  })
  tokenStorage.set(data.access_token, refreshToken)
  return data
}

function logout(): void {
  // Local-only logout (BP §08 has no /logout endpoint — JWT is stateless).
  // For server-side revocation in FASE 7+, add a denylist endpoint.
  emitLogout()
}

async function getMe(): Promise<UserMe> {
  return request<UserMe>('/api/users/me')
}

// ─────────────────────────── Courses ───────────────────────────────────

async function createCourse(data: CourseRequest): Promise<CourseResponse> {
  return request<CourseResponse>('/api/courses', { method: 'POST', json: data })
}

interface CourseListFilters {
  // Index signature lets us pass this directly as `query` without a copy.
  [key: string]: string | number | boolean | undefined
  page?: number
  per_page?: number
  status?: string
}

async function getCourses(filters: CourseListFilters = {}): Promise<CourseSummary[]> {
  // Backend returns a plain array (no envelope). Pagination is
  // page+per_page driven; the caller decides when to stop.
  return request<CourseSummary[]>('/api/courses', { query: filters })
}

async function getCourse(id: string): Promise<CourseDetail> {
  return request<CourseDetail>(`/api/courses/${encodeURIComponent(id)}`)
}

async function certifyCourse(id: string): Promise<CertifyResponse> {
  return request<CertifyResponse>(
    `/api/courses/${encodeURIComponent(id)}/certify`,
    { method: 'POST' },
  )
}

async function downloadCourse(id: string, format: DownloadFormat): Promise<Blob> {
  // Returns a Blob (PPTX/PDF/ZIP/audio-zip). Auth is added by `request`
  // logic which we inline here to keep the Blob handling explicit.
  const url = buildUrl(
    `/api/courses/${encodeURIComponent(id)}/download/${encodeURIComponent(format)}`,
  )
  const headers = new Headers()
  const access = tokenStorage.getAccess()
  if (access) headers.set('Authorization', `Bearer ${access}`)

  let res = await fetch(url, { headers })
  if (res.status === 401) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`)
      res = await fetch(url, { headers })
    } else {
      emitLogout()
    }
  }
  if (!res.ok) {
    const { msg, detail } = await parseErrorMessage(res)
    throw new ApiError(res.status, msg, detail)
  }
  return res.blob()
}

async function deleteCourse(id: string): Promise<{ status: string; course_id: string }> {
  return request<{ status: string; course_id: string }>(
    `/api/courses/${encodeURIComponent(id)}`,
    { method: 'DELETE' },
  )
}

// ─────────────────────────── Regulations ───────────────────────────────

/**
 * Metadata required by `POST /api/regulations/upload` alongside the file
 * (FastAPI `Form(...)` fields, not JSON). Mirrors the signature in
 * `app/api/routes/regulations.py`.
 */
export interface RegulationUploadMeta {
  slug: string
  title: string
  reg_type: string
  region?: string
  issuing_body?: string
  source_url?: string
}

async function uploadRegulation(
  file: File,
  meta: RegulationUploadMeta,
): Promise<UploadResponse> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('slug', meta.slug)
  fd.append('title', meta.title)
  fd.append('reg_type', meta.reg_type)
  if (meta.region) fd.append('region', meta.region)
  if (meta.issuing_body) fd.append('issuing_body', meta.issuing_body)
  if (meta.source_url) fd.append('source_url', meta.source_url)
  return request<UploadResponse>('/api/regulations/upload', {
    method: 'POST',
    formData: fd,
  })
}

async function getRegulations(
  filters: { page?: number; per_page?: number } = {},
): Promise<RegulationSummary[]> {
  return request<RegulationSummary[]>('/api/regulations', { query: filters })
}

async function getChunks(
  regulationId: string,
  filters: { page?: number; per_page?: number } = {},
): Promise<ChunkSummary[]> {
  return request<ChunkSummary[]>(
    `/api/regulations/${encodeURIComponent(regulationId)}/chunks`,
    { query: filters },
  )
}

/** Forma di un link normativa->corso esposto dal backend (v2 F1.D).
 *  Coincide con LinkedCourseSummary del Pydantic model. */
export interface LinkedCourse {
  course_type_slug: string
  title: string
  hours: number
  target: string
  link_source: 'scrape' | 'remap' | 'manual' | 'imported_v1'
  link_notes?: string | null
  course_approved: boolean
}

/** Lista dei corsi del catalogo che dichiarano la normativa come riferimento.
 *  Accetta sia lo slug (preferito) sia l'UUID della normativa. */
async function getLinkedCourses(slugOrId: string): Promise<LinkedCourse[]> {
  return request<LinkedCourse[]>(
    `/api/regulations/${encodeURIComponent(slugOrId)}/linked-courses`,
  )
}

async function deleteRegulation(
  regulationId: string,
): Promise<{ status: string; regulation_id: string }> {
  return request<{ status: string; regulation_id: string }>(
    `/api/regulations/${encodeURIComponent(regulationId)}`,
    { method: 'DELETE' },
  )
}

// ─────────────────────────── Course Studio (FASE 7) ───────────────────

/**
 * Slide deserializzata da `slide_contents_json` (FASE 7 Studio).
 * Tipo loose: il backend ritorna il dict SlideContent verbatim.
 */
export interface StudioSlide {
  index: number
  module_index: number
  slide_type: string
  title: string
  body: string
  speaker_notes: string
  normative_ref: string
  source_chunk_ids: string[]
  image: {
    strategy: string
    query?: string | null
    query_url?: string | null
    aspect_hint?: string | null
    diagram_code?: string | null
  }
  quiz_options?: string[] | null
  quiz_correct?: number | null
}

export interface SlidesResponse {
  course_id: string
  total: number
  slides: StudioSlide[]
}

export interface SlidePatchBody {
  title?: string
  body?: string
  speaker_notes?: string
  normative_ref?: string
  quiz_options?: string[]
  quiz_correct?: number
}

async function getCourseSlides(id: string): Promise<SlidesResponse> {
  return request<SlidesResponse>(`/api/courses/${encodeURIComponent(id)}/slides`)
}

async function getCourseSlide(id: string, idx: number): Promise<StudioSlide> {
  return request<StudioSlide>(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}`,
  )
}

// ─── D3 skeleton review (vast-hopping-sketch) ───

export interface SkeletonItem {
  ordinal: number
  sub_topic: string
  retrieval_query: string
}

export interface ModuleSkeleton {
  module_index: number
  title: string
  items: SkeletonItem[]
  approved: boolean
}

export interface SkeletonResponse {
  course_id: string
  status: string
  modules: ModuleSkeleton[]
  approved_at?: string | null
}

async function getCourseSkeleton(id: string): Promise<SkeletonResponse> {
  return request<SkeletonResponse>(
    `/api/courses/${encodeURIComponent(id)}/skeleton`,
  )
}

async function updateCourseSkeleton(
  id: string,
  modules: ModuleSkeleton[],
): Promise<SkeletonResponse> {
  return request<SkeletonResponse>(
    `/api/courses/${encodeURIComponent(id)}/skeleton`,
    { method: 'PUT', json: { modules } },
  )
}

async function approveCourseSkeleton(
  id: string,
): Promise<{ status: string; job_id: string }> {
  return request<{ status: string; job_id: string }>(
    `/api/courses/${encodeURIComponent(id)}/skeleton/approve`,
    { method: 'POST' },
  )
}

// ─── F3.AI — LLM micro-actions sulla struttura (2026-05-31) ───
// Risposte tipizzate: pulsanti per-voce ritornano {proposal} oppure
// {alternatives:[3]}; il free-edit per-modulo ritorna {patch:{items:[6-10]}}.

export interface SubtopicProposal {
  sub_topic: string
  retrieval_query: string
}

export type SkeletonAIVoiceAction =
  | 'rephrase_subtopic'
  | 'make_operational'
  | 'suggest_alternatives'

export type SkeletonAIVoiceResponse =
  | { proposal: SubtopicProposal }
  | { alternatives: SubtopicProposal[] }

export interface SkeletonAIModuleResponse {
  patch: { items: SkeletonItem[] }
}

async function aiEditSkeletonVoice(
  id: string,
  body: {
    action: SkeletonAIVoiceAction
    module_index: number
    voice_ordinal: number
  },
): Promise<SkeletonAIVoiceResponse> {
  return request<SkeletonAIVoiceResponse>(
    `/api/courses/${encodeURIComponent(id)}/skeleton/ai-edit-voice`,
    { method: 'POST', json: body },
  )
}

async function aiEditSkeletonModule(
  id: string,
  body: { module_index: number; user_instruction: string },
): Promise<SkeletonAIModuleResponse> {
  return request<SkeletonAIModuleResponse>(
    `/api/courses/${encodeURIComponent(id)}/skeleton/ai-edit-module`,
    { method: 'POST', json: body },
  )
}

async function patchCourseSlide(
  id: string,
  idx: number,
  patch: SlidePatchBody,
): Promise<StudioSlide> {
  return request<StudioSlide>(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}`,
    { method: 'PATCH', json: patch },
  )
}

async function patchSlideImage(
  id: string,
  idx: number,
  image: { strategy?: string; query?: string; query_url?: string; aspect_hint?: string },
): Promise<StudioSlide> {
  return request<StudioSlide>(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}/image`,
    { method: 'PATCH', json: image },
  )
}

async function searchSlideImages(
  id: string,
  q: string,
  orientation?: string,
): Promise<{ candidates: string[] }> {
  return request<{ candidates: string[] }>(
    `/api/courses/${encodeURIComponent(id)}/image/search`,
    { query: { q, orientation } },
  )
}

// F5.2 — Library tab (vast-hopping post-MVP 2026-05-31)
export interface LibraryHit {
  id: string
  file_path: string
  tags: string[]
  source: string
  license: string | null
  attribution: string | null
  source_url: string | null
  width: number | null
  height: number | null
  usage_count: number
  score: number
}

async function searchImageLibrary(
  id: string,
  q: string,
  k: number = 8,
): Promise<{ hits: LibraryHit[]; query: string }> {
  return request<{ hits: LibraryHit[]; query: string }>(
    `/api/courses/${encodeURIComponent(id)}/image/library/search`,
    { query: { q, k } },
  )
}

// ─── F6 — Chat Studio (vast-hopping post-MVP 2026-05-31) ───
// Memoria conversation cross-session + SSE streaming + apply diff.

export interface ProposedPatchDTO {
  title?: string | null
  body?: string[] | null
  speaker_notes?: string | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  slide_index: number | null
  tool_calls: { proposed_patch?: ProposedPatchDTO } | null
  applied_at: string | null
  created_at: string | null
}

export interface ChatHistoryResponse {
  conversation_id: string
  messages: ChatMessage[]
}

async function getChatHistory(id: string): Promise<ChatHistoryResponse> {
  return request<ChatHistoryResponse>(
    `/api/courses/${encodeURIComponent(id)}/chat/history`,
  )
}

async function applyChatMessage(
  id: string,
  messageId: string,
): Promise<{ applied: boolean; slide_index: number }> {
  return request(
    `/api/courses/${encodeURIComponent(id)}/chat/messages/${encodeURIComponent(messageId)}/apply`,
    { method: 'POST' },
  )
}

/**
 * URL endpoint SSE per POST /chat. Il client streaming usa fetch+ReadableStream
 * (non EventSource: EventSource non supporta header Authorization). Token JWT
 * passato in query string come fallback per autenticazione GET di Vercel proxy.
 */
function chatStreamUrl(id: string): string {
  return buildUrl(`/api/courses/${encodeURIComponent(id)}/chat`)
}

/** URL diretto del singolo MP3 di una slide (per <audio src>). */
function slideAudioUrl(id: string, idx: number): string {
  return buildUrl(`/api/courses/${encodeURIComponent(id)}/audio/${idx}`)
}

// F7.4 — audio track metadata per UI badge provider (post-MVP 2026-05-31).
export interface AudioInfo {
  provider: 'edge' | 'azure'
  voice: string
  duration_seconds: number | null
}

async function getSlideAudioInfo(id: string, idx: number): Promise<AudioInfo> {
  return request<AudioInfo>(
    `/api/courses/${encodeURIComponent(id)}/audio/${idx}/info`,
  )
}

/** URL diretto del PNG-render della pagina PDF della slide (per <img src>).
 *  Restituisce 404 finché il corso non è mai stato rigenerato/non ha PDF. */
function slidePreviewUrl(id: string, idx: number): string {
  return buildUrl(`/api/courses/${encodeURIComponent(id)}/slides/${idx}/preview.png`)
}

async function regenerateSlide(
  id: string,
  idx: number,
  instruction: string,
): Promise<StudioSlide> {
  return request<StudioSlide>(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}/regenerate`,
    { method: 'POST', json: { instruction, use_h8: false } },
  )
}

/**
 * F4b (analista 2026-05-31): rigenera SINGOLA slide via H8 voce-aware.
 * Backend identifica voce skeleton owner della slide + ri-genera con
 * build_voice_prompt + chunks B2+B3+B4 della voce. Slide sostituita nel
 * slide_contents_json + dirty=true (RebuildBanner mostra "esegui /rebuild").
 *
 * Synchronous: 15-30s tipico. Return: {status, old_title, new_title,
 * voce_used, provider, note}. 409 se slide bookend o course senza skeleton.
 */
async function regenerateSlideH8(
  id: string,
  idx: number,
): Promise<{
  status: string
  course_id: string
  slide_index: number
  voce_ordinal_used?: number
  voce_sub_topic_used?: string
  old_title?: string
  new_title?: string
  provider?: string
  note?: string
}> {
  return request(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}/regenerate`,
    { method: 'POST', json: { instruction: '', use_h8: true } },
  )
}

// F4 D9 Quality Issues (analista sign-off 2026-05-31)
export interface QualityIssue {
  slide_index: number
  module_index: number | null
  issue_type:
    | 'image_placeholder'
    | 'diagram_branded_fallback'
    | 'quiz_no_options'
    | 'notes_too_short'
    | 'module_underpopulated'
    | 'module_corpus_thin'
    | 'image_overused_in_module'
    | 'title_near_duplicate_in_module'
    | 'bullet_citation_warning'
    | 'bullet_citation_warning_as_object'
    | 'title_citation_warning'
  severity: 'info' | 'warning' | 'error'
  context?: Record<string, unknown>
}

export interface QualityIssuesResponse {
  course_id: string
  total_issues: number
  by_severity: Partial<Record<'info' | 'warning' | 'error', number>>
  by_type: Partial<Record<string, number>>
  issues: QualityIssue[]
}

/**
 * F4: compute quality issues per il corso (badge UI Course Studio).
 * Aggrega 9 sensori D9 (image_placeholder, diagram_fallback, quiz_no_options,
 * notes_too_short, module_underpopulated, image_overused, title_duplicate,
 * bullet_citation_warning, title_citation_warning). NON blocca download.
 */
async function getQualityIssues(courseId: string): Promise<QualityIssuesResponse> {
  return request<QualityIssuesResponse>(
    `/api/courses/${encodeURIComponent(courseId)}/quality-issues`,
  )
}

// F9 Regulation→Courses Discovery types (analista sign-off 2026-05-31)
export type CompatibleCoverage = 'generabile' | 'corpus_thin' | 'no_coverage'

export interface CompatibleCourse {
  slug: string
  title: string
  hours: number
  regulation_slugs: string[]
  overall_coverage: CompatibleCoverage
  chunks_per_regulation: Record<string, number>
  missing_regulations: string[]
}

export interface CompatibleCoursesResponse {
  regulation_slug: string
  n_courses_compatible: number
  courses: CompatibleCourse[]
  note?: string
}

/**
 * F9: ritorna i course_type del catalog che usano questa regulation,
 * con coverage score per badge UI (generabile/corpus_thin/no_coverage).
 * Pensato per workflow "carica normativa → vedi quali corsi posso generare".
 */
async function getCompatibleCourses(
  regulationSlug: string,
): Promise<CompatibleCoursesResponse> {
  return request<CompatibleCoursesResponse>(
    `/api/regulations/${encodeURIComponent(regulationSlug)}/compatible-courses`,
  )
}

async function rebuildCourse(
  id: string,
): Promise<{ status: string; course_id: string }> {
  return request<{ status: string; course_id: string }>(
    `/api/courses/${encodeURIComponent(id)}/rebuild`,
    { method: 'POST' },
  )
}

// ── Slide management (FASE 6): add / move / delete / duplicate ──────────
// Tutti ritornano l'array slide aggiornato (reindex contiguo lato backend).

async function addSlide(
  id: string,
  afterIdx: number,
  slideType: string,
): Promise<StudioSlide[]> {
  return request<StudioSlide[]>(
    `/api/courses/${encodeURIComponent(id)}/slides`,
    { method: 'POST', json: { after_idx: afterIdx, slide_type: slideType } },
  )
}

async function moveSlide(
  id: string,
  idx: number,
  direction: 'up' | 'down',
): Promise<StudioSlide[]> {
  return request<StudioSlide[]>(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}/move`,
    { method: 'POST', json: { direction } },
  )
}

async function duplicateSlide(id: string, idx: number): Promise<StudioSlide[]> {
  return request<StudioSlide[]>(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}/duplicate`,
    { method: 'POST' },
  )
}

async function deleteSlide(id: string, idx: number): Promise<StudioSlide[]> {
  return request<StudioSlide[]>(
    `/api/courses/${encodeURIComponent(id)}/slides/${idx}`,
    { method: 'DELETE' },
  )
}

// ─────────────────────────── Admin ─────────────────────────────────────

async function getMetrics(days: number = 7): Promise<MetricsResponse> {
  return request<MetricsResponse>('/api/admin/metrics', { query: { days } })
}

async function getDashboardStats(): Promise<DashboardStats> {
  return request<DashboardStats>('/api/dashboard/stats')
}

async function getBrandPresets(): Promise<BrandPresetSummary[]> {
  return request<BrandPresetSummary[]>('/api/brand-presets')
}

async function getCatalog(): Promise<Catalog> {
  return request<Catalog>('/api/catalog')
}

// ─── F1 D8 — Admin catalog DB-driven CRUD (vast-hopping) ───
// Coesiste con getCatalog() config-driven sopra. Quando flag v2_catalog_from_db
// è true, il research_agent legge dal DB invece che da config; questi endpoint
// sono il lato UI per la review/approval.

export interface CatalogEntrySummary {
  slug: string
  title: string
  hours: number
  target: string
  regulation_slugs: string[]
  regional: boolean
  source: string
  source_url?: string | null
  scraped_at?: string | null
  approved_at?: string | null
  approved_by?: string | null
  created_at?: string | null
  updated_at?: string | null
  n_modules: number
}

export interface CatalogListResponse {
  entries: CatalogEntrySummary[]
  total: number
  page: number
  per_page: number
}

export interface CatalogModule {
  id: string
  ordinal: number
  title: string
  normative_refs: string[]
  source: string
  created_at?: string | null
}

export interface CatalogEntryDetail extends CatalogEntrySummary {
  modules: CatalogModule[]
}

export interface CatalogUpdateBody {
  title?: string
  hours?: number
  target?: string
  regulation_slugs?: string[]
  regional?: boolean
}

export interface CatalogSummaryByTarget {
  target: string
  n_total: number
  n_approved: number
}

export interface CatalogSummaryResponse {
  total: number
  approved: number
  pending: number
  by_target: CatalogSummaryByTarget[]
  snapshot_at: string
}

async function adminListCatalog(params: {
  page?: number
  per_page?: number
  approved_only?: boolean
  target?: string
  search?: string
} = {}): Promise<CatalogListResponse> {
  return request<CatalogListResponse>('/api/admin/catalog', { query: params })
}

async function adminGetCatalogSummary(): Promise<CatalogSummaryResponse> {
  return request<CatalogSummaryResponse>('/api/admin/catalog/summary')
}

async function adminGetCatalogEntry(slug: string): Promise<CatalogEntryDetail> {
  return request<CatalogEntryDetail>(
    `/api/admin/catalog/${encodeURIComponent(slug)}`,
  )
}

async function adminUpdateCatalogEntry(
  slug: string,
  body: CatalogUpdateBody,
): Promise<CatalogEntryDetail> {
  return request<CatalogEntryDetail>(
    `/api/admin/catalog/${encodeURIComponent(slug)}`,
    { method: 'PATCH', json: body },
  )
}

async function adminApproveCatalogEntry(slug: string): Promise<CatalogEntryDetail> {
  return request<CatalogEntryDetail>(
    `/api/admin/catalog/${encodeURIComponent(slug)}/approve`,
    { method: 'POST' },
  )
}

async function adminUnapproveCatalogEntry(slug: string): Promise<CatalogEntryDetail> {
  return request<CatalogEntryDetail>(
    `/api/admin/catalog/${encodeURIComponent(slug)}/unapprove`,
    { method: 'POST' },
  )
}

async function adminBulkApproveCatalog(slugs: string[]): Promise<{ approved_count: number }> {
  return request<{ approved_count: number }>(
    '/api/admin/catalog/bulk-approve',
    { method: 'POST', json: { slugs } },
  )
}

// ─── Step B — Image Library admin (upload + audit + delete) ───
export interface ImageLibraryAdminEntry {
  id: string
  file_path: string
  tags: string[]
  source: string
  license: string | null
  attribution: string | null
  source_url: string | null
  width: number | null
  height: number | null
  bytes: number | null
  usage_count: number
  created_at: string | null
  updated_at: string | null
}

export interface ImageLibraryListResponse {
  entries: ImageLibraryAdminEntry[]
  total: number
  page: number
  per_page: number
}

async function adminListImages(params: {
  page?: number
  per_page?: number
  source?: string
} = {}): Promise<ImageLibraryListResponse> {
  return request<ImageLibraryListResponse>('/api/admin/images/library', { query: params })
}

async function adminUploadImage(args: {
  file: File
  tags: string
  source?: string
  license?: string
  attribution?: string
  source_url?: string
}): Promise<{ id: string; file_path: string }> {
  const fd = new FormData()
  fd.append('file', args.file)
  fd.append('tags', args.tags)
  if (args.source) fd.append('source', args.source)
  if (args.license) fd.append('license', args.license)
  if (args.attribution) fd.append('attribution', args.attribution)
  if (args.source_url) fd.append('source_url', args.source_url)
  return request<{ id: string; file_path: string }>(
    '/api/admin/images/library',
    { method: 'POST', formData: fd },
  )
}

async function adminDeleteImage(imageId: string): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/api/admin/images/library/${encodeURIComponent(imageId)}`,
    { method: 'DELETE' },
  )
}

// ─── Step C — Diagram catalog admin viewer ───
export interface DiagramSlotInfo {
  name: string
  max_chars: number
}

export interface DiagramTemplateInfo {
  name: string
  description: string
  slots: DiagramSlotInfo[]
  usage_count: number
  svg_available: boolean
  svg_content?: string | null
}

async function adminDiagramsCatalog(): Promise<DiagramTemplateInfo[]> {
  return request<DiagramTemplateInfo[]>('/api/admin/diagrams/catalog')
}

function adminDiagramSvgUrl(name: string): string {
  // Token in query string to allow <iframe> preview (no Authorization header
  // possible on iframe src). Backend accepts ?access_token= as fallback.
  const token = tokenStorage.getAccess() ?? ''
  return `${API_BASE}/api/admin/diagrams/${encodeURIComponent(name)}/svg?access_token=${encodeURIComponent(token)}`
}

// ─────────────────────────── Public surface ────────────────────────────

/**
 * Single namespace import for all REST calls:
 *
 *     import { api } from '@/lib/api'
 *     await api.login('a@b.it', 'pw')
 *     const courses = await api.getCourses({ page: 1 })
 *
 * Each method is fully typed against the OpenAPI schema (FASE 6.4).
 */
export const api = {
  // Auth
  login,
  refresh,
  logout,
  getMe,
  // Courses
  createCourse,
  getCourses,
  getCourse,
  certifyCourse,
  downloadCourse,
  deleteCourse,
  // Course Studio (FASE 7)
  getCourseSlides,
  getCourseSlide,
  patchCourseSlide,
  patchSlideImage,
  searchSlideImages,
  searchImageLibrary,
  // F6 chat
  getChatHistory,
  applyChatMessage,
  chatStreamUrl,
  // F7 audio
  getSlideAudioInfo,
  slideAudioUrl,
  slidePreviewUrl,
  regenerateSlide,
  regenerateSlideH8,
  getQualityIssues,
  getCompatibleCourses,
  rebuildCourse,
  addSlide,
  moveSlide,
  duplicateSlide,
  deleteSlide,
  // D3 skeleton review
  getCourseSkeleton,
  updateCourseSkeleton,
  approveCourseSkeleton,
  // F3.AI micro-actions LLM sulla struttura
  aiEditSkeletonVoice,
  aiEditSkeletonModule,
  // Regulations
  uploadRegulation,
  getRegulations,
  getChunks,
  getLinkedCourses,
  deleteRegulation,
  // Admin
  getMetrics,
  getDashboardStats,
  getBrandPresets,
  getCatalog,
  // F1 catalog DB-driven admin CRUD
  adminListCatalog,
  adminGetCatalogSummary,
  adminGetCatalogEntry,
  adminUpdateCatalogEntry,
  adminApproveCatalogEntry,
  adminUnapproveCatalogEntry,
  adminBulkApproveCatalog,
  // Step B — image library admin
  adminListImages,
  adminUploadImage,
  adminDeleteImage,
  // Step C — diagram catalog admin
  adminDiagramsCatalog,
  adminDiagramSvgUrl,
} as const

// Type-only re-export so consumers can refer to the OpenAPI schema directly.
export type { paths, components }
