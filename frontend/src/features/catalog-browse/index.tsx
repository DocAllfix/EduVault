/**
 * CatalogBrowse — `/catalog` (F11 Issue 3 / D-229).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Versione browse-only del catalogo corsi, accessibile a TUTTI gli utenti
 * autenticati (non solo admin). Mostra esclusivamente entries APPROVATE
 * (backend forza `approved_only=True`).
 *
 * Differenza dalla pagina admin (`/admin/catalog`):
 * - NESSUN bulk checkbox, NESSUN bottone approve/unapprove, NESSUN edit
 * - AGGIUNTO bottone "Crea corso da questo" per riga (CTA primary) che
 *   redirige al wizard con `?course_type=<slug>` pre-compilato
 *
 * Pattern visivo: tabella shadcn dense + filtri (search + target) sopra,
 * Dialog dettaglio moduli su click riga. Coerente con `/regulations` e
 * `/admin/catalog` ma più calmo (no azioni distruttive visibili).
 *
 * REI-1: shadcn Table/Card/Dialog/Badge/Button/Input. Zero design from scratch.
 */

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { BookOpen, ChevronRight, Loader2, Plus, Search } from 'lucide-react'

import {
  api,
  ApiError,
  type CatalogEntryDetail,
  type CatalogEntrySummary,
} from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { JobsBadge } from '@/components/jobs-badge'

const TARGET_LABELS: Record<string, string> = {
  discente: 'Discente',
  formatore: 'Formatore',
  rspp: 'RSPP',
  preposti: 'Preposti',
  dirigenti: 'Dirigenti',
}

function targetLabel(t: string): string {
  return TARGET_LABELS[t] ?? t
}

