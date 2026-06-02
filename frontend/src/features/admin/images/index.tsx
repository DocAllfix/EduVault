/**
 * Image Library Admin — `/admin/images` (Step B 2026-05-31).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: pagina admin per (a) audit della image_library cresciuta a
 *   ~300+ entries dopo Step A demo extraction + ISO 7010 vettoriali, (b)
 *   upload manuale di singoli PNG/JPG con tag input + license dropdown, (c)
 *   bulk delete entries inutili. Asset bank discovery view.
 * Tone: tabella shadcn con thumbnail 80x80 + tags badges + source chip +
 *   license chip + usage_count + Actions. Header con summary 3-card e CTA
 *   Upload. Brand C.F.P. Montessori (verde + rosa).
 * Constraints: REI-1 shadcn (Table/Card/Badge/Dialog/Input/Label/Select).
 *   Pagina admin-only (require_role admin backend).
 *   File source-of-truth e' image_library DB (delete row ≠ delete file).
 */

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2, Trash2, Upload as UploadIcon, ImageOff } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { toast } from 'sonner'

import { api, ApiError, API_BASE, type ImageLibraryAdminEntry } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { HelpButton } from '@/lib/onboarding/HelpButton'
import { JobsBadge } from '@/components/jobs-badge'

const PER_PAGE = 20

const SOURCE_OPTIONS = ['all', 'demo_seed', 'iso7010', 'wikimedia', 'openverse', 'manual_upload', 'web_promoted']
const LICENSE_OPTIONS = ['Public Domain', 'CC0', 'CC-BY 4.0', 'CC-BY-SA 4.0', 'Pexels License', 'Proprietary']

