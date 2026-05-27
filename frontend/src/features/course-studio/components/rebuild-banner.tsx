/**
 * RebuildBanner — banner "modifiche non rigenerate" + pulsante per ricostruire
 * e scaricare il file completo aggiornato (FASE 11).
 *
 * Appare quando il corso è dirty=true (l'utente ha modificato slide ma non ha
 * ancora rigenerato PPTX/PDF/audio). Click "Rigenera tutto" → POST /rebuild →
 * il backend ricostruisce gli artefatti col contenuto corrente. Poi l'utente
 * può scaricare il file completo dal dettaglio corso.
 */

import { useMutation } from '@tanstack/react-query'
import { Download, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function RebuildBanner({
  courseId,
  onRebuildStarted,
}: {
  courseId: string
  onRebuildStarted?: () => void
}) {
  const rebuildMut = useMutation({
    mutationFn: () => api.rebuildCourse(courseId),
    onSuccess: () => {
      toast.success(
        'Rigenerazione avviata. PPTX/PDF/audio verranno aggiornati (5-10 min).',
      )
      onRebuildStarted?.()
    },
    onError: () => toast.error('Avvio rigenerazione fallito'),
  })

  const downloadMut = useMutation({
    mutationFn: async () => {
      const blob = await api.downloadCourse(courseId, 'pptx')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `corso_${courseId}.pptx`
      a.click()
      URL.revokeObjectURL(url)
    },
    onError: () => toast.error('Download fallito'),
  })

  return (
    <div className="border-primary/40 bg-primary/5 flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div>
        <p className="text-foreground text-sm font-medium">
          Hai modifiche non rigenerate
        </p>
        <p className="text-muted-foreground text-xs">
          Il PPTX/PDF/audio scaricabili sono ancora la versione precedente.
          Rigenera per applicare le modifiche.
        </p>
      </div>
      <div className="flex gap-2">
        <Button
          onClick={() => rebuildMut.mutate()}
          disabled={rebuildMut.isPending}
        >
          {rebuildMut.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Rigenera tutto
        </Button>
        <Button
          variant="outline"
          onClick={() => downloadMut.mutate()}
          disabled={downloadMut.isPending}
        >
          <Download className="mr-2 h-4 w-4" /> Scarica PPTX
        </Button>
      </div>
    </div>
  )
}
