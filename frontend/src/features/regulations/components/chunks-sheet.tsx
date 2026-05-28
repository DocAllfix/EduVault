/**
 * Side sheet that lists the chunks of a regulation.
 *
 * Server-paginated via `api.getChunks(id, {page, per_page})`. The
 * paginator is intentionally simple (Prev/Next) — we don't know the
 * total count without a separate endpoint, and `len(rows) < per_page`
 * is a reliable "last page" signal that doesn't lie.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, BookOpen, ChevronDown, ChevronRight } from 'lucide-react'

import { api, type RegulationSummary } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'

type ChunksSheetProps = {
  regulation: RegulationSummary | null
  onOpenChange: (open: boolean) => void
}

const PAGE_SIZE = 25

export function ChunksSheet({ regulation, onOpenChange }: ChunksSheetProps) {
  const [page, setPage] = useState(1)
  const [linkedOpen, setLinkedOpen] = useState(true)
  const open = regulation !== null

  const chunksQ = useQuery({
    queryKey: ['chunks', regulation?.id, page] as const,
    queryFn: () => api.getChunks(regulation!.id, { page, per_page: PAGE_SIZE }),
    enabled: open && !!regulation?.id,
  })

  // Carichiamo i corsi linkati una volta sola (non paginati): tipicamente
  // < 50 per normativa. Usiamo slug se disponibile (URL piu' parlante), altrimenti UUID.
  const linkedQ = useQuery({
    queryKey: ['linked-courses', regulation?.slug ?? regulation?.id] as const,
    queryFn: () =>
      api.getLinkedCourses(regulation?.slug ?? regulation!.id),
    enabled: open && !!regulation,
  })

  const isLast = (chunksQ.data?.length ?? 0) < PAGE_SIZE

  return (
    <Sheet
      open={open}
      onOpenChange={(o) => {
        if (!o) setPage(1)
        onOpenChange(o)
      }}
    >
      <SheetContent className='w-full sm:max-w-xl'>
        <SheetHeader>
          <SheetTitle>{regulation?.title ?? '—'}</SheetTitle>
          <SheetDescription>
            {regulation?.type} · {regulation?.region} · slug{' '}
            <code className='font-mono text-xs'>{regulation?.slug ?? '—'}</code>
          </SheetDescription>
        </SheetHeader>

        <div className='flex h-full flex-col gap-3 px-4 pb-4'>
          {/* Corsi che usano questa normativa - collassabile, conteggio inline.
              Provenienza del link mostrata come piccola etichetta (VAA-b). */}
          <div className='rounded-md border'>
            <button
              type='button'
              onClick={() => setLinkedOpen((o) => !o)}
              className='hover:bg-muted/50 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors'
              aria-expanded={linkedOpen}
            >
              {linkedOpen ? (
                <ChevronDown className='size-4' aria-hidden='true' />
              ) : (
                <ChevronRight className='size-4' aria-hidden='true' />
              )}
              <BookOpen className='size-4' aria-hidden='true' />
              <span className='font-medium'>Corsi che usano questa normativa</span>
              <Badge variant='secondary' className='ms-auto'>
                {linkedQ.isLoading ? '…' : (linkedQ.data?.length ?? 0)}
              </Badge>
            </button>

            {linkedOpen && (
              <div className='space-y-1.5 border-t px-3 py-2'>
                {linkedQ.isLoading ? (
                  <Skeleton className='h-12 w-full' />
                ) : linkedQ.isError ? (
                  <p className='text-destructive text-xs'>
                    Impossibile caricare i corsi collegati.
                  </p>
                ) : !linkedQ.data?.length ? (
                  <p className='text-muted-foreground text-xs'>
                    Nessun corso del catalogo dichiara ancora questa normativa
                    come riferimento.
                  </p>
                ) : (
                  linkedQ.data.map((lc) => (
                    <div
                      key={lc.course_type_slug}
                      className='flex items-start justify-between gap-2 rounded-sm py-1 text-sm'
                    >
                      <div className='min-w-0 flex-1'>
                        <div className='truncate font-medium'>{lc.title}</div>
                        <div className='text-muted-foreground mt-0.5 flex flex-wrap items-center gap-1.5 text-xs'>
                          <span>{lc.hours}h</span>
                          <span>·</span>
                          <span>{lc.target}</span>
                          {lc.link_source !== 'scrape' && (
                            <>
                              <span>·</span>
                              <Badge
                                variant='outline'
                                className='border-amber-400/50 bg-amber-50/40 text-[10px] text-amber-700'
                                title={lc.link_notes ?? undefined}
                              >
                                link: {lc.link_source}
                              </Badge>
                            </>
                          )}
                        </div>
                      </div>
                      <Badge
                        variant='outline'
                        className={
                          lc.course_approved
                            ? 'border-brand-secondary/40 bg-brand-secondary/10 text-brand-secondary'
                            : 'border-border bg-muted text-muted-foreground'
                        }
                      >
                        {lc.course_approved ? 'Approvato' : 'In attesa'}
                      </Badge>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <div className='flex items-center justify-between text-sm text-muted-foreground'>
            <span>Pagina {page}</span>
            <div className='flex gap-1'>
              <Button
                variant='outline'
                size='sm'
                disabled={page === 1 || chunksQ.isLoading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ArrowLeft className='size-3.5' aria-hidden='true' />
              </Button>
              <Button
                variant='outline'
                size='sm'
                disabled={isLast || chunksQ.isLoading}
                onClick={() => setPage((p) => p + 1)}
              >
                <ArrowRight className='size-3.5' aria-hidden='true' />
              </Button>
            </div>
          </div>

          <div className='flex-1 space-y-3 overflow-y-auto'>
            {chunksQ.isLoading ? (
              [...Array(5)].map((_, i) => <Skeleton key={i} className='h-24 w-full' />)
            ) : !chunksQ.data?.length ? (
              <p className='text-sm text-muted-foreground'>
                Nessun chunk in questa pagina.
              </p>
            ) : (
              chunksQ.data.map((c) => (
                <div key={c.id} className='rounded-md border p-3'>
                  <div className='mb-2 flex flex-wrap items-center gap-2 text-xs'>
                    <Badge variant='outline' className='font-mono'>
                      {c.hierarchy_path}
                    </Badge>
                    <Badge variant='secondary'>{c.chunk_type}</Badge>
                    {c.tags.map((t) => (
                      <Badge key={t} variant='outline'>
                        {t}
                      </Badge>
                    ))}
                  </div>
                  <p className='text-sm leading-relaxed'>{c.body}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
