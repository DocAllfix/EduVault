/**
 * SlideActions — gestione slide nel Course Studio (FASE 6).
 *
 * Toolbar sopra la lista slide con "Aggiungi slide" (dialog con layout picker)
 * e, per la slide selezionata, le azioni sposta su/giù, duplica, elimina.
 *
 * Tutte le mutazioni invalidano la query ['course-slides', id] così la lista e
 * il viewer si aggiornano, e marcano il corso dirty (RebuildBanner already on).
 * L'integrità del PPTX è garantita lato backend dal reindex contiguo + rebuild.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronUp, ChevronDown, Copy, Trash2, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { api, type StudioSlide } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'

// I tipi che l'operatore può aggiungere manualmente (label IT umane).
const ADDABLE_LAYOUTS: { value: string; label: string }[] = [
  { value: 'CONTENT_TEXT', label: 'Contenuto testuale' },
  { value: 'CONTENT_IMAGE', label: 'Contenuto con immagine' },
  { value: 'DIAGRAM', label: 'Diagramma' },
  { value: 'QUIZ', label: 'Quiz' },
  { value: 'CASE_STUDY', label: 'Caso studio' },
  { value: 'RECAP', label: 'Riepilogo' },
]

const PROTECTED = new Set(['MODULE_OPEN', 'MODULE_CLOSE'])

export function SlideActions({
  courseId,
  selected,
  onSelectIndex,
}: {
  courseId: string
  selected: StudioSlide
  onSelectIndex: (idx: number) => void
}) {
  const qc = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [layout, setLayout] = useState<string>('CONTENT_TEXT')

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ['course-slides', courseId] })

  const addMut = useMutation({
    mutationFn: () => api.addSlide(courseId, selected.index, layout),
    onSuccess: (slides) => {
      invalidate()
      setAddOpen(false)
      // Seleziona la nuova slide (subito dopo quella corrente)
      const newIdx = selected.index + 1
      if (slides.some((s) => s.index === newIdx)) onSelectIndex(newIdx)
      toast.success('Slide aggiunta. Compila il contenuto e poi rigenera.')
    },
    onError: (e: Error) => toast.error(e.message || 'Aggiunta fallita'),
  })

  const moveMut = useMutation({
    mutationFn: (direction: 'up' | 'down') =>
      api.moveSlide(courseId, selected.index, direction),
    onSuccess: (_slides, direction) => {
      invalidate()
      onSelectIndex(
        direction === 'up' ? selected.index - 1 : selected.index + 1,
      )
    },
    onError: (e: Error) => toast.error(e.message || 'Spostamento non consentito'),
  })

  const dupMut = useMutation({
    mutationFn: () => api.duplicateSlide(courseId, selected.index),
    onSuccess: () => {
      invalidate()
      onSelectIndex(selected.index + 1)
      toast.success('Slide duplicata.')
    },
    onError: (e: Error) => toast.error(e.message || 'Duplicazione fallita'),
  })

  const delMut = useMutation({
    mutationFn: () => api.deleteSlide(courseId, selected.index),
    onSuccess: () => {
      invalidate()
      onSelectIndex(Math.max(0, selected.index - 1))
      toast.success('Slide eliminata.')
    },
    onError: (e: Error) => toast.error(e.message || 'Eliminazione non consentita'),
  })

  const isProtected = PROTECTED.has(selected.slide_type)
  const busy =
    addMut.isPending || moveMut.isPending || dupMut.isPending || delMut.isPending

  return (
    <div className='border-border mb-2 flex flex-wrap items-center gap-1.5 rounded-md border p-2'>
      {/* Aggiungi slide */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogTrigger asChild>
          <Button size='sm' variant='default' className='h-8' disabled={busy}>
            <Plus className='mr-1 size-4' /> Aggiungi
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aggiungi una nuova slide</DialogTitle>
            <DialogDescription>
              Scegli il layout. La slide verrà inserita dopo la slide{' '}
              {selected.index + 1}. Potrai poi compilarne testo e immagini e
              rigenerare il corso.
            </DialogDescription>
          </DialogHeader>
          <div className='py-2'>
            <Select value={layout} onValueChange={setLayout}>
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='Seleziona layout' />
              </SelectTrigger>
              <SelectContent>
                {ADDABLE_LAYOUTS.map((l) => (
                  <SelectItem key={l.value} value={l.value}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button
              variant='outline'
              onClick={() => setAddOpen(false)}
              disabled={addMut.isPending}
            >
              Annulla
            </Button>
            <Button onClick={() => addMut.mutate()} disabled={addMut.isPending}>
              {addMut.isPending ? 'Aggiunta…' : 'Aggiungi slide'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className='bg-border mx-1 h-5 w-px' aria-hidden='true' />

      {/* Sposta su */}
      <Button
        size='icon'
        variant='ghost'
        className='size-8'
        title='Sposta su'
        aria-label='Sposta slide su'
        disabled={busy || isProtected || selected.index === 0}
        onClick={() => moveMut.mutate('up')}
      >
        <ChevronUp className='size-4' />
      </Button>
      {/* Sposta giù */}
      <Button
        size='icon'
        variant='ghost'
        className='size-8'
        title='Sposta giù'
        aria-label='Sposta slide giù'
        disabled={busy || isProtected}
        onClick={() => moveMut.mutate('down')}
      >
        <ChevronDown className='size-4' />
      </Button>
      {/* Duplica */}
      <Button
        size='icon'
        variant='ghost'
        className='size-8'
        title='Duplica slide'
        aria-label='Duplica slide'
        disabled={busy}
        onClick={() => dupMut.mutate()}
      >
        <Copy className='size-4' />
      </Button>

      {/* Elimina (con conferma) */}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button
            size='icon'
            variant='ghost'
            className='text-destructive hover:text-destructive size-8'
            title='Elimina slide'
            aria-label='Elimina slide'
            disabled={busy || isProtected}
          >
            <Trash2 className='size-4' />
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminare questa slide?</AlertDialogTitle>
            <AlertDialogDescription>
              La slide {selected.index + 1} verrà rimossa dal corso. L'azione è
              reversibile solo rigenerando da una versione precedente. Vuoi
              procedere?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annulla</AlertDialogCancel>
            <AlertDialogAction
              className='bg-destructive text-white hover:bg-destructive/90'
              onClick={() => delMut.mutate()}
            >
              Elimina
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {isProtected && (
        <span className='text-muted-foreground ml-1 text-xs'>
          Slide di modulo (protetta)
        </span>
      )}
    </div>
  )
}
