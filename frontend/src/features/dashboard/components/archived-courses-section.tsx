/**
 * F10 ArchivedCoursesSection — sezione dedicata corsi archiviati.
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Sezione separata sotto la tabella principale, accordion-style (collassata
 * di default per non rumorezzare la dashboard se zero archiviati o solo per
 * audit).
 *
 * Quando aperta mostra una tabella compatta con: titolo, target, archiviato il,
 * bottone "Elimina definitivamente" (red, conferma forte).
 *
 * REI-1: shadcn Card + Collapsible + Button. Niente design from scratch.
 */

import { useState } from 'react'
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api, ApiError, type CourseSummary } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

export interface ArchivedCoursesSectionProps {
  courses: CourseSummary[] | undefined
  isLoading: boolean
  onChange: () => void
}

export function ArchivedCoursesSection({
  courses,
  isLoading,
  onChange,
}: ArchivedCoursesSectionProps) {
  const [open, setOpen] = useState(false)
  const [pendingHardDelete, setPendingHardDelete] =
    useState<CourseSummary | null>(null)
  const queryClient = useQueryClient()

  const total = courses?.length ?? 0
  // Auto-collapse se zero archiviati (no rumore visivo).
  // Se totale > 0 e l'utente non ha mai cliccato, resta collapsed di default
  // per coerenza con pattern Stripe Dashboard (dettagli on-demand).

  const hardDeleteMut = useMutation({
    mutationFn: (course: CourseSummary) => api.hardDeleteCourse(course.id),
    onSuccess: () => {
      toast.success('Corso eliminato definitivamente.')
      setPendingHardDelete(null)
      onChange()
      void queryClient.invalidateQueries({
        // Both archived and non-archived queries need refresh.
        predicate: (q) =>
          Array.isArray(q.queryKey) && q.queryKey[0] === 'courses',
      })
    },
    onError: (err) => {
      const msg =
        err instanceof ApiError
          ? err.message
          : 'Eliminazione definitiva non riuscita.'
      toast.error(msg)
    },
  })

  // Non mostrare la sezione se sta caricando e ancora nessun dato — evita
  // flash visivo di "0 corsi" durante il primo fetch.
  if (isLoading && courses === undefined) return null

  return (
    <section
      aria-labelledby='archived-heading'
      className='scroll-mt-20 mt-8'
    >
      <button
        type='button'
        onClick={() => setOpen((v) => !v)}
        className='hover:bg-accent flex w-full items-center justify-between rounded-md px-2 py-2 text-left transition-colors'
        aria-expanded={open}
        aria-controls='archived-content'
      >
        <h2
          id='archived-heading'
          className='flex items-center gap-2 text-sm font-semibold tracking-tight'
        >
          {open ? (
            <ChevronDown className='size-4' aria-hidden='true' />
          ) : (
            <ChevronRight className='size-4' aria-hidden='true' />
          )}
          Corsi archiviati
          <Badge
            variant='outline'
            className='text-muted-foreground tabular-nums'
          >
            {total}
          </Badge>
        </h2>
        <span className='text-muted-foreground text-xs'>
          {total === 0
            ? 'Nessun corso archiviato'
            : open
              ? 'Click per nascondere'
              : 'Click per mostrare'}
        </span>
      </button>

      {open && (
        <div id='archived-content' className='mt-3'>
          {total === 0 ? (
            <Card>
              <CardContent className='text-muted-foreground py-6 text-center text-sm'>
                Nessun corso archiviato. I corsi eliminati dalla tabella
                principale appaiono qui per consentirne l’eliminazione
                definitiva.
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className='p-0'>
                <table className='w-full text-sm'>
                  <thead className='border-border border-b'>
                    <tr className='text-muted-foreground text-xs uppercase tracking-wider'>
                      <th className='px-4 py-2.5 text-left font-medium'>
                        Titolo
                      </th>
                      <th className='px-4 py-2.5 text-left font-medium'>
                        Target
                      </th>
                      <th className='px-4 py-2.5 text-left font-medium'>
                        Durata
                      </th>
                      <th className='px-4 py-2.5 text-left font-medium'>
                        Creato il
                      </th>
                      <th className='px-4 py-2.5 text-right font-medium'>
                        Azioni
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {courses!.map((c) => (
                      <tr
                        key={c.id}
                        className='border-border hover:bg-muted/40 border-b last:border-0 transition-colors'
                      >
                        <td className='px-4 py-2.5'>
                          <div className='line-clamp-1 font-medium'>
                            {c.title}
                          </div>
                          <div className='text-muted-foreground line-clamp-1 text-xs'>
                            {c.course_type}
                          </div>
                        </td>
                        <td className='px-4 py-2.5'>
                          <Badge variant='outline' className='text-xs'>
                            {c.target}
                          </Badge>
                        </td>
                        <td className='text-muted-foreground px-4 py-2.5 text-xs tabular-nums'>
                          {c.duration_hours}h
                        </td>
                        <td className='text-muted-foreground px-4 py-2.5 text-xs'>
                          {new Date(c.created_at).toLocaleDateString('it-IT', {
                            day: '2-digit',
                            month: 'short',
                            year: 'numeric',
                          })}
                        </td>
                        <td className='px-4 py-2.5 text-right'>
                          <Button
                            variant='ghost'
                            size='sm'
                            onClick={() => setPendingHardDelete(c)}
                            disabled={hardDeleteMut.isPending}
                            className='text-destructive hover:text-destructive hover:bg-destructive/10 h-7 gap-1 px-2 text-xs'
                          >
                            <Trash2
                              className='size-3.5'
                              aria-hidden='true'
                            />
                            Elimina definitivamente
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Hard delete confirm dialog */}
      <AlertDialog
        open={pendingHardDelete !== null}
        onOpenChange={(o) => {
          if (!o) setPendingHardDelete(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className='text-destructive'>
              Eliminare definitivamente?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingHardDelete
                ? `«${pendingHardDelete.title}» sarà rimosso definitivamente dal database. Verranno cancellati anche i log di generazione associati. L'azione non è reversibile.`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={hardDeleteMut.isPending}>
              Annulla
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                if (pendingHardDelete) {
                  hardDeleteMut.mutate(pendingHardDelete)
                }
              }}
              disabled={hardDeleteMut.isPending}
              className='bg-destructive text-white hover:bg-destructive/90'
            >
              {hardDeleteMut.isPending
                ? 'Eliminazione…'
                : 'Sì, elimina definitivamente'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
