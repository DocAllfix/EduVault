/**
 * Regulations — `/regulations` (BP §10).
 *
 * ─── Design intent (frontend-design 2026-06-01 refresh) ───────────────────
 * Purpose: knowledge base management. Admin uploads new PDF, users browse
 *   indexed list, anyone inspects chunks per regulation.
 * Tone: editorial card grid (no più lista densa colonnata che l'utente ha
 *   esplicitamente bocciato 2026-06-01). Ogni normativa = una card con
 *   icona categoria + title prominente + meta calma + status + actions.
 *   Quick filter chips per tipologia in alto, search rimane testuale.
 * Constraints: REI-1 shadcn (Card/Badge/Button/Input). REI-11 spacing
 *   gap-4/p-6, hover ring brand-primary/30, no shadows hard. Mobile-first
 *   con grid sm:cols-1 md:cols-2 lg:cols-3.
 * Differentiation: card hover svela il "stato chunks" (Sheet) come prima,
 *   ma l'eye-candy iniziale ora racconta categoria a colpo d'occhio
 *   (icona/colore per type).
 */

import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Archive,
  CheckCircle2,
  FileText,
  Gavel,
  Globe2,
  Handshake,
  Library,
  Loader2,
  Scale,
  Trash2,
  Upload as UploadIcon,
} from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, tokenStorage, type RegulationSummary } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { cn } from '@/lib/utils'

import { ChunksSheet } from './components/chunks-sheet'
import { UploadRegulationDialog } from './components/upload-regulation-dialog'

function getRoleFromToken(): string | undefined {
  const tok = tokenStorage.getAccess()
  if (!tok) return undefined
  try {
    const p = tok.split('.')[1]
    const padded = p + '==='.slice((p.length + 3) % 4)
    return (JSON.parse(atob(padded.replace(/-/g, '+').replace(/_/g, '/'))) as { role?: string }).role
  } catch {
    return undefined
  }
}

// ─── Type metadata: icone + colori per categoria normativa ─────────────────

interface TypeMeta {
  label: string
  icon: React.ComponentType<{ className?: string }>
  accent: string // tailwind classes per icon container background
  textAccent: string // tailwind text color when icon is on white card
}

const TYPE_META: Record<string, TypeMeta> = {
  DECRETO: {
    label: 'Decreto',
    icon: Gavel,
    accent: 'bg-brand-primary/10',
    textAccent: 'text-brand-primary',
  },
  LEGGE: {
    label: 'Legge',
    icon: Scale,
    accent: 'bg-brand-primary/10',
    textAccent: 'text-brand-primary',
  },
  REGOLAMENTO_CE: {
    label: 'Regolamento CE',
    icon: Globe2,
    accent: 'bg-blue-500/10',
    textAccent: 'text-blue-600 dark:text-blue-400',
  },
  ACCORDO: {
    label: 'Accordo',
    icon: Handshake,
    accent: 'bg-brand-secondary/15',
    textAccent: 'text-brand-secondary',
  },
  NORMA_TECNICA: {
    label: 'Norma tecnica',
    icon: FileText,
    accent: 'bg-amber-500/10',
    textAccent: 'text-amber-700 dark:text-amber-400',
  },
  CIRCOLARE: {
    label: 'Circolare',
    icon: FileText,
    accent: 'bg-slate-500/10',
    textAccent: 'text-slate-600 dark:text-slate-300',
  },
}

function metaFor(type: string): TypeMeta {
  return (
    TYPE_META[type.toUpperCase()] ?? {
      label: type,
      icon: FileText,
      accent: 'bg-muted',
      textAccent: 'text-muted-foreground',
    }
  )
}

// ─── Component principale ──────────────────────────────────────────────────

