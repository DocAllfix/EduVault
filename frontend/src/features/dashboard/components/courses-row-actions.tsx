/**
 * Per-row actions for the courses table.
 *
 * Visible items depend on the course `status` and the current user role
 * (we receive `role` as a prop so the parent can pass it once instead of
 * each row reading the auth store).
 *
 * Action map:
 *   Dettaglio          always
 *   Scarica → PPTX     when status ∈ {completed, certified}
 *   Scarica → PDF      when status ∈ {completed, certified}
 *   Scarica → Audio    when status ∈ {completed, certified}
 *   Certifica          when status == 'completed' and role ∈ {admin, reviewer}
 *   Elimina            when status != 'archived'
 *
 * Download triggers a blob download via `api.downloadCourse` + an
 * anchor click — no new HTTP libraries. Delete opens an `AlertDialog`
 * owned by the parent (DashboardProvider) to centralise the confirm
 * flow and avoid one dialog instance per row.
 */

import { DotsHorizontalIcon } from '@radix-ui/react-icons'
import { type Row } from '@tanstack/react-table'
import { Download, FileText, Headphones, Presentation, ShieldCheck, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, type CourseSummary, type DownloadFormat } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

type CoursesRowActionsProps = {
  row: Row<CourseSummary>
  role: string | undefined
  onDelete: (course: CourseSummary) => void
  onOpenDetail: (course: CourseSummary) => void
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Defer revoke a tick — Safari sometimes races on immediate revoke.
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

async function downloadAndSave(
  courseId: string,
  format: DownloadFormat,
  baseTitle: string,
): Promise<void> {
  try {
    const blob = await api.downloadCourse(courseId, format)
    // Backend FileResponse sets a filename; we re-derive a sensible one
    // because fetch+blob loses Content-Disposition by default and we
    // don't want to over-engineer with header parsing.
    const safeTitle = baseTitle.replace(/[^\w\-]+/g, '_').slice(0, 60) || courseId
    const ext = format === 'audio' || format === 'zip' ? 'zip' : format
    triggerBlobDownload(blob, `${safeTitle}.${ext}`)
  } catch (err) {
    const msg = err instanceof ApiError ? err.message : 'Download non riuscito.'
    toast.error(msg)
  }
}

async function certifyCourse(courseId: string): Promise<void> {
  try {
    await api.certifyCourse(courseId)
    toast.success('Corso certificato (livello L2).')
  } catch (err) {
    const msg = err instanceof ApiError ? err.message : 'Certificazione non riuscita.'
    toast.error(msg)
  }
}

export function CoursesRowActions({
  row,
  role,
  onDelete,
  onOpenDetail,
}: CoursesRowActionsProps) {
  const course = row.original
  const canDownload =
    course.status === 'completed' || course.status === 'certified'
  const canCertify =
    course.status === 'completed' &&
    (role === 'admin' || role === 'reviewer')
  const canDelete = course.status !== 'archived'

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button
          variant='ghost'
          className='flex h-8 w-8 p-0 data-[state=open]:bg-muted'
          aria-label='Azioni corso'
        >
          <DotsHorizontalIcon className='h-4 w-4' />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align='end' className='w-44'>
        <DropdownMenuItem onClick={() => onOpenDetail(course)}>
          Dettaglio
        </DropdownMenuItem>
        {canDownload && (
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <Download className='me-2 size-4' aria-hidden='true' />
              Scarica
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem
                onClick={() => downloadAndSave(course.id, 'pptx', course.title)}
              >
                <Presentation className='me-2 size-4' aria-hidden='true' />
                PPTX
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => downloadAndSave(course.id, 'pdf', course.title)}
              >
                <FileText className='me-2 size-4' aria-hidden='true' />
                PDF
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => downloadAndSave(course.id, 'audio', course.title)}
              >
                <Headphones className='me-2 size-4' aria-hidden='true' />
                Audio (ZIP)
              </DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        )}
        {canCertify && (
          <DropdownMenuItem onClick={() => certifyCourse(course.id)}>
            <ShieldCheck className='me-2 size-4' aria-hidden='true' />
            Certifica
          </DropdownMenuItem>
        )}
        {canDelete && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => onDelete(course)}
              variant='destructive'
            >
              <Trash2 className='me-2 size-4' aria-hidden='true' />
              Elimina
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
