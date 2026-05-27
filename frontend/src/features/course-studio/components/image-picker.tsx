/**
 * ImagePicker — cambia l'immagine di una slide (FASE 10).
 *
 * Due modi: (1) cerca su Pexels via l'agente (endpoint /image/search) e scegli
 * dai risultati; (2) incolla un URL diretto. Click su un candidato → PATCH
 * /slides/{idx}/image → dirty=true. REI-1: Dialog + Input + Button shadcn.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ImageIcon, Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'

import { api, type StudioSlide } from '@/lib/api'
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

export function ImagePicker({
  courseId,
  slide,
}: {
  courseId: string
  slide: StudioSlide
}) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(slide.image.query ?? '')
  const [candidates, setCandidates] = useState<string[]>([])
  const [manualUrl, setManualUrl] = useState('')

  const searchMut = useMutation({
    mutationFn: () =>
      api.searchSlideImages(courseId, query, slide.image.aspect_hint ?? undefined),
    onSuccess: (res) => {
      setCandidates(res.candidates)
      if (res.candidates.length === 0) toast.info('Nessuna immagine trovata')
    },
    onError: () => toast.error('Ricerca immagini fallita'),
  })

  const setImageMut = useMutation({
    mutationFn: (url: string) =>
      api.patchSlideImage(courseId, slide.index, {
        strategy: 'web_search',
        query,
        query_url: url,
      }),
    onSuccess: () => {
      toast.success('Immagine aggiornata')
      qc.invalidateQueries({ queryKey: ['course-slides', courseId] })
      setOpen(false)
    },
    onError: () => toast.error('Aggiornamento immagine fallito'),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="w-full">
          <ImageIcon className="mr-2 h-4 w-4" /> Cambia immagine
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Scegli immagine</DialogTitle>
          <DialogDescription>
            Cerca su Pexels o incolla un URL diretto.
          </DialogDescription>
        </DialogHeader>

        {/* Ricerca Pexels */}
        <div className="flex gap-2">
          <Input
            placeholder="es. casco protezione cantiere"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button onClick={() => searchMut.mutate()} disabled={searchMut.isPending}>
            {searchMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Griglia candidati */}
        {candidates.length > 0 ? (
          <div className="grid grid-cols-3 gap-2">
            {candidates.map((url) => (
              <button
                key={url}
                onClick={() => setImageMut.mutate(url)}
                disabled={setImageMut.isPending}
                className="border-border hover:border-primary overflow-hidden rounded-md border transition-colors"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt="candidato" className="h-28 w-full object-cover" />
              </button>
            ))}
          </div>
        ) : (
          // FIX #32 (polish): empty state esplicito per guidare cliente.
          !searchMut.isPending && (
            <div className="border-border bg-muted/30 rounded-md border border-dashed p-6 text-center">
              <ImageIcon className="text-muted-foreground mx-auto mb-2 h-8 w-8" />
              <p className="text-muted-foreground text-xs">
                Scrivi una parola chiave (es. "casco protezione cantiere") e clicca cerca,
                oppure incolla un URL immagine nel campo sotto.
              </p>
            </div>
          )
        )}

        {/* URL manuale */}
        <div className="border-border border-t pt-3">
          <p className="text-muted-foreground mb-2 text-xs">Oppure incolla un URL:</p>
          <div className="flex gap-2">
            <Input
              placeholder="https://..."
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
            />
            <Button
              variant="secondary"
              onClick={() => manualUrl && setImageMut.mutate(manualUrl)}
              disabled={!manualUrl || setImageMut.isPending}
            >
              Usa
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
