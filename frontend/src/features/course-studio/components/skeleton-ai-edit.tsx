/**
 * Skeleton AI Edit — micro-azioni LLM su struttura (F3.AI, 2026-05-31).
 *
 * Componenti riusabili da SkeletonReview:
 *  - <VoiceAiActions />     3 pulsanti per voce (Riformula / Operativo / Alternative)
 *  - <ModuleAiPrompt />     Input "Chiedi all'AI" per modulo (free-text)
 *  - <DiffAcceptDialog />   Dialog che mostra diff before/after e chiede Applica/Annulla
 *  - <AlternativesDialog /> Dialog che mostra 3 alternative e fa scegliere quale applicare
 *
 * Pattern: il componente non muta lo state esterno direttamente — invoca callback
 * `onApply(newItem)` o `onApplyModule(newItems)` quando l'utente conferma. Lo stato
 * AI (loading, response, error) e' isolato qui per non inquinare SkeletonReview.
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Loader2,
  RefreshCw,
  Sparkles,
  Wand2,
  Wrench,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  api,
  ApiError,
  type SkeletonItem,
  type SubtopicProposal,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

// ─── Diff Dialog (riusato da rephrase + operational) ────────────────────────

interface DiffAcceptDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  before: SubtopicProposal
  after: SubtopicProposal | null
  onApply: (next: SubtopicProposal) => void
  actionLabel: string
}

export function DiffAcceptDialog({
  open,
  onOpenChange,
  before,
  after,
  onApply,
  actionLabel,
}: DiffAcceptDialogProps) {
  if (!after) return null
  const changedTopic = before.sub_topic !== after.sub_topic
  const changedQuery = before.retrieval_query !== after.retrieval_query
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <Sparkles className='text-brand-primary size-4' aria-hidden='true' />
            Proposta AI · {actionLabel}
          </DialogTitle>
          <DialogDescription>
            Confronta la versione attuale con quella proposta dall'AI. Applica solo
            se la proposta migliora il sotto-tema.
          </DialogDescription>
        </DialogHeader>

        <div className='grid grid-cols-2 gap-3 text-sm'>
          <div className='space-y-2'>
            <Badge variant='outline' className='text-xs'>
              Prima
            </Badge>
            <div className='border-border space-y-1 rounded-md border p-3'>
              <div className='text-muted-foreground text-[10px] uppercase tracking-wide'>
                Sotto-tema
              </div>
              <div className={cn('font-medium', changedTopic && 'line-through opacity-60')}>
                {before.sub_topic}
              </div>
              <div className='text-muted-foreground mt-2 text-[10px] uppercase tracking-wide'>
                Query di recupero
              </div>
              <div className={cn('text-xs', changedQuery && 'line-through opacity-60')}>
                {before.retrieval_query}
              </div>
            </div>
          </div>

          <div className='space-y-2'>
            <Badge
              variant='outline'
              className='border-brand-primary/40 bg-brand-primary/10 text-brand-primary text-xs'
            >
              Dopo
            </Badge>
            <div
              className={cn(
                'space-y-1 rounded-md border p-3',
                'border-brand-primary/40 bg-brand-primary/5',
              )}
            >
              <div className='text-muted-foreground text-[10px] uppercase tracking-wide'>
                Sotto-tema
              </div>
              <div className={cn('font-medium', changedTopic && 'text-brand-primary')}>
                {after.sub_topic}
              </div>
              <div className='text-muted-foreground mt-2 text-[10px] uppercase tracking-wide'>
                Query di recupero
              </div>
              <div className={cn('text-xs', changedQuery && 'text-brand-primary')}>
                {after.retrieval_query}
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant='ghost' onClick={() => onOpenChange(false)}>
            Annulla
          </Button>
          <Button
            onClick={() => {
              onApply(after)
              onOpenChange(false)
            }}
            disabled={!changedTopic && !changedQuery}
          >
            Applica modifica
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Alternatives Dialog ────────────────────────────────────────────────────

interface AlternativesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  before: SubtopicProposal
  alternatives: SubtopicProposal[]
  onApply: (next: SubtopicProposal) => void
}

export function AlternativesDialog({
  open,
  onOpenChange,
  before,
  alternatives,
  onApply,
}: AlternativesDialogProps) {
  const [selected, setSelected] = useState<number | null>(null)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <Sparkles className='text-brand-primary size-4' aria-hidden='true' />
            3 alternative AI per "{before.sub_topic}"
          </DialogTitle>
          <DialogDescription>
            Scegli un'alternativa con un taglio diverso, oppure tieni la versione attuale.
          </DialogDescription>
        </DialogHeader>

        <div className='space-y-2'>
          {alternatives.map((alt, i) => (
            <button
              key={i}
              type='button'
              onClick={() => setSelected(i)}
              className={cn(
                'block w-full rounded-md border p-3 text-left transition-colors',
                selected === i
                  ? 'border-brand-primary bg-brand-primary/5 ring-brand-primary/30 ring-2'
                  : 'border-border hover:bg-muted/40',
              )}
            >
              <div className='flex items-center gap-2'>
                <Badge variant='outline' className='text-[10px]'>
                  Alternativa {i + 1}
                </Badge>
              </div>
              <div className='mt-1.5 font-medium text-sm'>{alt.sub_topic}</div>
              <div className='text-muted-foreground mt-1 text-xs'>
                {alt.retrieval_query}
              </div>
            </button>
          ))}
        </div>

        <DialogFooter>
          <Button variant='ghost' onClick={() => onOpenChange(false)}>
            Annulla
          </Button>
          <Button
            onClick={() => {
              if (selected !== null) {
                onApply(alternatives[selected])
                onOpenChange(false)
              }
            }}
            disabled={selected === null}
          >
            Usa alternativa
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Voice AI Actions (3 pulsanti per sotto-tema) ───────────────────────────

interface VoiceAiActionsProps {
  courseId: string
  moduleIndex: number
  item: SkeletonItem
  onApply: (next: SubtopicProposal) => void
}

export function VoiceAiActions({
  courseId,
  moduleIndex,
  item,
  onApply,
}: VoiceAiActionsProps) {
  const [diffOpen, setDiffOpen] = useState(false)
  const [diffAfter, setDiffAfter] = useState<SubtopicProposal | null>(null)
  const [diffLabel, setDiffLabel] = useState<string>('')
  const [altsOpen, setAltsOpen] = useState(false)
  const [alts, setAlts] = useState<SubtopicProposal[]>([])

  const before: SubtopicProposal = {
    sub_topic: item.sub_topic,
    retrieval_query: item.retrieval_query,
  }

  const mut = useMutation({
    mutationFn: (action: 'rephrase_subtopic' | 'make_operational' | 'suggest_alternatives') =>
      api.aiEditSkeletonVoice(courseId, {
        action,
        module_index: moduleIndex,
        voice_ordinal: item.ordinal,
      }),
    onError: (e) =>
      toast.error(
        e instanceof ApiError
          ? e.message
          : 'AI temporaneamente non disponibile.',
      ),
  })

  async function runAction(
    action: 'rephrase_subtopic' | 'make_operational' | 'suggest_alternatives',
    label: string,
  ) {
    const result = await mut.mutateAsync(action)
    if ('proposal' in result) {
      setDiffAfter(result.proposal)
      setDiffLabel(label)
      setDiffOpen(true)
    } else if ('alternatives' in result) {
      setAlts(result.alternatives)
      setAltsOpen(true)
    }
  }

  const pending = mut.isPending
  const Spinner = <Loader2 className='size-3 animate-spin' aria-hidden='true' />

  return (
    <>
      <TooltipProvider delayDuration={200}>
        <div className='flex flex-wrap items-center gap-1'>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size='sm'
                variant='ghost'
                className='text-brand-primary hover:bg-brand-primary/10 h-6 px-2 text-[10px]'
                onClick={() => runAction('rephrase_subtopic', 'Riformula')}
                disabled={pending}
                aria-label='Riformula con AI'
              >
                {pending ? Spinner : <Sparkles className='size-3' aria-hidden='true' />}
                <span className='ml-1'>Riformula</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              Riformula il sotto-tema mantenendo significato e perimetro.
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size='sm'
                variant='ghost'
                className='text-brand-primary hover:bg-brand-primary/10 h-6 px-2 text-[10px]'
                onClick={() => runAction('make_operational', 'Rendi operativo')}
                disabled={pending}
                aria-label='Rendi operativo con AI'
              >
                {pending ? Spinner : <Wrench className='size-3' aria-hidden='true' />}
                <span className='ml-1'>Operativo</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              Trasforma in azioni/procedure concrete invece di concetti astratti.
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size='sm'
                variant='ghost'
                className='text-brand-primary hover:bg-brand-primary/10 h-6 px-2 text-[10px]'
                onClick={() => runAction('suggest_alternatives', 'Alternative')}
                disabled={pending}
                aria-label='Suggerisci 3 alternative'
              >
                {pending ? Spinner : <RefreshCw className='size-3' aria-hidden='true' />}
                <span className='ml-1'>Alternative</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              Mostra 3 alternative con tagli diversi (teorico / applicativo / regolamentare).
            </TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>

      <DiffAcceptDialog
        open={diffOpen}
        onOpenChange={setDiffOpen}
        before={before}
        after={diffAfter}
        onApply={onApply}
        actionLabel={diffLabel}
      />
      <AlternativesDialog
        open={altsOpen}
        onOpenChange={setAltsOpen}
        before={before}
        alternatives={alts}
        onApply={onApply}
      />
    </>
  )
}

// ─── Module AI Prompt (free-text "Chiedi all'AI") ───────────────────────────

interface ModuleAiPromptProps {
  courseId: string
  moduleIndex: number
  moduleTitle: string
  onApplyModule: (items: SkeletonItem[]) => void
}

export function ModuleAiPrompt({
  courseId,
  moduleIndex,
  moduleTitle,
  onApplyModule,
}: ModuleAiPromptProps) {
  const [instruction, setInstruction] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [patch, setPatch] = useState<SkeletonItem[] | null>(null)

  const mut = useMutation({
    mutationFn: (instr: string) =>
      api.aiEditSkeletonModule(courseId, {
        module_index: moduleIndex,
        user_instruction: instr,
      }),
    onSuccess: (res) => {
      setPatch(res.patch.items)
      setPreviewOpen(true)
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError
          ? e.message
          : 'AI temporaneamente non disponibile.',
      ),
  })

  const trimmed = instruction.trim()
  const tooShort = trimmed.length > 0 && trimmed.length < 5
  const tooLong = trimmed.length > 1000

  return (
    <>
      <div className='border-brand-primary/20 bg-brand-primary/5 mt-3 space-y-2 rounded-md border border-dashed p-3'>
        <div className='flex items-center gap-2 text-xs font-medium'>
          <Wand2 className='text-brand-primary size-3.5' aria-hidden='true' />
          <span>Chiedi all'AI di modificare il modulo</span>
        </div>
        <Textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          rows={2}
          placeholder={`Esempi: "rendi tutto più operativo", "aggiungi un sotto-tema su DPI", "metti la prevenzione prima del rischio biologico"…`}
          className='text-xs'
          aria-label={`Chiedi all'AI · modulo ${moduleIndex + 1}`}
        />
        <div className='flex items-center justify-between gap-2'>
          <div className='text-muted-foreground text-[10px]'>
            {tooShort && 'Min 5 caratteri.'}
            {tooLong && 'Max 1000 caratteri.'}
            {!tooShort && !tooLong && trimmed.length > 0 && `${trimmed.length} caratteri`}
          </div>
          <Button
            size='sm'
            className='h-7 text-xs'
            disabled={trimmed.length < 5 || tooLong || mut.isPending}
            onClick={() => mut.mutate(trimmed)}
          >
            {mut.isPending ? (
              <Loader2 className='size-3 animate-spin' aria-hidden='true' />
            ) : (
              <Sparkles className='size-3' aria-hidden='true' />
            )}
            <span className='ml-1'>Genera proposta</span>
          </Button>
        </div>
      </div>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className='max-w-2xl'>
          <DialogHeader>
            <DialogTitle className='flex items-center gap-2'>
              <Sparkles className='text-brand-primary size-4' aria-hidden='true' />
              Nuova struttura proposta per "{moduleTitle}"
            </DialogTitle>
            <DialogDescription>
              {patch?.length ?? 0} sotto-temi proposti. Applica per sostituire la
              struttura attuale del modulo.
            </DialogDescription>
          </DialogHeader>
          <div className='max-h-96 space-y-2 overflow-y-auto'>
            {patch?.map((it, i) => (
              <div key={i} className='border-border rounded-md border p-2.5 text-sm'>
                <div className='flex items-baseline gap-2'>
                  <Badge variant='secondary' className='text-[10px]'>
                    {it.ordinal}
                  </Badge>
                  <span className='font-medium'>{it.sub_topic}</span>
                </div>
                <div className='text-muted-foreground ms-7 mt-1 text-xs'>
                  {it.retrieval_query}
                </div>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant='ghost' onClick={() => setPreviewOpen(false)}>
              Annulla
            </Button>
            <Button
              onClick={() => {
                if (patch) {
                  onApplyModule(patch)
                  setPreviewOpen(false)
                  setInstruction('')
                  toast.success('Struttura modulo aggiornata.')
                }
              }}
            >
              Applica nuova struttura
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
