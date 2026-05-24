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
import { ArrowLeft, ArrowRight } from 'lucide-react'

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
  const open = regulation !== null

  const chunksQ = useQuery({
    queryKey: ['chunks', regulation?.id, page] as const,
    queryFn: () => api.getChunks(regulation!.id, { page, per_page: PAGE_SIZE }),
    enabled: open && !!regulation?.id,
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
