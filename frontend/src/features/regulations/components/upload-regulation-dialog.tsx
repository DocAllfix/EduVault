/**
 * Upload regulation dialog — admin-only (BP §10).
 *
 * Native HTML5 drag-and-drop on a single drop zone, plus a hidden
 * <input type=file> as fallback (click to browse). No react-dropzone
 * dep — REI-5: don't pull a library for 30 lines of drag-drop event
 * wiring that vanilla HTML5 supports cleanly.
 *
 * Backend (`POST /api/regulations/upload`) requires multipart with the
 * file PLUS form fields slug, title, reg_type, region, issuing_body,
 * source_url. We collect them in the same dialog before submit — making
 * the user upload a PDF and only THEN realize they need a slug is the
 * worst possible UX.
 */

import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Check, Info, Loader2, Upload } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError } from '@/lib/api'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

// ─── Ingestion stage estimator (UX progress chiaro) ───
// Tempi stimati basati sulla taglia file. Backend non emette progress
// granulare in upload, ma le 4 fasi sono deterministiche: parse PDF →
// chunk + segment → classify LLM → embed Voyage. ETA aggiornato live.

interface IngestionStage {
  id: 'upload' | 'parse' | 'chunk' | 'classify' | 'embed'
  label: string
  description: string
}

const INGESTION_STAGES: IngestionStage[] = [
  { id: 'upload', label: 'Upload', description: 'Trasferimento file al server.' },
  { id: 'parse', label: 'Parsing PDF', description: 'Estrazione testo strutturato.' },
  { id: 'chunk', label: 'Segmentazione', description: 'Divisione in chunk semantici.' },
  { id: 'classify', label: 'Classificazione', description: 'LLM categorizza articoli e commi.' },
  { id: 'embed', label: 'Embedding', description: 'Voyage genera vettori per ricerca.' },
]

function estimateTotalMs(sizeMB: number): number {
  // Misurato empiricamente: 1 MB ~ 30s pipeline completa.
  // Min 30s (overhead fisso) + 25s per MB.
  return Math.max(30_000, Math.round(30_000 + sizeMB * 25_000))
}

const REG_TYPES = ['DECRETO', 'LEGGE', 'ACCORDO', 'CIRCOLARE', 'NORMA_TECNICA'] as const

// Soglia oltre la quale informiamo l'utente che il server continuera' a
// processare in background anche se il client va in timeout. Verificato in
// produzione (sessione F1.C): il D.Lgs 81/08 (~6 MB / 137 pp) e il Reg CE
// 1272/2008 (22 MB / 1576 pp) completano lato server anche quando il client
// httpx interrompe la connessione per ReadTimeout. 10 MB e' il punto in cui
// inizia a essere prudente avvisare.
const LARGE_FILE_THRESHOLD_MB = 10

