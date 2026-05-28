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

import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Info, Loader2, Upload } from 'lucide-react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

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

  function reset() {
    setFile(null)
    setSlug('')
    setTitle('')
    setRegType('DECRETO')
    setRegion('NAZIONALE')
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
