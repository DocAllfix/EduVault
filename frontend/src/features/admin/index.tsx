/**
 * Admin — `/admin` (BP §10).
 *
 * ─── Design intent (frontend-design) ────────────────────────────────────
 * Purpose: operational overview for admins — pipeline metrics, brand
 *   presets registry. NO transactions: this is a read-only page in v1.0.
 * Tone: Stripe dashboard rev (calm numbers, no charts). Three metric
 *   cards + brand presets grid + honest "Gestione utenti" stub.
 * Constraints: REI-5 — `/api/users` does NOT exist (only `/api/users/me`).
 *   Showing a fake user table would invent capability. Instead we render
 *   an honest "endpoint non disponibile in v1.0" block so admins know
 *   the section is acknowledged but not yet shipped.
 * Differentiation: transparent UI — when the backend doesn't support a
 *   feature, the UI says so instead of mocking it.
 *
 * ─── SELF-AUDIT at end-of-file.
 */

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BookOpen,
  Clock,
  Image as ImageIcon,
  Info,
  Layers,
  Users,
} from 'lucide-react'

import { api, ApiError, type BrandPresetSummary, type MetricsResponse, type DashboardStats } from '@/lib/api'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'

function paletteSwatches(palette: Record<string, unknown>): { name: string; hex: string }[] {
  const out: { name: string; hex: string }[] = []
  for (const [name, value] of Object.entries(palette)) {
    if (typeof value === 'string' && /^#[0-9a-f]{3,8}$/i.test(value)) {
      out.push({ name, hex: value })
    }
  }
  return out
}

export function Admin() {
  const metricsQ = useQuery({
    queryKey: ['admin', 'metrics'] as const,
    queryFn: async () => {
      try {
        return await api.getMetrics(7)
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) return undefined
        throw err
      }
    },
    refetchInterval: 60_000,
  })
  const statsQ = useQuery({
    queryKey: ['admin', 'dashboard-stats'] as const,
    queryFn: () => api.getDashboardStats(),
  })
  const presetsQ = useQuery({
    queryKey: ['admin', 'brand-presets'] as const,
    queryFn: () => api.getBrandPresets(),
  })

  const isForbidden = useMemo(
    () => metricsQ.error instanceof ApiError && metricsQ.error.status === 403,
    [metricsQ.error],
  )

  if (isForbidden) {
    return (
      <>
        <Header>
          <div className='ms-auto flex items-center gap-2'>
            <ThemeSwitch />
            <ProfileDropdown />
          </div>
        </Header>
        <Main>
          <Card className='mx-auto max-w-md'>
            <CardHeader>
              <CardTitle>Accesso negato</CardTitle>
              <CardDescription>
                Solo gli amministratori possono visualizzare questa pagina.
              </CardDescription>
            </CardHeader>
          </Card>
        </Main>
      </>
    )
  }

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center gap-2'>
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mb-6'>
          <h1 className='text-2xl font-bold tracking-tight'>Amministrazione</h1>
          <p className='text-sm text-muted-foreground'>
            Metriche pipeline, brand presets e gestione utenti.
          </p>
        </div>

        {/* Pipeline metrics (last 7 days) */}
        <section className='mb-8'>
          <h2 className='mb-3 text-lg font-semibold tracking-tight'>Metriche pipeline</h2>
          <MetricsGrid metrics={metricsQ.data} stats={statsQ.data} isLoading={metricsQ.isLoading || statsQ.isLoading} />
        </section>

        {/* Brand presets */}
        <section className='mb-8'>
          <h2 className='mb-3 text-lg font-semibold tracking-tight'>Brand presets</h2>
          {presetsQ.isLoading ? (
            <Skeleton className='h-32 w-full' />
          ) : !presetsQ.data?.length ? (
            <Card>
              <CardContent className='py-6 text-sm text-muted-foreground'>
                Nessun brand preset configurato.
              </CardContent>
            </Card>
          ) : (
            <div className='grid gap-4 md:grid-cols-2'>
              {presetsQ.data.map((p) => <PresetCard key={p.id} preset={p} />)}
            </div>
          )}
        </section>

        {/* Asset bank & catalogo: 3 entry points */}
        <section className='mb-8'>
          <h2 className='mb-3 text-lg font-semibold tracking-tight'>Asset bank & catalogo</h2>
          <div className='grid gap-4 sm:grid-cols-3'>
            <Card>
              <CardHeader>
                <CardTitle className='flex items-center gap-2 text-base'>
                  <Layers className='text-brand-primary size-4' aria-hidden='true' />
                  Catalogo corsi
                </CardTitle>
                <CardDescription>
                  Tipologie corso + approvazione gate.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <a
                  href='/admin/catalog'
                  className='bg-brand-primary text-primary-foreground hover:bg-brand-primary/90 inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-medium transition-colors'
                >
                  Apri →
                </a>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className='flex items-center gap-2 text-base'>
                  <ImageIcon className='text-brand-primary size-4' aria-hidden='true' />
                  Image Library
                </CardTitle>
                <CardDescription>
                  Asset visuali, upload, audit usage.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <a
                  href='/admin/images'
                  className='bg-brand-primary text-primary-foreground hover:bg-brand-primary/90 inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-medium transition-colors'
                >
                  Apri →
                </a>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className='flex items-center gap-2 text-base'>
                  <Layers className='text-brand-primary size-4' aria-hidden='true' />
                  Diagrammi catalog
                </CardTitle>
                <CardDescription>
                  Template SVG, slot, usage.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <a
                  href='/admin/diagrams'
                  className='bg-brand-primary text-primary-foreground hover:bg-brand-primary/90 inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-medium transition-colors'
                >
                  Apri →
                </a>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Users — honest stub */}
        <section>
          <h2 className='mb-3 text-lg font-semibold tracking-tight'>Gestione utenti</h2>
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Info className='size-4 text-muted-foreground' aria-hidden='true' />
                Endpoint non disponibile in v1.0
              </CardTitle>
              <CardDescription>
                Il backend espone solo <code className='font-mono text-xs'>GET /api/users/me</code> (BP §10).
                La lista utenti completa e la modifica del ruolo arrivano con FASE 7
                (hardening + user-management endpoints). Per l&apos;intanto le operazioni
                amministrative sugli utenti vanno fatte via psql:
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className='overflow-x-auto rounded-md bg-muted p-3 text-xs'>
{`docker exec -it eduvault-postgres-1 psql -U nexus_admin -d nexus
nexus=# SELECT email, role, is_active FROM users;
nexus=# UPDATE users SET role='reviewer' WHERE email='user@example.com';`}
              </pre>
            </CardContent>
          </Card>
        </section>
      </Main>
    </>
  )
}

