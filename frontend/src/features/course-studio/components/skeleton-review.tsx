/**
 * Skeleton Review — D3 gate (vast-hopping-sketch, post-review-17).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: il gate umano 1-click sullo scheletro narrativo. Quando un corso è
 *   `skeleton_pending`, l'operatore (RSPP esperto) vede i sotto-temi proposti
 *   dall'LLM per ogni modulo, li può correggere/riordinare/aggiungere/togliere,
 *   e poi APPROVA — solo allora la pipeline materializza le slide.
 * Tone: una card per modulo, lista ordinata di sotto-temi editabili, azioni
 *   chiare. Brand C.F.P. Montessori (verde/rosa).
 * Constraints: REI-1 riusa shadcn (Card/Button/Input/Textarea/Badge). Edit
 *   MANUALE (la chat NL è D7). Approva = gate, non opzionale.
 */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Check, Loader2, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, type ModuleSkeleton } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

const MIN_ITEMS = 6
const MAX_ITEMS = 10

interface Props {
  courseId: string
  onApproved?: () => void
}

export function SkeletonReview({ courseId, onApproved }: Props) {
  const queryClient = useQueryClient()
  const [modules, setModules] = useState<ModuleSkeleton[] | null>(null)

  const skeletonQ = useQuery({
    queryKey: ['course-skeleton', courseId] as const,
    queryFn: () => api.getCourseSkeleton(courseId),
  })

  // Initialize local editable copy once the query lands.
  if (skeletonQ.data && modules === null) {
    setModules(skeletonQ.data.modules.map((m) => ({ ...m, items: [...m.items] })))
  }

  const saveMut = useMutation({
    mutationFn: (mods: ModuleSkeleton[]) =>
      api.updateCourseSkeleton(courseId, mods),
    onSuccess: () => toast.success('Scheletro salvato.'),
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : 'Salvataggio non riuscito.'),
  })

  const approveMut = useMutation({
    mutationFn: () => api.approveCourseSkeleton(courseId),
    onSuccess: async () => {
      toast.success('Scheletro approvato — generazione slide avviata.')
      await queryClient.invalidateQueries({ queryKey: ['course-skeleton', courseId] })
      onApproved?.()
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : 'Approvazione non riuscita.'),
  })

  if (skeletonQ.isLoading) {
    return (
      <div className='space-y-4 p-6'>
        <Skeleton className='h-8 w-1/3' />
        <Skeleton className='h-40 w-full' />
        <Skeleton className='h-40 w-full' />
      </div>
    )
  }
  if (skeletonQ.isError || !modules) {
    return (
      <div className='p-6 text-sm text-destructive'>
        Impossibile caricare lo scheletro.
      </div>
    )
  }

  // ── local edit helpers (committed to backend via "Salva modifiche") ──
  function patchModules(next: ModuleSkeleton[]) {
    setModules(next)
  }

  function editSubTopic(mi: number, ii: number, value: string) {
    const next = modules!.map((m, j) =>
      j === mi
        ? { ...m, items: m.items.map((it, k) => (k === ii ? { ...it, sub_topic: value } : it)) }
        : m,
    )
    patchModules(next)
  }

  function editQuery(mi: number, ii: number, value: string) {
    const next = modules!.map((m, j) =>
      j === mi
        ? { ...m, items: m.items.map((it, k) => (k === ii ? { ...it, retrieval_query: value } : it)) }
        : m,
    )
    patchModules(next)
  }

  function reorder(mi: number, ii: number, dir: -1 | 1) {
    const m = modules![mi]
    const j = ii + dir
    if (j < 0 || j >= m.items.length) return
    const items = [...m.items]
    ;[items[ii], items[j]] = [items[j], items[ii]]
    // renumber ordinals locally (backend re-normalizes too)
    items.forEach((it, k) => (it.ordinal = k + 1))
    patchModules(modules!.map((mm, idx) => (idx === mi ? { ...mm, items } : mm)))
  }

  function addItem(mi: number) {
    const m = modules![mi]
    if (m.items.length >= MAX_ITEMS) {
      toast.warning(`Massimo ${MAX_ITEMS} sotto-temi per modulo.`)
      return
    }
    const items = [
      ...m.items,
      {
        ordinal: m.items.length + 1,
        sub_topic: 'Nuovo sotto-tema',
        retrieval_query: 'descrivi qui la query di recupero per questo sotto-tema',
      },
    ]
    patchModules(modules!.map((mm, idx) => (idx === mi ? { ...mm, items } : mm)))
  }

  function removeItem(mi: number, ii: number) {
    const m = modules![mi]
    if (m.items.length <= MIN_ITEMS) {
      toast.warning(`Minimo ${MIN_ITEMS} sotto-temi per modulo.`)
      return
    }
    const items = m.items.filter((_, k) => k !== ii)
    items.forEach((it, k) => (it.ordinal = k + 1))
    patchModules(modules!.map((mm, idx) => (idx === mi ? { ...mm, items } : mm)))
  }

  const totalSubtopics = modules.reduce((acc, m) => acc + m.items.length, 0)

  return (
    <div className='mx-auto max-w-4xl space-y-6 p-6'>
      <div className='flex items-start justify-between gap-4'>
        <div>
          <h2 className='text-2xl font-semibold'>Revisione scheletro narrativo</h2>
          <p className='text-muted-foreground text-sm'>
            {modules.length} moduli · {totalSubtopics} sotto-temi proposti.
            Lo scheletro è una bozza generata dall'AI: rivedila, correggi, riordina,
            poi approva. Le slide vengono generate solo dopo l'approvazione.
          </p>
        </div>
        <div className='flex shrink-0 gap-2'>
          <Button
            variant='ghost'
            onClick={() => saveMut.mutate(modules)}
            disabled={saveMut.isPending || approveMut.isPending}
          >
            {saveMut.isPending ? (
              <Loader2 className='animate-spin' aria-hidden='true' />
            ) : null}
            Salva modifiche
          </Button>
          <Button
            onClick={() => approveMut.mutate()}
            disabled={approveMut.isPending || saveMut.isPending}
          >
            {approveMut.isPending ? (
              <Loader2 className='animate-spin' aria-hidden='true' />
            ) : (
              <Check aria-hidden='true' />
            )}
            Approva scheletro
          </Button>
        </div>
      </div>

      {modules.map((m, mi) => (
        <Card key={m.module_index}>
          <CardHeader>
            <CardTitle className='flex items-center gap-2 text-base'>
              <Badge variant='secondary'>Modulo {m.module_index + 1}</Badge>
              {m.title}
            </CardTitle>
          </CardHeader>
          <CardContent className='space-y-3'>
            {m.items.map((it, ii) => (
              <div
                key={ii}
                className='border-border bg-muted/30 flex gap-2 rounded-md border p-2.5'
              >
                <div className='text-muted-foreground w-6 shrink-0 pt-2 text-center text-sm font-medium'>
                  {ii + 1}
                </div>
                <div className='flex-1 space-y-1.5'>
                  <Input
                    value={it.sub_topic}
                    onChange={(e) => editSubTopic(mi, ii, e.target.value)}
                    className='font-medium'
                    aria-label='Sotto-tema'
                  />
                  <Textarea
                    value={it.retrieval_query}
                    onChange={(e) => editQuery(mi, ii, e.target.value)}
                    rows={2}
                    className='text-muted-foreground text-xs'
                    aria-label='Query di recupero'
                  />
                </div>
                <div className='flex shrink-0 flex-col gap-1'>
                  <Button
                    size='icon'
                    variant='ghost'
                    onClick={() => reorder(mi, ii, -1)}
                    disabled={ii === 0}
                    aria-label='Sposta su'
                  >
                    <ArrowUp className='size-4' aria-hidden='true' />
                  </Button>
                  <Button
                    size='icon'
                    variant='ghost'
                    onClick={() => reorder(mi, ii, 1)}
                    disabled={ii === m.items.length - 1}
                    aria-label='Sposta giù'
                  >
                    <ArrowDown className='size-4' aria-hidden='true' />
                  </Button>
                  <Button
                    size='icon'
                    variant='ghost'
                    onClick={() => removeItem(mi, ii)}
                    aria-label='Rimuovi sotto-tema'
                  >
                    <Trash2 className='size-4 text-destructive' aria-hidden='true' />
                  </Button>
                </div>
              </div>
            ))}
            <Button
              variant='ghost'
              size='sm'
              onClick={() => addItem(mi)}
              disabled={m.items.length >= MAX_ITEMS}
            >
              <Plus className='size-4' aria-hidden='true' />
              Aggiungi sotto-tema
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