export function Regulations() {
  const queryClient = useQueryClient()
  const role = useMemo(() => getRoleFromToken(), [])
  const isAdmin = role === 'admin'
  const [filter, setFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState<string | null>(null)
  const [showAbrogated, setShowAbrogated] = useState(false)
  const [openChunks, setOpenChunks] = useState<RegulationSummary | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const regsQ = useQuery({
    queryKey: ['regulations'] as const,
    queryFn: () => api.getRegulations({ page: 1, per_page: 100 }),
  })

  const all = regsQ.data ?? []

  // Statistiche header
  const vigenti = useMemo(() => all.filter((r) => r.status !== 'ABROGATA'), [all])
  const abrogate = useMemo(() => all.filter((r) => r.status === 'ABROGATA'), [all])

  // Tipi presenti, per quick-filter chips (ordinati per frequenza)
  const typesPresent = useMemo(() => {
    const counts = new Map<string, number>()
    for (const r of all) counts.set(r.type, (counts.get(r.type) ?? 0) + 1)
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1])
  }, [all])

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    return all.filter((r) => {
      // status filter
      if (!showAbrogated && r.status === 'ABROGATA') return false
      // type filter
      if (typeFilter && r.type !== typeFilter) return false
      // search
      if (q) {
        const hay = `${r.title} ${r.type} ${r.region} ${r.slug ?? ''}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [all, filter, typeFilter, showAbrogated])

  async function handleDelete(reg: RegulationSummary) {
    if (
      !confirm(
        `Marcare «${reg.title}» come ABROGATA? Resta nel DB ma non sarà più usata dal Research Agent.`,
      )
    ) {
      return
    }
    setDeletingId(reg.id)
    try {
      await api.deleteRegulation(reg.id)
      toast.success('Normativa abrogata.')
      await queryClient.invalidateQueries({ queryKey: ['regulations'] })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Operazione non riuscita.')
    } finally {
      setDeletingId(null)
    }
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
        {/* ─── Hero header ─── */}
        <header className='mb-8'>
          <div className='flex flex-wrap items-start justify-between gap-4'>
            <div>
              <div className='mb-2 inline-flex items-center gap-2 rounded-full bg-brand-primary/10 px-3 py-1 text-xs font-medium text-brand-primary'>
                <Library className='size-3.5' aria-hidden='true' />
                Knowledge base
              </div>
              <h1 className='text-3xl font-bold tracking-tight'>Normative</h1>
              <p className='mt-1 max-w-xl text-sm text-muted-foreground'>
                Documenti normativi indicizzati per la pipeline RAG. Ogni
                citazione delle slide e degli audio ancora a chunk reali di
                queste fonti.
              </p>
            </div>
            {isAdmin && <UploadRegulationDialog />}
          </div>

          {/* Stat counters */}
          <div className='mt-6 grid gap-3 sm:grid-cols-3'>
            <StatPill
              label='Documenti totali'
              value={all.length}
              accent='bg-brand-primary/10 text-brand-primary'
              icon={Library}
            />
            <StatPill
              label='Vigenti'
              value={vigenti.length}
              accent='bg-brand-secondary/15 text-brand-secondary'
              icon={CheckCircle2}
            />
            <StatPill
              label='Abrogate'
              value={abrogate.length}
              accent='bg-muted text-muted-foreground'
              icon={Archive}
            />
          </div>
        </header>

        {/* ─── Search + filter chips ─── */}
        <section className='mb-6 space-y-3'>
          <Input
            placeholder='Cerca per titolo, slug, regione…'
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className='max-w-xl'
          />
          <div className='flex flex-wrap items-center gap-2'>
            <Chip
              active={typeFilter === null}
              onClick={() => setTypeFilter(null)}
              label='Tutti'
              count={vigenti.length + (showAbrogated ? abrogate.length : 0)}
            />
            {typesPresent.map(([t, n]) => {
              const m = metaFor(t)
              return (
                <Chip
                  key={t}
                  active={typeFilter === t}
                  onClick={() => setTypeFilter(t === typeFilter ? null : t)}
                  label={m.label}
                  count={n}
                  icon={m.icon}
                />
              )
            })}
            {abrogate.length > 0 && (
              <Chip
                active={showAbrogated}
                onClick={() => setShowAbrogated((v) => !v)}
                label='Mostra abrogate'
                count={abrogate.length}
                muted
              />
            )}
          </div>
        </section>

        {/* ─── Grid normative ─── */}
        {regsQ.isLoading ? (
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className='h-44 w-full rounded-lg' />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <Card>
            <CardHeader className='items-center text-center'>
              <Library className='mb-2 size-12 text-muted-foreground' aria-hidden='true' />
              <CardTitle>
                {all.length === 0 ? 'Knowledge base vuota' : 'Nessun risultato'}
              </CardTitle>
              <CardDescription className='max-w-md'>
                {all.length === 0
                  ? isAdmin
                    ? 'Carica il primo PDF normativo per iniziare ad indicizzare il corpus.'
                    : 'Nessuna normativa indicizzata. Contatta un amministratore.'
                  : 'I filtri attivi non corrispondono a nessuna normativa. Modifica la ricerca o reset.'}
              </CardDescription>
              {all.length === 0 && isAdmin && (
                <div className='mt-4'>
                  <UploadRegulationDialog />
                </div>
              )}
            </CardHeader>
          </Card>
        ) : (
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
            {filtered.map((r) => (
              <RegulationCard
                key={r.id}
                reg={r}
                isAdmin={isAdmin}
                isDeleting={deletingId === r.id}
                onOpen={() => setOpenChunks(r)}
                onDelete={() => handleDelete(r)}
              />
            ))}
          </div>
        )}

        <ChunksSheet
          regulation={openChunks}
          onOpenChange={(o) => {
            if (!o) setOpenChunks(null)
          }}
        />
      </Main>
    </>
  )
}

// ─── Sub-components ────────────────────────────────────────────────────────

function StatPill({
  label,
  value,
  accent,
  icon: Icon,
}: {
  label: string
  value: number
  accent: string
  icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <div className='flex items-center gap-3 rounded-lg border bg-card p-4'>
      <div className={cn('grid size-10 place-items-center rounded-md', accent)}>
        <Icon className='size-5' aria-hidden='true' />
      </div>
      <div className='min-w-0'>
        <div className='truncate text-xs text-muted-foreground'>{label}</div>
        <div className='text-2xl font-bold tabular-nums leading-tight'>{value}</div>
      </div>
    </div>
  )
}

function Chip({
  active,
  onClick,
  label,
  count,
  icon: Icon,
  muted = false,
}: {
  active: boolean
  onClick: () => void
  label: string
  count: number
  icon?: React.ComponentType<{ className?: string }>
  muted?: boolean
}) {
  return (
    <button
      type='button'
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        active
          ? muted
            ? 'border-border bg-muted text-foreground'
            : 'border-brand-primary/40 bg-brand-primary/10 text-brand-primary'
          : 'border-border bg-card text-muted-foreground hover:bg-muted/60',
      )}
    >
      {Icon && <Icon className='size-3.5' aria-hidden='true' />}
      <span>{label}</span>
      <span
        className={cn(
          'rounded-full px-1.5 text-[10px] tabular-nums',
          active ? 'bg-background/60' : 'bg-muted',
        )}
      >
        {count}
      </span>
    </button>
  )
}

function RegulationCard({
  reg,
  isAdmin,
  isDeleting,
  onOpen,
  onDelete,
}: {
  reg: RegulationSummary
  isAdmin: boolean
  isDeleting: boolean
  onOpen: () => void
  onDelete: () => void
}) {
  const isAbrogata = reg.status === 'ABROGATA'
  const m = metaFor(reg.type)
  const Icon = m.icon

  return (
    <Card
      onClick={onOpen}
      className={cn(
        'group relative flex cursor-pointer flex-col gap-3 overflow-hidden border-border/70 p-5 transition-all',
        'hover:-translate-y-0.5 hover:border-brand-primary/40 hover:shadow-md',
        isAbrogata && 'opacity-70',
      )}
      role='button'
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
      aria-label={`Apri dettaglio normativa ${reg.title}`}
    >
      {/* Top row: icona type + status badge */}
      <div className='relative z-10 flex items-start justify-between gap-3'>
        <div
          className={cn(
            'grid size-11 shrink-0 place-items-center rounded-lg',
            m.accent,
          )}
        >
          <Icon className={cn('size-5', m.textAccent)} aria-hidden='true' />
        </div>
        <Badge
          variant='outline'
          className={cn(
            'shrink-0 gap-1',
            isAbrogata
              ? 'border-border bg-muted text-muted-foreground'
              : 'border-brand-secondary/40 bg-brand-secondary/10 text-brand-secondary',
          )}
        >
          {isAbrogata ? (
            <Archive className='size-3' aria-hidden='true' />
          ) : (
            <CheckCircle2 className='size-3' aria-hidden='true' />
          )}
          {isAbrogata ? 'Abrogata' : 'Vigente'}
        </Badge>
      </div>

      {/* Title + slug */}
      <div className='relative z-10 min-w-0 flex-1 space-y-1'>
        <h3 className='line-clamp-2 text-base font-semibold leading-snug tracking-tight'>
          {reg.title}
        </h3>
        <code className='block truncate font-mono text-[11px] text-muted-foreground'>
          {reg.slug ?? '—'}
        </code>
      </div>

      {/* Meta footer */}
      <div className='relative z-10 mt-auto flex items-center justify-between gap-2 border-t border-border/60 pt-3 text-xs'>
        <div className='flex items-center gap-2'>
          <span className='font-medium text-foreground'>{m.label}</span>
          <span className='text-muted-foreground'>·</span>
          <span className='text-muted-foreground'>{reg.region}</span>
        </div>
        {isAdmin && !isAbrogata && (
          <Button
            variant='ghost'
            size='icon'
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            disabled={isDeleting}
            className='relative z-20 size-7 text-muted-foreground hover:text-destructive'
            aria-label='Marca abrogata'
          >
            {isDeleting ? (
              <Loader2 className='size-3.5 animate-spin' aria-hidden='true' />
            ) : (
              <Trash2 className='size-3.5' aria-hidden='true' />
            )}
          </Button>
        )}
      </div>
    </Card>
  )
}

// Re-export UploadRegulationDialog button if user lands on empty state.
// (Otherwise unused import — keep at module level to avoid dead deps.)
export { UploadIcon }