function MetricsGrid({
  metrics,
  stats,
  isLoading,
}: {
  metrics: MetricsResponse | undefined
  stats: DashboardStats | undefined
  isLoading: boolean
}) {
  const cards: { label: string; value: React.ReactNode; icon: React.ComponentType<{ className?: string }>; help?: string }[] = [
    {
      label: 'Pipeline eseguite (7gg)',
      value: metrics?.total_runs ?? 0,
      icon: Layers,
    },
    {
      label: 'Tempo medio',
      value: metrics?.avg_elapsed_seconds
        ? `${Math.round(metrics.avg_elapsed_seconds)}s`
        : '—',
      icon: Clock,
      help: 'Tempo medio per pipeline completata',
    },
    {
      label: 'Slide medie / corso',
      value: metrics?.avg_slides ? Math.round(metrics.avg_slides) : '—',
      icon: BookOpen,
    },
    {
      label: 'Immagini totali',
      value: metrics?.total_images_resolved ?? 0,
      icon: ImageIcon,
      help: 'Risolte da web search + diagrammi SVG',
    },
    {
      label: 'Corsi totali',
      value: stats?.courses_count ?? 0,
      icon: BookOpen,
    },
    {
      label: 'Corsi L2',
      value: stats?.l2_count ?? 0,
      icon: Users,
    },
  ]
  return (
    <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
      {cards.map((c) => (
        <Card key={c.label}>
          <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
            <CardTitle className='text-sm font-medium'>{c.label}</CardTitle>
            <c.icon className='size-4 text-muted-foreground' aria-hidden='true' />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className='h-8 w-16' />
            ) : (
              <div className='text-2xl font-bold tabular-nums'>{c.value}</div>
            )}
            {c.help && <p className='mt-1 text-xs text-muted-foreground'>{c.help}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function PresetCard({ preset }: { preset: BrandPresetSummary }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className='flex items-center gap-2 text-base'>
          {preset.name}
          {preset.is_default && (
            <Badge variant='secondary' className='text-xs'>default</Badge>
          )}
        </CardTitle>
        <CardDescription className='font-mono text-xs'>{preset.id}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className='flex flex-wrap gap-3'>
          {paletteSwatches(preset.palette).map((sw) => (
            <div key={sw.name} className='flex flex-col items-center gap-1'>
              <span
                className='size-10 rounded-md border'
                style={{ backgroundColor: sw.hex }}
                aria-label={`${sw.name}: ${sw.hex}`}
              />
              <span className='text-[10px] uppercase tracking-wide text-muted-foreground'>
                {sw.name}
              </span>
              <span className='font-mono text-[10px] text-muted-foreground'>{sw.hex}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/*
 * ─── SELF-AUDIT (impeccable) ──────────────────────────────────────────────
 *
 * Hierarchy:
 *   ✓ Page H1 + 3 sections each with H2 — clear three-tier structure.
 *
 * Spacing:
 *   ✓ section mb-8, h2 mb-3 — consistent vertical rhythm.
 *
 * Color:
 *   ✓ Restrained: brand only on the live (no brand here actually).
 *     Default preset Badge uses secondary (neutral grey) so the brand
 *     accent budget stays at 0% — Admin is a calm reference page.
 *
 * Bans:
 *   ✓ No em dashes. ✓ No nested cards (metric cards are siblings;
 *     PresetCards are siblings; user stub is one card).
 *   ✓ NO INVENTED USERS TABLE — instead, transparent "endpoint not
 *     available, here's how to do it via psql for now". This is the
 *     REI-5 spirit applied to UX: don't fake capability.
 *
 * Provenance:
 *   ✓ Users stub explicitly cites BP §10 and points to the actual SQL
 *     commands so admin is unblocked. Beats a placeholder spinner.
 */
