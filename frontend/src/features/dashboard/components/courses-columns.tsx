/**
 * Column definitions for the courses DataTable.
 *
 * Columns mirror BP §10 `CourseSummary` plus a derived `target` label
 * (discente/formatore). Sortable on title, status, created_at. Filter
 * functions on `status` and `target` enable the faceted filters in the
 * toolbar.
 *
 * Row actions live in a separate file (`courses-row-actions.tsx`) and
 * receive `role` + dispatch handlers via the `meta` field on the table
 * options (TanStack idiom for plumbing context to cells without prop
 * drilling through 200 lines).
 */

import { type ColumnDef } from '@tanstack/react-table'
import { type CourseSummary } from '@/lib/api'
import { DataTableColumnHeader } from '@/components/data-table'
import { courseStatuses, courseTargets } from '../data/courses-meta'
import { CourseStatusBadge } from './course-status-badge'
import { CoursesRowActions } from './courses-row-actions'

// `meta` passed from the table options — see courses-table.tsx.
declare module '@tanstack/react-table' {
  interface TableMeta<TData extends unknown> {
    role?: string
    onDelete?: (course: TData & CourseSummary) => void
    onOpenDetail?: (course: TData & CourseSummary) => void
  }
}

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

export const coursesColumns: ColumnDef<CourseSummary>[] = [
  {
    accessorKey: 'title',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Titolo' />
    ),
    meta: { className: 'min-w-40 max-w-0 w-2/5', tdClassName: 'ps-4' },
    cell: ({ row }) => (
      <span className='truncate font-medium' title={row.getValue('title')}>
        {row.getValue('title')}
      </span>
    ),
  },
  {
    accessorKey: 'course_type',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Tipo' />
    ),
    meta: { className: 'min-w-32' },
    cell: ({ row }) => (
      <span className='text-sm text-muted-foreground'>
        {row.getValue('course_type')}
      </span>
    ),
  },
  {
    accessorKey: 'target',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Target' />
    ),
    meta: { className: 'w-32' },
    cell: ({ row }) => {
      const meta = courseTargets.find((t) => t.value === row.getValue('target'))
      return <span>{meta?.label ?? row.getValue('target')}</span>
    },
    filterFn: (row, id, value: string[]) => value.includes(row.getValue(id)),
  },
  {
    accessorKey: 'duration_hours',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Durata' />
    ),
    meta: { className: 'w-24 text-end', tdClassName: 'text-end tabular-nums' },
    cell: ({ row }) => {
      const h = Number(row.getValue('duration_hours'))
      return <span>{Number.isInteger(h) ? h : h.toFixed(1)} h</span>
    },
  },
  {
    accessorKey: 'status',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Stato' />
    ),
    meta: { className: 'w-40' },
    cell: ({ row }) => <CourseStatusBadge status={row.getValue('status')} />,
    filterFn: (row, id, value: string[]) => value.includes(row.getValue(id)),
  },
  {
    accessorKey: 'created_at',
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title='Data' />
    ),
    meta: { className: 'w-32' },
    cell: ({ row }) => {
      const iso = row.getValue('created_at') as string
      return (
        <span className='text-sm text-muted-foreground'>
          {dateFmt.format(new Date(iso))}
        </span>
      )
    },
  },
  {
    id: 'actions',
    meta: { className: 'w-12' },
    cell: ({ row, table }) => {
      const m = table.options.meta
      if (!m?.onDelete || !m.onOpenDetail) return null
      return (
        <CoursesRowActions
          row={row}
          role={m.role}
          onDelete={m.onDelete}
          onOpenDetail={m.onOpenDetail}
        />
      )
    },
  },
]

export { courseStatuses, courseTargets }
