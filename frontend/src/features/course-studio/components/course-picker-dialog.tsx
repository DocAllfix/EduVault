/**
 * CoursePickerDialog — modal "Apri Course Studio".
 *
 * Apre un dialog con i corsi editabili e, alla selezione, naviga al loro
 * Course Studio. Pensato per il nuovo entry-point sidebar (Course Studio)
 * e riutilizzabile dalla dashboard come "Apri uno dei tuoi corsi in Studio".
 *
 * Filtri: solo corsi che hanno slide_contents_json (status != 'queued' e
 * != 'failed'), perché il backend ritorna 409 sul GET /slides per quelli
 * vuoti. Mostra titolo, tipo, durata, status, badge "modifiche non
 * rigenerate" quando dirty=true.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Pencil, Search } from 'lucide-react'

import { api, type CourseSummary } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' {
  if (status === 'completed' || status === 'certified') return 'default'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

type Props = {
  /** Optional custom trigger (e.g. a Button in the sidebar). Defaults to a
   *  brand "Apri Course Studio" button so it works standalone too. */
  trigger?: React.ReactNode
}

export function CoursePickerDialog({ trigger }: Props) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const navigate = useNavigate()

  // Fetch only when the dialog actually opens — keeps the sidebar idle.
  const coursesQ = useQuery({
    queryKey: ['courses', 'studio-picker'] as const,
    queryFn: () => api.getCourses({ page: 1, per_page: 50 }),
    enabled: open,
  })

  const items: CourseSummary[] = (coursesQ.data ?? []).filter((c) => {
    if (c.status === 'queued' || c.status === 'failed') return false
    if (!q.trim()) return true
    const t = `${c.title} ${c.course_type}`.toLowerCase()
    return t.includes(q.trim().toLowerCase())
  })

  function openStudio(id: string) {
    setOpen(false)
    navigate({ to: '/courses/$id/studio', params: { id } })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button>
            <Pencil aria-hidden='true' /> Apri Course Studio
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle>Scegli il corso da modificare</DialogTitle>
          <DialogDescription>
            Apri il Course Studio per modificare slide, immagini, note e
            rigenerare PPTX/PDF/audio.
          </DialogDescription>
        </DialogHeader>

        <div className='relative'>
          <Search
            className='text-muted-foreground absolute top-2.5 left-2.5 size-4'
            aria-hidden='true'
          />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder='Cerca per titolo o tipo…'
            className='pl-8'
            autoFocus
          />
        </div>

        <div className='max-h-[60vh] space-y-1.5 overflow-y-auto pr-1'>
          {coursesQ.isLoading && (
            <>
              <Skeleton className='h-14 w-full' />
              <Skeleton className='h-14 w-full' />
              <Skeleton className='h-14 w-full' />
            </>
          )}
          {!coursesQ.isLoading && items.length === 0 && (
            <p className='text-muted-foreground py-6 text-center text-sm'>
              Nessun corso editabile trovato.
            </p>
          )}
          {items.map((c) => (
            <button
              key={c.id}
              onClick={() => openStudio(c.id)}
              className={cn(
                'border-border hover:bg-muted/60 hover:border-brand-primary/40',
                'w-full rounded-md border p-3 text-left transition-colors',
              )}
            >
              <div className='flex items-start justify-between gap-2'>
                <div className='min-w-0 flex-1'>
                  <p className='truncate text-sm font-semibold'>{c.title}</p>
                  <p className='text-muted-foreground truncate text-xs'>
                    {c.course_type} · {c.duration_hours}h · {c.target}
                  </p>
                </div>
                <div className='flex shrink-0 flex-col items-end gap-1'>
                  <Badge variant={statusVariant(c.status)} className='capitalize'>
                    {c.status}
                  </Badge>
                </div>
              </div>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
