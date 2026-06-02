/**
 * Catalog Review — `/admin/catalog` (F1 D8 vast-hopping, 2026-05-31).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: pagina admin per la review del catalog course_type. Gate VAA-c:
 *   un entry NON è disponibile per la generazione finche' un admin non lo ha
 *   approvato esplicitamente (stamp `approved_at`). Il sistema propone,
 *   l'umano valida. Da qui il bottone "Approva" per riga + bulk approve.
 * Tone: tabella shadcn, header summary 3-card (totali / approvati / pending),
 *   filtri (search + target + only-approved toggle), checkbox bulk, dialog
 *   dettaglio con moduli. Brand C.F.P. Montessori.
 * Constraints: REI-1 shadcn (Table/Card/Badge/Checkbox/Select/Dialog/Switch).
 *   Pagina read+approve only: edit dei campi (title/hours/regulation_slugs)
 *   resta backend-ready ma fuori scope MVP UI (utente puo' editare DB
 *   direttamente o aspettare F1.next).
 */

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Layers,
  Loader2,
  ShieldCheck,
  X,
} from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { toast } from 'sonner'

import {
  api,
  ApiError,
  type CatalogEntrySummary,
  type CatalogSummaryByTarget,
} from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { HelpButton } from '@/lib/onboarding/HelpButton'
import { cn } from '@/lib/utils'

const TARGETS = [
  'lavoratori',
  'preposti',
  'dirigenti',
  'rspp',
  'aspp',
  'rls',
  'datore_lavoro',
  'formatore',
  'primo_soccorso',
  'antincendio',
  'haccp',
  'coordinatore_cantieri',
  'pes_pav',
  'generale',
] as const

const ALL_TARGETS = '__ALL__'
const PAGE_SIZE = 50

