/**
 * RebuildBanner — banner "modifiche non rigenerate" + pulsante per ricostruire
 * e scaricare il file completo aggiornato (FASE 11).
 *
 * Appare quando il corso è dirty=true (l'utente ha modificato slide ma non ha
 * ancora rigenerato PPTX/PDF/audio). Click "Rigenera tutto" → POST /rebuild →
 * il backend ricostruisce gli artefatti col contenuto corrente. Poi l'utente
 * può scaricare il file completo dal dettaglio corso.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Download, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { api } from '@/lib/api'
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
import { Button } from '@/components/ui/button'

export function RebuildBanner({
  courseId,
  onRebuildStarted,
}: {
  courseId: string
  onRebuildStarted?: () => void
}) {
  const qc = useQueryClient()
  const rebuildMut = useMutation({
    mutationFn: () => api.rebuildCourse(courseId),
    onSuccess: () => {
      toast.success(
        'Rigenerazione avviata. PPTX e PDF pronti a breve; la narrazione vocale viene rigenerata in background (2-10 min).',
      )
      // Backend updates last_rebuilt_at + audio_manifest_path on completion.
      // Invalidate everything the user can be looking at right now so detail,
      // dashboard, slides list and slide previews all reflect the new state.
      qc.invalidateQueries({ queryKey: ['course-slides', courseId] })
      qc.invalidateQueries({ queryKey: ['course', courseId] })
      qc.invalidateQueries({ queryKey: ['courses'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
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
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button disabled={rebuildMut.isPending}>
              {rebuildMut.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Rigenera tutto
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <AlertTriangle className="text-amber-600 size-5" aria-hidden="true" />
                Rigenerare PPTX, PDF e audio?
              </AlertDialogTitle>
              <AlertDialogDescription>
                La rigenerazione ricostruisce PPTX, PDF e narrazione vocale
                <strong> dai contenuti correnti del corso nel sistema</strong>.
                Se hai modificato manualmente il PPTX in PowerPoint e lo hai
                ricaricato come versione definitiva, quelle modifiche manuali
                <strong> verranno sovrascritte</strong>. Procedi solo se vuoi
                applicare le modifiche fatte qui in Course Studio.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Annulla</AlertDialogCancel>
              <AlertDialogAction onClick={() => rebuildMut.mutate()}>
                Sì, rigenera tutto
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
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