export function ImageLibraryAdmin() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [previewEntry, setPreviewEntry] = useState<ImageLibraryAdminEntry | null>(null)

  const listQ = useQuery({
    queryKey: ['admin', 'images', page, sourceFilter] as const,
    queryFn: () =>
      api.adminListImages({
        page,
        per_page: PER_PAGE,
        source: sourceFilter !== 'all' ? sourceFilter : undefined,
      }),
  })

  const deleteMut = useMutation({
    mutationFn: (imageId: string) => api.adminDeleteImage(imageId),
    onSuccess: () => {
      toast.success('Immagine eliminata')
      qc.invalidateQueries({ queryKey: ['admin', 'images'] })
      setPreviewEntry(null)
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : 'Errore eliminazione')
    },
  })

  // Summary card aggregates
  const summary = useMemo(() => {
    const total = listQ.data?.total ?? 0
    const entries = listQ.data?.entries ?? []
    const bySource = new Map<string, number>()
    let totalUsage = 0
    for (const e of entries) {
      bySource.set(e.source, (bySource.get(e.source) ?? 0) + 1)
      totalUsage += e.usage_count
    }
    return { total, bySource, totalUsage, pageCount: entries.length }
  }, [listQ.data])

  const totalPages = Math.max(1, Math.ceil((listQ.data?.total ?? 0) / PER_PAGE))

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center gap-2'>
          <JobsBadge />
          <HelpButton />
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mb-4 flex items-center gap-2'>
          <Button variant='ghost' size='sm' asChild>
            <Link to='/admin' className='gap-1'>
              <ArrowLeft className='size-4' /> Admin
            </Link>
          </Button>
        </div>

        <div className='mb-6 flex flex-wrap items-end justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>Image Library</h1>
            <p className='text-sm text-muted-foreground'>
              Audit asset bank visivo: {summary.total} entries totali,{' '}
              {summary.totalUsage} usi accumulati.
            </p>
          </div>
          <Button
            onClick={() => setUploadOpen(true)}
            className='bg-brand-primary hover:bg-brand-primary/90 gap-2'
          >
            <UploadIcon className='size-4' />
            Carica immagine
          </Button>
        </div>

        {/* Summary cards */}
        <section className='mb-6 grid gap-4 sm:grid-cols-3'>
          <Card>
            <CardHeader>
              <CardDescription>Totale</CardDescription>
              <CardTitle className='text-3xl tabular-nums'>{summary.total}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Per sorgente (in pagina)</CardDescription>
              <div className='mt-1 flex flex-wrap gap-1'>
                {[...summary.bySource.entries()].map(([src, count]) => (
                  <Badge key={src} variant='secondary'>
                    {src}: {count}
                  </Badge>
                ))}
                {summary.bySource.size === 0 && (
                  <span className='text-sm text-muted-foreground'>—</span>
                )}
              </div>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Usi totali (in pagina)</CardDescription>
              <CardTitle className='text-3xl tabular-nums'>{summary.totalUsage}</CardTitle>
            </CardHeader>
          </Card>
        </section>

        {/* Filter row */}
        <section className='mb-4 flex flex-wrap items-center gap-3'>
          <div className='flex items-center gap-2'>
            <Label className='text-sm'>Sorgente</Label>
            <Select
              value={sourceFilter}
              onValueChange={(v) => {
                setSourceFilter(v)
                setPage(1)
              }}
            >
              <SelectTrigger className='w-[200px]'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SOURCE_OPTIONS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s === 'all' ? 'Tutte' : s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </section>

        {/* Library table */}
        {listQ.isLoading ? (
          <Skeleton className='h-96 w-full' />
        ) : !listQ.data?.entries?.length ? (
          <Card>
            <CardHeader className='items-center text-center'>
              <ImageOff className='size-12 text-muted-foreground' />
              <CardTitle>Nessuna immagine</CardTitle>
              <CardDescription>
                {sourceFilter !== 'all'
                  ? `Nessun risultato per sorgente "${sourceFilter}". Rimuovi il filtro o carica nuove immagini.`
                  : 'Library vuota. Carica la prima immagine per iniziare.'}
              </CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className='w-24'>Anteprima</TableHead>
                  <TableHead>File / Tag</TableHead>
                  <TableHead>Sorgente</TableHead>
                  <TableHead>Licenza</TableHead>
                  <TableHead className='text-right'>Usi</TableHead>
                  <TableHead className='w-16'></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {listQ.data.entries.map((e) => (
                  <TableRow
                    key={e.id}
                    className='cursor-pointer hover:bg-muted/50'
                    onClick={() => setPreviewEntry(e)}
                  >
                    <TableCell>
                      <div className='size-16 overflow-hidden rounded-md border bg-muted/30'>
                        <img
                          // F11 D-231 + F12 fix: backend monta assets/ a
                          // /static/assets. Su prod Vercel non proxia
                          // /static al backend Railway → 404 (rispondeva
                          // l'SPA HTML, non l'immagine). Uso API_BASE
                          // assoluto: in prod = origin Railway, in dev
                          // = http://localhost:8000.
                          src={`${API_BASE}/static/${e.file_path}`}
                          alt={e.tags[0] ?? 'image'}
                          className='size-full object-cover'
                          loading='lazy'
                          onError={(ev) => {
                            ;(ev.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className='font-mono text-xs text-muted-foreground'>
                        {e.file_path.split('/').slice(-1)[0]}
                      </div>
                      <div className='mt-1 flex flex-wrap gap-1'>
                        {e.tags.slice(0, 5).map((t) => (
                          <Badge key={t} variant='outline' className='text-[10px]'>
                            {t}
                          </Badge>
                        ))}
                        {e.tags.length > 5 && (
                          <span className='text-[10px] text-muted-foreground'>
                            +{e.tags.length - 5}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant='secondary'>{e.source}</Badge>
                    </TableCell>
                    <TableCell className='text-sm text-muted-foreground'>
                      {e.license ?? '—'}
                    </TableCell>
                    <TableCell className='text-right tabular-nums'>
                      {e.usage_count}
                    </TableCell>
                    <TableCell onClick={(ev) => ev.stopPropagation()}>
                      <Button
                        variant='ghost'
                        size='icon'
                        onClick={() => deleteMut.mutate(e.id)}
                        disabled={deleteMut.isPending}
                      >
                        <Trash2 className='size-4 text-destructive' />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className='mt-4 flex items-center justify-between'>
            <p className='text-sm text-muted-foreground'>
              Pagina {page} di {totalPages}
            </p>
            <div className='flex gap-2'>
              <Button
                variant='outline'
                size='sm'
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Precedente
              </Button>
              <Button
                variant='outline'
                size='sm'
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Successiva
              </Button>
            </div>
          </div>
        )}

        <UploadImageDialog
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          onUploaded={() => {
            qc.invalidateQueries({ queryKey: ['admin', 'images'] })
            setUploadOpen(false)
          }}
        />

        <PreviewImageDialog
          entry={previewEntry}
          onOpenChange={(open) => !open && setPreviewEntry(null)}
        />
      </Main>
    </>
  )
}

// ─── Upload Dialog ───

function UploadImageDialog({
  open,
  onOpenChange,
  onUploaded,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUploaded: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [tags, setTags] = useState('')
  const [license, setLicense] = useState('Proprietary')
  const [attribution, setAttribution] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')

  const mut = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Seleziona un file')
      if (!tags.trim()) throw new Error('Almeno 1 tag obbligatorio')
      return api.adminUploadImage({
        file,
        tags: tags.trim(),
        source: 'manual_upload',
        license,
        attribution: attribution.trim() || undefined,
        source_url: sourceUrl.trim() || undefined,
      })
    },
    onSuccess: () => {
      toast.success('Immagine caricata')
      setFile(null)
      setTags('')
      setAttribution('')
      setSourceUrl('')
      onUploaded()
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : (err as Error).message)
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-md'>
        <DialogHeader>
          <DialogTitle>Carica immagine in library</DialogTitle>
          <DialogDescription>
            PNG o JPEG, max 5MB. Tag e attribution salvati per audit.
          </DialogDescription>
        </DialogHeader>
        <div className='space-y-4'>
          <div className='space-y-2'>
            <Label htmlFor='upload-file'>File</Label>
            <Input
              id='upload-file'
              type='file'
              accept='image/png, image/jpeg'
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='upload-tags'>Tag (separati da virgola)</Label>
            <Input
              id='upload-tags'
              placeholder='es. casco, cantiere, dpi'
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='upload-license'>Licenza</Label>
            <Select value={license} onValueChange={setLicense}>
              <SelectTrigger id='upload-license'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LICENSE_OPTIONS.map((l) => (
                  <SelectItem key={l} value={l}>
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className='space-y-2'>
            <Label htmlFor='upload-attribution'>Attribution (opzionale)</Label>
            <Input
              id='upload-attribution'
              placeholder='es. Pexels — Anonymous'
              value={attribution}
              onChange={(e) => setAttribution(e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='upload-source-url'>Source URL (opzionale)</Label>
            <Input
              id='upload-source-url'
              placeholder='https://...'
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant='ghost' onClick={() => onOpenChange(false)} disabled={mut.isPending}>
            Annulla
          </Button>
          <Button
            onClick={() => mut.mutate()}
            disabled={!file || !tags.trim() || mut.isPending}
            className='bg-brand-primary hover:bg-brand-primary/90'
          >
            {mut.isPending && <Loader2 className='mr-2 size-4 animate-spin' />}
            Carica
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Preview Dialog ───

function PreviewImageDialog({
  entry,
  onOpenChange,
}: {
  entry: ImageLibraryAdminEntry | null
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={!!entry} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-2xl'>
        <DialogHeader>
          <DialogTitle>{entry?.file_path.split('/').slice(-1)[0]}</DialogTitle>
          <DialogDescription className='font-mono text-xs'>{entry?.file_path}</DialogDescription>
        </DialogHeader>
        {entry && (
          <div className='space-y-3'>
            <div className='flex justify-center rounded-md border bg-muted/30 p-2'>
              <img
                // F11 D-231 + F12 fix: backend monta assets/ a /static/assets.
                // Vercel non proxia /static a Railway → uso API_BASE assoluto.
                src={`${API_BASE}/static/${entry.file_path}`}
                alt={entry.tags[0] ?? 'preview'}
                className='max-h-96 object-contain'
              />
            </div>
            <dl className='grid grid-cols-2 gap-2 text-sm'>
              <dt className='text-muted-foreground'>Sorgente</dt>
              <dd>
                <Badge variant='secondary'>{entry.source}</Badge>
              </dd>
              <dt className='text-muted-foreground'>Licenza</dt>
              <dd>{entry.license ?? '—'}</dd>
              <dt className='text-muted-foreground'>Attribution</dt>
              <dd className='break-all'>{entry.attribution ?? '—'}</dd>
              <dt className='text-muted-foreground'>Dimensione</dt>
              <dd>
                {entry.width}×{entry.height} ({Math.round((entry.bytes ?? 0) / 1024)} KB)
              </dd>
              <dt className='text-muted-foreground'>Usi</dt>
              <dd className='tabular-nums'>{entry.usage_count}</dd>
              <dt className='text-muted-foreground'>Tag</dt>
              <dd>
                <div className='flex flex-wrap gap-1'>
                  {entry.tags.map((t) => (
                    <Badge key={t} variant='outline'>
                      {t}
                    </Badge>
                  ))}
                </div>
              </dd>
            </dl>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