export function CatalogReview() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [targetFilter, setTargetFilter] = useState<string>(ALL_TARGETS)
  const [approvedOnly, setApprovedOnly] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [detailSlug, setDetailSlug] = useState<string | null>(null)

  // Summary header (totali + per target)
  const summaryQ = useQuery({
    queryKey: ['admin', 'catalog', 'summary'] as const,
    queryFn: () => api.adminGetCatalogSummary(),
  })

  // Lista paginata
  const listQ = useQuery({
    queryKey: [
      'admin',
      'catalog',
      'list',
      page,
      search,
      targetFilter,
      approvedOnly,
    ] as const,
    queryFn: () =>
      api.adminListCatalog({
        page,
        per_page: PAGE_SIZE,
        approved_only: approvedOnly,
        target: targetFilter === ALL_TARGETS ? undefined : targetFilter,
        search: search.trim() || undefined,
      }),
  })

  // Dettaglio entry (lazy quando si apre dialog)
  const detailQ = useQuery({
    queryKey: ['admin', 'catalog', 'detail', detailSlug] as const,
    queryFn: () => api.adminGetCatalogEntry(detailSlug!),
    enabled: detailSlug !== null,
  })

  const approveMut = useMutation({
    mutationFn: (slug: string) => api.adminApproveCatalogEntry(slug),
    onSuccess: async (entry) => {
      toast.success(`Approvato: ${entry.title}`)
      await queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? e.message : 'Approvazione non riuscita.',
      ),
  })

  const unapproveMut = useMutation({
    mutationFn: (slug: string) => api.adminUnapproveCatalogEntry(slug),
    onSuccess: async (entry) => {
      toast.warning(`Approval revocata: ${entry.title}`)
      await queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : 'Revoca non riuscita.'),
  })

  const bulkApproveMut = useMutation({
    mutationFn: (slugs: string[]) => api.adminBulkApproveCatalog(slugs),
    onSuccess: async (res) => {
      toast.success(`${res.approved_count} entries approvate.`)
      setSelected(new Set())
      await queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] })
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? e.message : 'Approve bulk non riuscito.',
      ),
  })

  const entries = listQ.data?.entries ?? []
  const total = listQ.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function toggleSelect(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  function toggleSelectAll() {
    if (selected.size === entries.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(entries.map((e) => e.slug)))
    }
  }

  const selectedPendingCount = useMemo(() => {
    let n = 0
    for (const e of entries) {
      if (selected.has(e.slug) && !e.approved_at) n++
    }
    return n
  }, [selected, entries])

  function bulkApproveSelected() {
    const slugs = entries
      .filter((e) => selected.has(e.slug) && !e.approved_at)
      .map((e) => e.slug)
    if (slugs.length === 0) {
      toast.info('Seleziona almeno 1 entry non approvata.')
      return
    }
    bulkApproveMut.mutate(slugs)
  }

  function clearFilters() {
    setSearch('')
    setTargetFilter(ALL_TARGETS)
    setApprovedOnly(false)
    setPage(1)
  }

  const hasFilters =
    search.trim() !== '' || targetFilter !== ALL_TARGETS || approvedOnly

  return (
    <>
      <Header>
        <Button asChild variant="ghost" size="sm">
          <Link to="/admin">
            <ArrowLeft className="mr-2 h-4 w-4" /> Admin
          </Link>
        </Button>
        <div className="ml-auto flex items-center gap-2">
          <HelpButton />
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>

      <Main>
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Catalogo corsi</h1>
            <p className="text-muted-foreground text-sm">
              Review delle{' '}
              <span className="font-medium">tipologie di corso</span> disponibili
              per la generazione. Ogni entry deve essere approvata da un admin
              prima che diventi selezionabile nel wizard.
            </p>
          </div>

          {/* Summary header — 3 card numeri + breakdown per target */}
          <div className="grid gap-3 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-wide">
                  Totale entries
                </CardDescription>
                <CardTitle className="flex items-center gap-2 text-3xl">
                  {summaryQ.isLoading ? (
                    <Skeleton className="h-8 w-12" />
                  ) : (
                    summaryQ.data?.total ?? '—'
                  )}
                  <Layers className="text-muted-foreground size-5" aria-hidden="true" />
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-wide">
                  Approvate
                </CardDescription>
                <CardTitle className="flex items-center gap-2 text-3xl">
                  {summaryQ.isLoading ? (
                    <Skeleton className="h-8 w-12" />
                  ) : (
                    <span className="text-brand-secondary">
                      {summaryQ.data?.approved ?? '—'}
                    </span>
                  )}
                  <ShieldCheck
                    className="text-brand-secondary/80 size-5"
                    aria-hidden="true"
                  />
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-wide">
                  In attesa
                </CardDescription>
                <CardTitle className="flex items-center gap-2 text-3xl">
                  {summaryQ.isLoading ? (
                    <Skeleton className="h-8 w-12" />
                  ) : (
                    <span
                      className={cn(
                        summaryQ.data?.pending
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-muted-foreground',
                      )}
                    >
                      {summaryQ.data?.pending ?? '—'}
                    </span>
                  )}
                  <Clock className="text-amber-500/80 size-5" aria-hidden="true" />
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {/* Breakdown per target (chip riepilogativi) */}
          {summaryQ.data && summaryQ.data.by_target.length > 0 && (
            <div className="border-border rounded-md border p-3">
              <div className="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide">
                Per target
              </div>
              <div className="flex flex-wrap gap-1.5">
                {summaryQ.data.by_target.map((t: CatalogSummaryByTarget) => (
                  <button
                    key={t.target}
                    type="button"
                    onClick={() => {
                      setTargetFilter(t.target)
                      setPage(1)
                    }}
                    className={cn(
                      'border-border hover:bg-muted/60 inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors',
                      targetFilter === t.target &&
                        'border-brand-primary bg-brand-primary/10 text-brand-primary',
                    )}
                    aria-label={`Filtra per target ${t.target}`}
                  >
                    <span className="font-medium">{t.target}</span>
                    <span className="text-muted-foreground">
                      {t.n_approved}/{t.n_total}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Filtri + bulk action */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-1 min-w-[200px] items-center gap-2">
              <Input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
                placeholder="Cerca per slug o titolo…"
                className="max-w-md"
                aria-label="Cerca"
              />
              <Select
                value={targetFilter}
                onValueChange={(v) => {
                  setTargetFilter(v)
                  setPage(1)
                }}
              >
                <SelectTrigger className="w-[180px]" aria-label="Filtra per target">
                  <SelectValue placeholder="Tutti i target" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_TARGETS}>Tutti i target</SelectItem>
                  {TARGETS.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex items-center gap-2">
                <Switch
                  id="approved-only"
                  checked={approvedOnly}
                  onCheckedChange={(c) => {
                    setApprovedOnly(c)
                    setPage(1)
                  }}
                />
                <label
                  htmlFor="approved-only"
                  className="text-muted-foreground cursor-pointer text-xs"
                >
                  Solo approvate
                </label>
              </div>
              {hasFilters && (
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  <X className="size-3.5" /> Reset
                </Button>
              )}
            </div>
            <Button
              size="sm"
              onClick={bulkApproveSelected}
              disabled={
                selectedPendingCount === 0 || bulkApproveMut.isPending
              }
            >
              {bulkApproveMut.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Check className="size-3.5" />
              )}
              Approva selezionate
              {selectedPendingCount > 0 && (
                <Badge variant="secondary" className="ms-1.5">
                  {selectedPendingCount}
                </Badge>
              )}
            </Button>
          </div>

          {/* Tabella */}
          <div className="border-border rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      checked={
                        entries.length > 0 &&
                        selected.size === entries.length
                      }
                      onCheckedChange={toggleSelectAll}
                      aria-label="Seleziona tutti"
                    />
                  </TableHead>
                  <TableHead>Corso</TableHead>
                  <TableHead className="w-[120px]">Target</TableHead>
                  <TableHead className="w-[80px] text-right">Ore</TableHead>
                  <TableHead className="w-[80px] text-center">Moduli</TableHead>
                  <TableHead className="w-[120px]">Origine</TableHead>
                  <TableHead className="w-[120px]">Stato</TableHead>
                  <TableHead className="w-[180px] text-right">Azioni</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {listQ.isLoading &&
                  Array.from({ length: 6 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={8}>
                        <Skeleton className="h-8 w-full" />
                      </TableCell>
                    </TableRow>
                  ))}
                {!listQ.isLoading && entries.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={8}
                      className="text-muted-foreground py-8 text-center text-sm"
                    >
                      {hasFilters
                        ? 'Nessuna entry corrisponde ai filtri.'
                        : 'Nessuna entry nel catalog. Importa dati via script di scraping.'}
                    </TableCell>
                  </TableRow>
                )}
                {entries.map((e) => (
                  <CatalogRow
                    key={e.slug}
                    entry={e}
                    selected={selected.has(e.slug)}
                    onToggleSelect={() => toggleSelect(e.slug)}
                    onOpenDetail={() => setDetailSlug(e.slug)}
                    onApprove={() => approveMut.mutate(e.slug)}
                    onUnapprove={() => unapproveMut.mutate(e.slug)}
                    busy={
                      approveMut.isPending && approveMut.variables === e.slug ||
                      unapproveMut.isPending && unapproveMut.variables === e.slug
                    }
                  />
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Paginazione */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                Pagina {page} di {totalPages} · {total} entries totali
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Precedente
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Successiva
                </Button>
              </div>
            </div>
          )}

          {/* Dialog dettaglio modulo */}
          <Dialog
            open={detailSlug !== null}
            onOpenChange={(o) => !o && setDetailSlug(null)}
          >
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>
                  {detailQ.data?.title ?? detailSlug ?? 'Dettaglio'}
                </DialogTitle>
                <DialogDescription>
                  {detailQ.data && (
                    <span className="font-mono text-xs">
                      slug: {detailQ.data.slug}
                    </span>
                  )}
                </DialogDescription>
              </DialogHeader>

              {detailQ.isLoading && (
                <div className="space-y-2">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-32 w-full" />
                </div>
              )}

              {detailQ.data && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-muted-foreground text-xs uppercase tracking-wide">
                        Target
                      </div>
                      <div className="font-medium">{detailQ.data.target}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground text-xs uppercase tracking-wide">
                        Durata
                      </div>
                      <div className="font-medium">{detailQ.data.hours} ore</div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-muted-foreground text-xs uppercase tracking-wide">
                        Normative riferimento
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {detailQ.data.regulation_slugs.length === 0 ? (
                          <span className="text-muted-foreground text-xs">
                            Nessuna
                          </span>
                        ) : (
                          detailQ.data.regulation_slugs.map((s) => (
                            <Badge
                              key={s}
                              variant="outline"
                              className="font-mono text-[10px]"
                            >
                              {s}
                            </Badge>
                          ))
                        )}
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <h3 className="text-sm font-semibold">
                        Moduli ({detailQ.data.modules.length})
                      </h3>
                      <Badge variant="outline" className="text-[10px]">
                        Origine: {detailQ.data.source}
                      </Badge>
                    </div>
                    <div className="max-h-72 space-y-1.5 overflow-y-auto">
                      {detailQ.data.modules.length === 0 ? (
                        <p className="text-muted-foreground text-xs">
                          Nessun modulo definito.
                        </p>
                      ) : (
                        detailQ.data.modules.map((m) => (
                          <div
                            key={m.id}
                            className="border-border rounded-md border p-2 text-sm"
                          >
                            <div className="flex items-baseline gap-2">
                              <Badge variant="secondary" className="text-[10px]">
                                {m.ordinal}
                              </Badge>
                              <span className="font-medium">{m.title}</span>
                            </div>
                            {m.normative_refs.length > 0 && (
                              <div className="ms-7 mt-1 flex flex-wrap gap-1">
                                {m.normative_refs.map((r) => (
                                  <Badge
                                    key={r}
                                    variant="outline"
                                    className="font-mono text-[10px]"
                                  >
                                    {r}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="border-border flex items-center justify-between rounded-md border p-3">
                    <div>
                      <div className="text-xs font-semibold">Stato approvazione</div>
                      {detailQ.data.approved_at ? (
                        <div className="text-brand-secondary mt-0.5 text-xs">
                          ✓ Approvato il{' '}
                          {new Date(detailQ.data.approved_at).toLocaleString('it-IT')}
                        </div>
                      ) : (
                        <div className="mt-0.5 text-xs text-amber-700 dark:text-amber-400">
                          In attesa di approvazione
                        </div>
                      )}
                    </div>
                    {detailQ.data.approved_at ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => unapproveMut.mutate(detailQ.data!.slug)}
                        disabled={unapproveMut.isPending}
                      >
                        Revoca
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => approveMut.mutate(detailQ.data!.slug)}
                        disabled={approveMut.isPending}
                      >
                        {approveMut.isPending ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <Check className="size-3.5" />
                        )}
                        Approva
                      </Button>
                    )}
                  </div>
                </div>
              )}

              <DialogFooter>
                <Button variant="ghost" onClick={() => setDetailSlug(null)}>
                  Chiudi
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </Main>
    </>
  )
}

// ─── Row component ──────────────────────────────────────────────────────────

interface RowProps {
  entry: CatalogEntrySummary
  selected: boolean
  onToggleSelect: () => void
  onOpenDetail: () => void
  onApprove: () => void
  onUnapprove: () => void
  busy: boolean
}

function CatalogRow({
  entry,
  selected,
  onToggleSelect,
  onOpenDetail,
  onApprove,
  onUnapprove,
  busy,
}: RowProps) {
  const approved = entry.approved_at !== null && entry.approved_at !== undefined
  return (
    <TableRow className={cn(selected && 'bg-muted/30')}>
      <TableCell>
        <Checkbox
          checked={selected}
          onCheckedChange={onToggleSelect}
          aria-label={`Seleziona ${entry.slug}`}
        />
      </TableCell>
      <TableCell>
        <button
          type="button"
          onClick={onOpenDetail}
          className="text-left hover:underline"
        >
          <div className="font-medium leading-tight">{entry.title}</div>
          <code className="text-muted-foreground text-[10px] font-mono">
            {entry.slug}
          </code>
        </button>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="font-mono text-[10px]">
          {entry.target}
        </Badge>
      </TableCell>
      <TableCell className="text-right tabular-nums">{entry.hours}h</TableCell>
      <TableCell className="text-center tabular-nums">{entry.n_modules}</TableCell>
      <TableCell>
        <Badge
          variant="outline"
          className={cn(
            'text-[10px]',
            entry.source === 'scraped' && 'border-sky-300/40 bg-sky-50/40 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300',
            entry.source === 'manual' && 'border-purple-300/40 bg-purple-50/40 text-purple-700 dark:bg-purple-500/10 dark:text-purple-300',
            entry.source === 'imported_v1' && 'border-amber-300/40 bg-amber-50/40 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
          )}
        >
          {entry.source}
        </Badge>
      </TableCell>
      <TableCell>
        {approved ? (
          <Badge
            variant="outline"
            className="border-brand-secondary/40 bg-brand-secondary/10 text-brand-secondary text-[10px]"
          >
            <CheckCircle2 className="me-1 size-3" />
            Approvato
          </Badge>
        ) : (
          <Badge
            variant="outline"
            className="border-amber-400/50 bg-amber-50/40 text-[10px] text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
          >
            <Clock className="me-1 size-3" />
            In attesa
          </Badge>
        )}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-1.5">
          {approved ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[11px]"
              onClick={onUnapprove}
              disabled={busy}
            >
              {busy ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <X className="size-3" />
              )}
              Revoca
            </Button>
          ) : (
            <Button
              size="sm"
              className="h-7 px-2 text-[11px]"
              onClick={onApprove}
              disabled={busy}
            >
              {busy ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Check className="size-3" />
              )}
              Approva
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[11px]"
            onClick={onOpenDetail}
          >
            <ChevronDown className="size-3" />
            Moduli
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}
