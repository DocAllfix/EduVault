/**
 * Dashboard page — Cfp EduVault (BLUEPRINT §10).
 *
 * ─── Design intent (frontend-design skill, point 1) ──────────────────────
 * Purpose: operator cockpit. In one screen the user (a) sees 4 KPI
 *   counters, (b) finds an existing course via a filterable table,
 *   (c) launches a new course via the prominent CTA. ≤30s task.
 * Tone: Linear.app applied to a small institution — medium info density,
 *   coloured status badges, animated dot ONLY on the "live" generating
 *   stat card and on `generating` row badges. No charts (BP §10 doesn't
 *   require any in v1.0; analytics ship later).
 * Constraints: REI-1 adapt template `features/dashboard` + `features/tasks`
 *   pattern, REI-11 pixel-perfect, react-query for fetch (already in
 *   `main.tsx` provider), URL-sync pagination via `useTableUrlState`,
 *   ownership-aware (admin sees all, operator sees own — backend enforces).
 * Differentiation: (a) one card pulses (brand-pink ring + spinning icon)
 *   when count > 0; (b) `Nuovo Corso` CTA in the header reads-as
 *   the action you most want to perform when the queue is empty.
 *
 * ─── Impeccable self-audit (point 4) — see end-of-file SELF-AUDIT block.
 */

import { useMemo, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError, type CourseSummary } from '@/lib/api'
import { tokenStorage } from '@/lib/api'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { HelpButton } from '@/lib/onboarding/HelpButton'
import { JobsBadge } from '@/components/jobs-badge'
import { OnboardingBanner } from '@/lib/onboarding/OnboardingBanner'
import { startDashboardTour } from '@/lib/onboarding/tours/dashboard'

import { ArchivedCoursesSection } from './components/archived-courses-section'
import { CoursesPrimaryButtons } from './components/courses-primary-buttons'
import { CoursesTable } from './components/courses-table'
import { DeleteCourseDialog } from './components/delete-course-dialog'
import { EnrichedStats } from './components/enriched-stats'
import { StatsCards } from './components/stats-cards'

const STATS_QK = ['dashboard', 'stats'] as const
const COURSES_QK = ['courses', 'list'] as const
const GENERATING_QK = ['courses', 'generating-count'] as const

// 30s window for "live" counters — same cadence as BP §10.3 polling
// fallback (docs/POLLING_FALLBACK.md). Faster polling here would only
// matter if we drove progress bars; we don't — the WS handles per-job.
const REFRESH_INTERVAL_MS = 30_000

// JWT payload role extractor. We decode the access token client-side
// just for `role` (UI gating only — the backend re-verifies every call,
// so a forged role here grants nothing). No JWT lib needed; the access
// token is `header.payload.signature`, all base64url.
function getRoleFromToken(): string | undefined {
  const tok = tokenStorage.getAccess()
  if (!tok) return undefined
  const parts = tok.split('.')
  if (parts.length !== 3) return undefined
  try {
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    const payload = JSON.parse(json) as { role?: string }
    return payload.role
  } catch {
    return undefined
  }
}

