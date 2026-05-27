/**
 * RegenerateDialog — chiedi all'LLM di rifare la slide scrivendo l'istruzione
 * (FASE 10/11). Textarea libera (es. "rendi più sintetico", "aggiungi esempio
 * concreto sul cantiere", "cambia il riferimento all'Art. 41") → POST
 * /slides/{idx}/regenerate → content_agent riscrive mantenendo provenance.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, type StudioSlide } from '@/lib/api'
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
import { Textarea } from '@/components/ui/textarea'

export function RegenerateDialog({
  courseId,
  slide,
}: {
  courseId: string
  slide: StudioSlide
}) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [instruction, setInstruction] = useState('')

  const mutation = useMutation({
    mutationFn: () => api.regenerateSlide(courseId, slide.index, instruction),
    onSuccess: () => {
      toast.success('Slide rigenerata dall’AI')
      qc.invalidateQueries({ queryKey: ['course-slides', courseId] })
      setOpen(false)
      setInstruction('')
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) {
        toast.error(`Rigenerazione rifiutata: ${err.message}`)
      } else {
        toast.error('Rigenerazione fallita')
      }
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="w-full">
          <Sparkles className="mr-2 h-4 w-4" /> Rigenera con AI
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rigenera slide con AI</DialogTitle>
          <DialogDescription>
            Descrivi cosa modificare. L&apos;AI riscriverà la slide mantenendo il
            tipo e le citazioni normative.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          placeholder="es. Rendi più sintetico, aggiungi un esempio concreto su un cantiere edile, cambia il riferimento all'Art. 41."
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          rows={4}
        />
        <DialogFooter>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!instruction.trim() || mutation.isPending}
          >
            {mutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Rigenera questa slide
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