export function CatalogBrowse() {
  const navigate = useNavigate()
  const [searchInput, setSearchInput] = useState('')
  const [targetFilter, setTargetFilter] = useState<string>('all')
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)

  const listQ = useQuery({
    queryKey: ['public-catalog', targetFilter, searchInput] as const,
    queryFn: () =>
      api.getPublicCatalog({
        per_page: 100,
        target: targetFilter === 'all' ? undefined : targetFilter,
        search: searchInput.trim() || undefined,
      }),
  })

  const detailQ = useQuery({
    queryKey: ['public-catalog-entry', selectedSlug] as const,
    queryFn: () =>
      selectedSlug ? api.getPublicCatalogEntry(selectedSlug) : null,
    enabled: !!selectedSlug,
  })

  const entries = useMemo(() => listQ.data?.entries ?? [], [listQ.data])

  function handleCreateFromCatalog(entry: CatalogEntrySummary) {
    navigate({
      to: '/courses/new',
      search: { course_type: entry.slug },
    })
  }

  return (
    <>
      <Header>
        <h1 className='text-base font-semibold'>Catalogo Corsi</h1>
        <div className='ml-auto flex items-center gap-2'>
          <JobsBadge />
          <HelpButton />
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>

      <Main>
        {/* Page heading */}
        <div className='mb-6 flex items-end justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>Catalogo Corsi</h1>
            <p className='text-sm text-muted-foreground'>
              Sfoglia i tipi di corso disponibili. Clicca una riga per i moduli
              e usa <strong>Crea corso da questo</strong> per partire dal wizard
              precompilato.
            </p>
          </div>
        </div>

        {/* Filtri */}
        <Card className='mb-4'>
          <CardContent className='flex flex-col gap-3 p-4 sm:flex-row sm:items-center'>
            <div className='relative flex-1'>
              <Search
                className='text-muted-foreground absolute left-3 top-1/2 size-4 -translate-y-1/2'
                aria-hidden='true'
              />
              <Input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder='Cerca per titolo o slug…'
                className='pl-9'
              />
            </div>
            <Select value={targetFilter} onValueChange={setTargetFilter}>
              <SelectTrigger className='w-full sm:w-48'>
                <SelectValue placeholder='Target' />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>Tutti i target</SelectItem>
                {Object.entries(TARGET_LABELS).map(([slug, label]) => (
                  <SelectItem key={slug} value={slug}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Tabella */}
        <Card>
          <CardHeader className='border-b'>
            <CardTitle className='flex items-center gap-2 text-base'>
              <BookOpen className='size-4' aria-hidden='true' />
              Corsi disponibili
              <Badge variant='outline' className='ml-2 text-xs font-normal'>
                {listQ.data?.total ?? 0}
              </Badge>
            </CardTitle>
            <CardDescription>
              Solo corsi approvati dall'amministrazione sono mostrati qui.
            </CardDescription>
          </CardHeader>
          <CardContent className='p-0'>
            {listQ.isLoading ? (
              <div className='space-y-2 p-4'>
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className='h-10 w-full' />
                ))}
              </div>
            ) : listQ.isError ? (
              <div className='text-muted-foreground p-6 text-center text-sm'>
                {listQ.error instanceof ApiError
                  ? listQ.error.message
                  : 'Impossibile caricare il catalogo.'}
              </div>
            ) : entries.length === 0 ? (
              <div className='text-muted-foreground p-6 text-center text-sm'>
                Nessun corso disponibile per i filtri correnti.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Titolo</TableHead>
                    <TableHead className='hidden sm:table-cell'>Target</TableHead>
                    <TableHead className='hidden md:table-cell'>Durata</TableHead>
                    <TableHead className='hidden lg:table-cell'>
                      Normative
                    </TableHead>
                    <TableHead className='text-right'>Azioni</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map((e) => (
                    <TableRow
                      key={e.slug}
                      className='hover:bg-muted/40 cursor-pointer'
                      onClick={() => setSelectedSlug(e.slug)}
                    >
                      <TableCell>
                        <div className='font-medium'>{e.title}</div>
                        <div className='text-muted-foreground font-mono text-xs'>
                          {e.slug}
                        </div>
                      </TableCell>
                      <TableCell className='hidden sm:table-cell'>
                        <Badge variant='outline'>{targetLabel(e.target)}</Badge>
                      </TableCell>
                      <TableCell className='text-muted-foreground hidden text-sm tabular-nums md:table-cell'>
                        {e.hours}h
                      </TableCell>
                      <TableCell className='hidden lg:table-cell'>
                        <div className='flex flex-wrap gap-1'>
                          {e.regulation_slugs.slice(0, 2).map((rs) => (
                            <Badge
                              key={rs}
                              variant='secondary'
                              className='font-mono text-[10px]'
                            >
                              {rs}
                            </Badge>
                          ))}
                          {e.regulation_slugs.length > 2 && (
                            <Badge
                              variant='secondary'
                              className='text-[10px]'
                            >
                              +{e.regulation_slugs.length - 2}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className='text-right'>
                        <Button
                          size='sm'
                          onClick={(ev) => {
                            ev.stopPropagation()
                            handleCreateFromCatalog(e)
                          }}
                          className='h-7 gap-1.5 text-xs'
                        >
                          <Plus className='size-3.5' aria-hidden='true' />
                          Crea
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </Main>

      {/* Dialog dettaglio moduli */}
      <Dialog
        open={selectedSlug !== null}
        onOpenChange={(o) => {
          if (!o) setSelectedSlug(null)
        }}
      >
        <DialogContent className='sm:max-w-2xl'>
          <DialogHeader>
            <DialogTitle>{detailQ.data?.title ?? 'Dettaglio corso'}</DialogTitle>
            <DialogDescription className='font-mono text-xs'>
              {detailQ.data?.slug}
            </DialogDescription>
          </DialogHeader>
          {detailQ.isLoading ? (
            <div className='flex items-center justify-center py-8'>
              <Loader2 className='size-5 animate-spin' aria-hidden='true' />
            </div>
          ) : detailQ.data ? (
            <CatalogEntryDetailBody
              entry={detailQ.data}
              onCreate={() => {
                if (detailQ.data) {
                  handleCreateFromCatalog(detailQ.data)
                  setSelectedSlug(null)
                }
              }}
            />
          ) : (
            <p className='text-muted-foreground text-sm'>
              Nessun dato disponibile.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

function CatalogEntryDetailBody({
  entry,
  onCreate,
}: {
  entry: CatalogEntryDetail
  onCreate: () => void
}) {
  return (
    <div className='space-y-4'>
      <dl className='grid grid-cols-2 gap-x-4 gap-y-2 text-sm'>
        <dt className='text-muted-foreground'>Target</dt>
        <dd>
          <Badge variant='outline'>{targetLabel(entry.target)}</Badge>
        </dd>
        <dt className='text-muted-foreground'>Durata</dt>
        <dd className='font-medium tabular-nums'>{entry.hours}h</dd>
        <dt className='text-muted-foreground'>Normative</dt>
        <dd className='flex flex-wrap gap-1'>
          {entry.regulation_slugs.map((rs) => (
            <Badge
              key={rs}
              variant='secondary'
              className='font-mono text-[10px]'
            >
              {rs}
            </Badge>
          ))}
        </dd>
      </dl>

      {entry.modules.length > 0 && (
        <div>
          <h4 className='mb-2 text-sm font-semibold'>
            Moduli ({entry.modules.length})
          </h4>
          <ol className='space-y-2'>
            {entry.modules.map((m) => (
              <li
                key={m.ordinal}
                className='border-border bg-muted/30 flex items-start gap-3 rounded-md border p-3'
              >
                <div className='text-muted-foreground tabular-nums text-xs font-semibold'>
                  M{m.ordinal}
                </div>
                <div className='flex-1'>
                  <p className='text-sm font-medium leading-tight'>
                    {m.title}
                  </p>
                  {m.normative_refs && m.normative_refs.length > 0 && (
                    <div className='mt-1.5 flex flex-wrap gap-1'>
                      {m.normative_refs.map((nr) => (
                        <Badge
                          key={nr}
                          variant='outline'
                          className='font-mono text-[10px]'
                        >
                          {nr}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      <Button onClick={onCreate} className='w-full gap-2' size='lg'>
        <Plus className='size-4' aria-hidden='true' />
        Crea corso da questo
        <ChevronRight className='ml-auto size-4' aria-hidden='true' />
      </Button>
    </div>
  )
}