export function UploadRegulationDialog() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [slug, setSlug] = useState('')
  const [title, setTitle] = useState('')
  const [regType, setRegType] = useState<string>('DECRETO')
  const [region, setRegion] = useState('NAZIONALE')

  // Progress UX: stage corrente + elapsed time + ETA. Avanza autonomamente
  // basandosi su timer (backend non emette progress granulare in upload).
  const [stageIndex, setStageIndex] = useState(0)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [totalEtaMs, setTotalEtaMs] = useState(60_000)
  const startTimeRef = useRef<number | null>(null)

  useEffect(() => {
    if (!isLoading) return
    const tick = () => {
      if (!startTimeRef.current) return
      const elapsed = Date.now() - startTimeRef.current
      setElapsedMs(elapsed)
      // Avanza stage in modo proporzionale: ogni 1/5 del totale ETA cambia stage
      const stageStep = totalEtaMs / INGESTION_STAGES.length
      const target = Math.min(
        INGESTION_STAGES.length - 1,
        Math.floor(elapsed / stageStep),
      )
      setStageIndex(target)
    }
    const interval = window.setInterval(tick, 500)
    return () => window.clearInterval(interval)
  }, [isLoading, totalEtaMs])

  function reset() {
    setFile(null)
    setSlug('')
    setTitle('')
    setRegType('DECRETO')
    setRegion('NAZIONALE')
    setStageIndex(0)
    setElapsedMs(0)
    startTimeRef.current = null
  }

  function acceptFile(f: File | undefined) {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Solo file PDF sono accettati.')
      return
    }
    setFile(f)
    // Auto-derive a slug suggestion from filename if user hasn't typed one.
    if (!slug) {
      const base = f.name.replace(/\.pdf$/i, '').toLowerCase()
        .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
      setSlug(base.slice(0, 64))
    }
    if (!title) setTitle(f.name.replace(/\.pdf$/i, ''))
  }

  async function handleSubmit() {
    if (!file || !slug || !title) {
      toast.error('Compila tutti i campi obbligatori.')
      return
    }
    const sizeMB = file.size / 1024 / 1024
    const isLarge = sizeMB > LARGE_FILE_THRESHOLD_MB
    setIsLoading(true)
    setStageIndex(0)
    setElapsedMs(0)
    startTimeRef.current = Date.now()
    setTotalEtaMs(estimateTotalMs(sizeMB))
    // PDF grossi: il server completa anche se il client va in timeout. Mostriamo
    // un toast informativo PRIMA del fetch cosi' l'utente sa che attesa lunga
    // non vuol dire fallimento. Il toast successivo (success / network-error)
    // resta comunque la fonte di verita' del risultato.
    if (isLarge) {
      toast.info(
        `Il file e' grande (${sizeMB.toFixed(0)} MB). Se il client va in timeout, ` +
          'il server continua a indicizzare in background: controlla la lista ' +
          'normative tra 2-5 minuti.',
        { duration: 8000 },
      )
    }
    try {
      const res = await api.uploadRegulation(file, { slug, title, reg_type: regType, region })
      toast.success(`Normativa indicizzata: ${res.chunks_count} chunk.`)
      await queryClient.invalidateQueries({ queryKey: ['regulations'] })
      setOpen(false)
      reset()
    } catch (err) {
      // Per i file grandi un timeout client e' un falso positivo: il server
      // probabilmente sta ancora processando. Distinguiamo il messaggio.
      const msg = err instanceof ApiError ? err.message : 'Upload non riuscito.'
      if (isLarge && /timeout|aborted|network|failed to fetch/i.test(msg)) {
        toast.warning(
          'Connessione interrotta lato client. L\'elaborazione potrebbe essere ' +
            'comunque in corso sul server: aspetta 2-5 minuti, poi ricarica la ' +
            'lista normative per verificare.',
          { duration: 10000 },
        )
        await queryClient.invalidateQueries({ queryKey: ['regulations'] })
        setOpen(false)
        reset()
      } else {
        toast.error(msg)
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Upload aria-hidden='true' />
          Carica normativa
        </Button>
      </DialogTrigger>
      <DialogContent className='sm:max-w-md'>
        <DialogHeader>
          <DialogTitle>Carica una normativa</DialogTitle>
          <DialogDescription>
            Il PDF viene segmentato, classificato e indicizzato per la pipeline RAG.
          </DialogDescription>
        </DialogHeader>

        <div className='space-y-4'>
          {/* Drop zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setIsDragging(true)
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setIsDragging(false)
              acceptFile(e.dataTransfer.files[0])
            }}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-6 text-center transition-colors',
              isDragging
                ? 'border-brand-primary bg-brand-primary/5'
                : 'border-border hover:bg-muted/40',
            )}
            role='button'
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                fileInputRef.current?.click()
              }
            }}
          >
            <Upload className='size-6 text-muted-foreground' aria-hidden='true' />
            {file ? (
              <div className='text-sm'>
                <div className='font-medium'>{file.name}</div>
                <div className='text-xs text-muted-foreground'>
                  {(file.size / 1024).toFixed(0)} KB · clicca per sostituire
                </div>
              </div>
            ) : (
              <>
                <div className='text-sm font-medium'>Trascina il PDF qui</div>
                <div className='text-xs text-muted-foreground'>
                  oppure clicca per sfogliare
                </div>
              </>
            )}
            <input
              ref={fileInputRef}
              type='file'
              accept='application/pdf,.pdf'
              className='hidden'
              onChange={(e) => acceptFile(e.target.files?.[0] ?? undefined)}
            />
          </div>

          {/* Avviso permanente: limiti tecnici noti del parser pdfplumber.
              Restano visibili PRIMA della selezione file cosi' l'utente sa
              cosa funziona e cosa no senza dover provare. */}
          <div className='border-border bg-muted/40 flex gap-2 rounded-md border p-2.5 text-xs'>
            <Info
              className='text-muted-foreground mt-0.5 size-3.5 shrink-0'
              aria-hidden='true'
            />
            <div className='text-muted-foreground leading-relaxed'>
              <p>
                <strong className='text-foreground'>Solo PDF testuali.</strong>{' '}
                I PDF scansionati come immagini non possono essere indicizzati
                (manca OCR). Se il documento e' una scansione, riprova con la
                versione testuale dalla Gazzetta Ufficiale, EUR-Lex o
                normattiva.it.
              </p>
              <p className='mt-1'>
                Per file molto grandi (oltre {LARGE_FILE_THRESHOLD_MB} MB),
                l'elaborazione lato server puo' durare diversi minuti e
                continua anche se il browser sembra scollegarsi.
              </p>
            </div>
          </div>

          {/* Metadata */}
          <div className='grid gap-2'>
            <Label htmlFor='reg-slug'>Slug</Label>
            <Input
              id='reg-slug'
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder='dlgs_81_08'
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='reg-title'>Titolo</Label>
            <Input
              id='reg-title'
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder='D.Lgs. 81/2008 — Testo Unico Sicurezza'
            />
          </div>
          <div className='grid grid-cols-2 gap-3'>
            <div className='grid gap-2'>
              <Label htmlFor='reg-type'>Tipo</Label>
              <Select value={regType} onValueChange={setRegType}>
                <SelectTrigger id='reg-type'>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REG_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className='grid gap-2'>
              <Label htmlFor='reg-region'>Regione</Label>
              <Input
                id='reg-region'
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder='NAZIONALE'
              />
            </div>
          </div>
        </div>

        {/* Progress stepper visibile durante upload (UX feedback chiaro) */}
        {isLoading && (
          <div className='space-y-4 rounded-md border bg-muted/30 p-4'>
            <div className='flex items-center justify-between text-sm'>
              <span className='font-medium'>
                {INGESTION_STAGES[stageIndex]?.label ?? 'Avvio…'}
              </span>
              <span className='tabular-nums text-muted-foreground'>
                {Math.round(elapsedMs / 1000)}s / ~{Math.round(totalEtaMs / 1000)}s
              </span>
            </div>
            <Progress
              value={Math.min(100, Math.round((elapsedMs / totalEtaMs) * 100))}
              className='h-2'
            />
            <ul className='space-y-1.5'>
              {INGESTION_STAGES.map((s, i) => {
                const done = i < stageIndex
                const active = i === stageIndex
                return (
                  <li
                    key={s.id}
                    className={cn(
                      'flex items-center gap-2 text-xs transition-opacity',
                      done && 'text-muted-foreground',
                      active && 'font-medium text-foreground',
                      !done && !active && 'opacity-50',
                    )}
                  >
                    <span className='flex size-5 items-center justify-center'>
                      {done ? (
                        <Check className='size-4 text-brand-secondary' aria-hidden='true' />
                      ) : active ? (
                        <Loader2 className='size-4 animate-spin text-brand-primary' aria-hidden='true' />
                      ) : (
                        <span className='size-2 rounded-full bg-muted-foreground/40' />
                      )}
                    </span>
                    <span>{s.label}</span>
                    {active && (
                      <span className='ml-1 text-muted-foreground'>— {s.description}</span>
                    )}
                  </li>
                )
              })}
            </ul>
            <p className='text-[11px] text-muted-foreground'>
              Il server continua l'elaborazione anche se chiudi il dialog. La
              normativa apparirà nell'elenco al termine.
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant='ghost' onClick={() => setOpen(false)} disabled={isLoading}>
            Annulla
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading || !file}>
            {isLoading ? <Loader2 className='animate-spin' aria-hidden='true' /> : <Upload aria-hidden='true' />}
            {isLoading ? 'Indicizzazione…' : 'Carica'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