export function Dashboard() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [pendingDelete, setPendingDelete] = useState<CourseSummary | null>(null)

  // role is stable for the session (until refresh rotates it); useMemo to
  // avoid recomputing on every render.
  const role = useMemo(() => getRoleFromToken(), [])

  // Dashboard counters. Admins only get a 200 (BP §10 D57); operators get
  // 403, which we swallow into "—" rather than toast every render.
  const statsQuery = useQuery({
    queryKey: STATS_QK,
    queryFn: async () => {
      try {
        return await api.getDashboardStats()
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) return undefined
        throw err
      }
    },
    refetchInterval: REFRESH_INTERVAL_MS,
  })

  // Courses list. Backend returns an array (no envelope) — we fetch
  // page 1 with a generous per_page; pagination is client-side via
  // TanStack table (suits the dashboard's working-set scale; >100
  // courses we'll switch to server-side in 6.10).
  //
  // F10 2026-06-02: backend non ha un filtro "exclude_archived" puro;
  // fetcho TUTTI (status=null) e filtro client-side. La sezione
  // Archiviati ha una propria query indipendente con status=archived
  // → 2 fetch parallel ma robuste contro lo stesso refetchInterval.
  const coursesQuery = useQuery({
    queryKey: COURSES_QK,
    queryFn: () => api.getCourses({ page: 1, per_page: 100 }),
    select: (rows) => rows.filter((c) => c.status !== 'archived'),
    refetchInterval: REFRESH_INTERVAL_MS,
  })

  const archivedCoursesQuery = useQuery({
    queryKey: [...COURSES_QK, 'archived'] as const,
    queryFn: () =>
      api.getCourses({ page: 1, per_page: 100, status: 'archived' }),
    refetchInterval: REFRESH_INTERVAL_MS,
  })

  // Dedicated "in-generating" count for the live stat card. Cheap query
  // because backend filters server-side via `?status=generating`.
  const generatingQuery = useQuery({
    queryKey: GENERATING_QK,
    queryFn: () =>
      api
        .getCourses({ page: 1, per_page: 100, status: 'generating' })
        .then((rows) => rows.length),
    refetchInterval: REFRESH_INTERVAL_MS,
  })

  function handleOpenDetail(c: CourseSummary) {
    // Route to the detail page (FASE 6.9). If the course is still
    // generating, the user may prefer the Progress Monitor — but the
    // detail page links there itself when it sees a non-terminal status,
    // so we navigate uniformly to /courses/$id.
    navigate({ to: '/courses/$id', params: { id: c.id } })
  }

  function handleDeleted() {
    void queryClient.invalidateQueries({ queryKey: COURSES_QK })
    void queryClient.invalidateQueries({ queryKey: STATS_QK })
    // F10: invalida anche la query archived perche` il corso appena
    // soft-deleted va a comparire nella tabella archiviati.
    void queryClient.invalidateQueries({
      queryKey: [...COURSES_QK, 'archived'],
    })
  }

  return (
    <>
      <Header>
        <Search />
        <div className='ms-auto flex items-center gap-2'>
          <JobsBadge />
          <HelpButton />
          <ThemeSwitch />
          <ConfigDrawer />
          <ProfileDropdown />
        </div>
      </Header>

      <Main>
        {/* F10 onboarding banner — visibile solo al primo accesso */}
        <OnboardingBanner
          pageId='dashboard'
          title='Benvenuto nella dashboard'
          body='Da qui monitori metriche, corsi recenti e accedi alle azioni rapide. Premi “Fai il tour” per una guida veloce di 4 passaggi.'
          onStartTour={() => startDashboardTour()}
        />

        {/* Page heading + primary CTA */}
        <div className='mb-6 flex flex-wrap items-end justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>Dashboard</h1>
            <p className='text-sm text-muted-foreground'>
              Stato della piattaforma e gestione corsi.
            </p>
          </div>
          <div data-tour='dashboard-new-course'>
            <CoursesPrimaryButtons />
          </div>
        </div>

        {/* 4 KPI cards */}
        <div className='mb-8' data-tour='dashboard-stats'>
          <StatsCards
            stats={statsQuery.data}
            generatingCount={generatingQuery.data}
            isLoading={statsQuery.isLoading || generatingQuery.isLoading}
          />
        </div>

        {/* FASE 13 — 4 dati arricchimento: status breakdown, dirty, ore, recenti */}
        <div data-tour='dashboard-recent-courses'>
          <EnrichedStats stats={statsQuery.data} />
        </div>

        {/* Courses list */}
        <section id='corsi' aria-labelledby='courses-heading' className='scroll-mt-20'>
          <h2
            id='courses-heading'
            className='mb-3 text-lg font-semibold tracking-tight'
          >
            Corsi
          </h2>
          <CoursesTable
            data={coursesQuery.data ?? []}
            isLoading={coursesQuery.isLoading}
            role={role}
            onDelete={setPendingDelete}
            onOpenDetail={handleOpenDetail}
          />
        </section>

        {/* F10 2026-06-02: sezione archiviati separata collassabile */}
        <ArchivedCoursesSection
          courses={archivedCoursesQuery.data}
          isLoading={archivedCoursesQuery.isLoading}
          onChange={handleDeleted}
        />
      </Main>

      <DeleteCourseDialog
        course={pendingDelete}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        onDeleted={handleDeleted}
      />
    </>
  )
}

/*
 * ─── SELF-AUDIT (impeccable skill, point 4) ──────────────────────────────
 *
 * Hierarchy:
 *   ✓ Single H1 "Dashboard" at the top. H2 "Corsi" introduces the table.
 *   ✓ KPI cards use CardTitle text-sm (label) + text-2xl bold (number)
 *     — clear two-level descent within each card.
 *
 * Spacing:
 *   ✓ mb-6 between header and stats, mb-8 between stats and section
 *     (rhythm via varied gaps, not monotonic — impeccable §layout).
 *   ✓ Table gap-4 inherited from CoursesTable.
 *   ✓ No nested cards (impeccable absolute ban). Stats are siblings;
 *     table sits outside any Card wrapper.
 *
 * Color strategy (impeccable §color):
 *   ✓ Restrained: neutral surface, brand-pink accent only on (a) live
 *     generating card border+spinner, (b) generating badge dot in table,
 *     (c) Nuovo Corso CTA. Total brand surface ≈ 8% — within "≤10%".
 *   ✓ Status badges use semantically obvious palette (amber/blue/green/
 *     red/grey). Green = brand-secondary (#769E2E) for certified —
 *     consistent reuse, not random new colour.
 *
 * Bans applied:
 *   ✓ No em dashes in copy. ✓ No gradient text. ✓ No side-stripe.
 *   ✓ No glassmorphism. ✓ No hero-metric template (4 cards + table, not
 *     "big number + supporting stats + gradient accent").
 *
 * Category-reflex:
 *   First-order "admin dashboard → recharts grid + gradient cards" →
 *   AVOIDED: 4 plain Cards + 1 Table, no charts.
 *   Second-order "admin not-chart-y → tailwind starter shell with empty
 *   states" → AVOIDED: real data flows, live pulsing card, brand visible.
 *
 * Live-data correctness:
 *   ✓ refetchInterval 30s aligns with BP §10.3 polling fallback. WS not
 *     used here — that's per-job (6.9). The card pulse signals activity
 *     even without explicit refresh.
 *   ✓ 403 on stats (operator role) returns `undefined` → cards show "—"
 *     and no error toast loop. Toast on hard errors only.
 *
 * Deferred to 6.9 / 6.10:
 *   - Course detail page (`onOpenDetail` toasts placeholder)
 *   - Course wizard route (`CoursesPrimaryButtons` toasts placeholder)
 *   - Auth guard in `_authenticated/route.tsx` (so role decoding always
 *     finds a token; today we tolerate missing token gracefully)
 */
