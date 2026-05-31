/**
 * ImagePicker — cambia l'immagine di una slide (FASE 10 + F5.4 post-MVP 2026-05-31).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: Library tab "internal asset stock", grid 4-col con hover license chip.
 *   Distinta da Pexels tab esterno via badge color: brand-primary su Library
 *   (asset curato CFP), muted su Web (provenance terza parte).
 *   Tabs default = Library (asset interno > terza parte: VAA-b attribution).
 * Tone: shadcn Dialog + Tabs + Badge + Tooltip. Riusa pattern image-picker MVP.
 * Constraints: REI-1 shadcn only, REI-10 attribution sempre visibile per CC-BY.
 *
 * Due modi:
 *   (1) Library tab (default): cerca semantica multimodal voyage-3 → grid
 *       4-col con thumbnail + hover overlay con license/attribution.
 *   (2) Web tab: cerca su Pexels via /image/search (cascata legacy).
 *   (3) URL manuale fallback in tutti i tab.
 */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ImageIcon, Library, Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'

import { api, type LibraryHit, type StudioSlide } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

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
  const [committedQuery, setCommittedQuery] = useState<string>('')
  const [candidates, setCandidates] = useState<string[]>([])
  const [manualUrl, setManualUrl] = useState('')

  // F5.4 — Library tab (default). useQuery con enabled gating su query >=2 chars
  // per non sparare la chiamata Voyage embed ad ogni keystroke.
  const libraryQ = useQuery({
    queryKey: ['imageLibrary', courseId, committedQuery] as const,
    queryFn: () => api.searchImageLibrary(courseId, committedQuery, 8),
    enabled: open && committedQuery.length >= 2,
    staleTime: 60_000,
  })

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
    mutationFn: (args: { url: string; strategy?: string }) =>
      api.patchSlideImage(courseId, slide.index, {
        strategy: args.strategy ?? 'web_search',
        query,
        query_url: args.url,
      }),
    onSuccess: () => {
      toast.success('Immagine aggiornata')
      qc.invalidateQueries({ queryKey: ['course-slides', courseId] })
      setOpen(false)
    },
    onError: () => toast.error('Aggiornamento immagine fallito'),
  })

  function commitQuery() {
    setCommittedQuery(query.trim())
  }

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
            Library locale (preferita, attribution tracciata) oppure ricerca web.
          </DialogDescription>
        </DialogHeader>

        {/* Search bar condivisa Library + Web */}
        <div className="flex gap-2">
          <Input
            placeholder="es. estintore officina"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                commitQuery()
                searchMut.mutate()
              }
            }}
          />
          <Button
            onClick={() => {
              commitQuery()
              searchMut.mutate()
            }}
            disabled={searchMut.isPending || query.trim().length < 2}
          >
            {searchMut.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </Button>
        </div>

        <Tabs defaultValue="library" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="library" className="gap-1.5">
              <Library className="h-3.5 w-3.5" />
              Library
              {libraryQ.data && libraryQ.data.hits.length > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
                  {libraryQ.data.hits.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="web" className="gap-1.5">
              <Search className="h-3.5 w-3.5" />
              Web
              {candidates.length > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-[10px]">
                  {candidates.length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* ─── LIBRARY TAB ─────────────────────────────────────────────── */}
          <TabsContent value="library" className="mt-3">
            {!committedQuery && (
              <div className="border-border bg-muted/30 rounded-md border border-dashed p-6 text-center">
                <Library className="text-muted-foreground mx-auto mb-2 h-8 w-8" />
                <p className="text-muted-foreground text-xs">
                  Scrivi una parola chiave per cercare nella libreria interna
                  (asset curati con attribution tracciata).
                </p>
              </div>
            )}
            {libraryQ.isLoading && (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="bg-muted aspect-square animate-pulse rounded-md"
                  />
                ))}
              </div>
            )}
            {libraryQ.data && libraryQ.data.hits.length === 0 && (
              <p className="text-muted-foreground py-6 text-center text-xs">
                Nessun asset nella libreria per "{committedQuery}". Prova la tab
                Web oppure incolla un URL.
              </p>
            )}
            {libraryQ.data && libraryQ.data.hits.length > 0 && (
              <TooltipProvider delayDuration={200}>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {libraryQ.data.hits.map((hit: LibraryHit) => (
                    <LibraryCard
                      key={hit.id}
                      hit={hit}
                      onChoose={(url) =>
                        setImageMut.mutate({ url, strategy: 'library' })
                      }
                      disabled={setImageMut.isPending}
                    />
                  ))}
                </div>
              </TooltipProvider>
            )}
          </TabsContent>

          {/* ─── WEB TAB ─────────────────────────────────────────────────── */}
          <TabsContent value="web" className="mt-3">
            {candidates.length > 0 ? (
              <div className="grid grid-cols-3 gap-2">
                {candidates.map((url) => (
                  <button
                    key={url}
                    onClick={() => setImageMut.mutate({ url })}
                    disabled={setImageMut.isPending}
                    className="border-border hover:border-primary overflow-hidden rounded-md border transition-colors"
                  >
                    <img src={url} alt="candidato" className="h-28 w-full object-cover" />
                  </button>
                ))}
              </div>
            ) : (
              !searchMut.isPending && (
                <div className="border-border bg-muted/30 rounded-md border border-dashed p-6 text-center">
                  <Search className="text-muted-foreground mx-auto mb-2 h-8 w-8" />
                  <p className="text-muted-foreground text-xs">
                    Cerca su Pexels/Pixabay/Openverse/Wikimedia. Quando trovi
                    l'immagine giusta, sarà segnalata "Web" (provenance esterna).
                  </p>
                </div>
              )
            )}
          </TabsContent>
        </Tabs>

        {/* URL manuale (sempre visibile) */}
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
              onClick={() => manualUrl && setImageMut.mutate({ url: manualUrl })}
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

// ─── F5.4 Library hit card con hover license chip ──────────────────────────

interface LibraryCardProps {
  hit: LibraryHit
  onChoose: (url: string) => void
  disabled: boolean
}

function LibraryCard({ hit, onChoose, disabled }: LibraryCardProps) {
  // file_path è relativo al repo (es. assets/seeds/iso7010/...).
  // Per ora il path serve come identificatore — il backend lo userà come
  // chiave PATCH (strategy=library), e la pipeline image_service caricherà
  // l'asset dal filesystem. La preview UI usa solo lo stesso path che dovrà
  // essere mounted via static.
  const previewSrc = `/static/${hit.file_path}`
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={() => onChoose(hit.file_path)}
          disabled={disabled}
          className="border-border hover:border-brand-primary group relative aspect-square overflow-hidden rounded-md border transition-colors"
        >
          <img
            src={previewSrc}
            alt={hit.attribution ?? hit.file_path}
            className="h-full w-full object-cover"
            onError={(e) => {
              // Se /static/ non è ancora mountato (deploy iniziale), mostra
              // placeholder testuale invece di icona broken.
              const target = e.target as HTMLImageElement
              target.style.display = 'none'
            }}
          />
          {/* Hover overlay: license chip */}
          <div className="absolute inset-0 flex items-end bg-foreground/60 p-2 opacity-0 transition-opacity group-hover:opacity-100">
            <Badge
              variant="outline"
              className="border-background/40 bg-background/80 font-mono text-[9px]"
            >
              {hit.source}
              {hit.license ? ` · ${hit.license}` : ''}
            </Badge>
          </div>
          {/* Top-right score badge */}
          <Badge
            variant="outline"
            className="border-brand-primary/30 bg-brand-primary/10 text-brand-primary absolute right-1 top-1 font-mono text-[9px]"
          >
            {hit.score.toFixed(2)}
          </Badge>
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-[280px]">
        <p className="text-xs font-medium">{hit.attribution ?? hit.file_path}</p>
        {hit.tags.length > 0 && (
          <p className="text-muted-foreground mt-1 text-[10px]">
            tag: {hit.tags.slice(0, 5).join(', ')}
            {hit.tags.length > 5 ? '…' : ''}
          </p>
        )}
      </TooltipContent>
    </Tooltip>
  )
}
