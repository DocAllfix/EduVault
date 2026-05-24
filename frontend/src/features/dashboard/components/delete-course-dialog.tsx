/**
 * Confirmation dialog for the course soft-delete action.
 *
 * Backend behaviour: `DELETE /api/courses/{id}` sets `status='archived'`
 * (BP §10). It is **not** a hard delete — the row stays in DB for audit
 * and L2 promotion lineage. We surface this in the copy so users don't
 * mis-read "Elimina" as destructive.
 */

import { useState } from 'react'
import { toast } from 'sonner'

import { api, ApiError, type CourseSummary } from '@/lib/api'
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

type DeleteCourseDialogProps = {
  course: CourseSummary | null
  onOpenChange: (open: boolean) => void
  onDeleted: () => void
}

export function DeleteCourseDialog({
  course,
  onOpenChange,
  onDeleted,
}: DeleteCourseDialogProps) {
  const [isLoading, setIsLoading] = useState(false)

  async function handleConfirm() {
    if (!course) return
    setIsLoading(true)
    try {
      await api.deleteCourse(course.id)
      toast.success('Corso archiviato.')
      onDeleted()
      onOpenChange(false)
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : 'Archiviazione non riuscita.'
      toast.error(msg)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <AlertDialog open={course !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Archiviare il corso?</AlertDialogTitle>
          <AlertDialogDescription>
            {course
              ? `«${course.title}» verrà spostato negli archivi. Resta consultabile da admin per audit ma non comparirà più nelle liste operative. L'azione non è reversibile dall'interfaccia.`
              : ''}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isLoading}>Annulla</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault() // keep dialog open until handler resolves
              void handleConfirm()
            }}
            disabled={isLoading}
            className='bg-destructive text-white hover:bg-destructive/90'
          >
            {isLoading ? 'Archiviazione…' : 'Archivia'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
