/**
 * Courses DataTable — EduVault Dashboard.
 *
 * Structural fork of the template's `tasks-table.tsx` (REI-1: adapt,
 * don't reinvent). Differences:
 *   - data type is `CourseSummary` from `lib/api.ts`
 *   - no row selection (bulk archive isn't in v1.0; one-at-a-time keeps
 *     the audit trail human-readable per BP §16)
 *   - global filter scopes to `title` only
 *   - faceted filters expose `status` and `target` (the prompt's
 *     "filtri per stato e per target")
 *   - URL-synced search keys: `page`, `pageSize`, `filter`, `status`,
 *     `target`. Route schema mirrors this in 6.7 step "update route".
 *   - parent receives `role` + delete/detail handlers via TanStack's
 *     `meta` (see `courses-columns.tsx` declare module).
 *
 * The "Tipo" column is intentionally not faceted: course types come from
 * the dynamic COURSE_CATALOG (FASE 6.8) and listing them here would mean
 * hardcoding them — REI-5 forbids that. Free-text title filter covers the
 * narrowing need in the meantime.
 */

import { useEffect, useState } from 'react'
import { getRouteApi } from '@tanstack/react-router'
import {
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFacetedRowModel,
  getFacetedUniqueValues,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'

import type { CourseSummary } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useTableUrlState } from '@/hooks/use-table-url-state'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DataTablePagination, DataTableToolbar } from '@/components/data-table'
import { courseStatuses, courseTargets } from '../data/courses-meta'
import { coursesColumns } from './courses-columns'

const route = getRouteApi('/_authenticated/dashboard')

type CoursesTableProps = {
  data: CourseSummary[]
  isLoading: boolean
  role: string | undefined
  onDelete: (course: CourseSummary) => void
  onOpenDetail: (course: CourseSummary) => void
}

export function CoursesTable({
  data,
  isLoading,
  role,
  onDelete,
  onOpenDetail,
}: CoursesTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})

  const {
    globalFilter,
    onGlobalFilterChange,
    columnFilters,
    onColumnFiltersChange,
    pagination,
    onPaginationChange,
    ensurePageInRange,
  } = useTableUrlState({
    search: route.useSearch(),
    navigate: route.useNavigate(),
    pagination: { defaultPage: 1, defaultPageSize: 10 },
    globalFilter: { enabled: true, key: 'filter' },
    columnFilters: [
      { columnId: 'status', searchKey: 'status', type: 'array' },
      { columnId: 'target', searchKey: 'target', type: 'array' },
    ],
  })

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns: coursesColumns,
    state: {
      sorting,
      columnVisibility,
      columnFilters,
      globalFilter,
      pagination,
    },
    meta: { role, onDelete, onOpenDetail },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    globalFilterFn: (row, _columnId, filterValue) => {
      const title = String(row.getValue('title')).toLowerCase()
      const type = String(row.getValue('course_type')).toLowerCase()
      const q = String(filterValue).toLowerCase()
      return title.includes(q) || type.includes(q)
    },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFacetedRowModel: getFacetedRowModel(),
    getFacetedUniqueValues: getFacetedUniqueValues(),
    onPaginationChange,
    onGlobalFilterChange,
    onColumnFiltersChange,
  })

  const pageCount = table.getPageCount()
  useEffect(() => {
    ensurePageInRange(pageCount)
  }, [pageCount, ensurePageInRange])

  return (
    <div
      className={cn(
        'max-sm:has-[div[role="toolbar"]]:mb-16',
        'flex flex-1 flex-col gap-4',
      )}
    >
      <DataTableToolbar
        table={table}
        searchPlaceholder='Cerca per titolo o tipo…'
        filters={[
          {
            columnId: 'status',
            title: 'Stato',
            options: courseStatuses.map((s) => ({
              label: s.label,
              value: s.value,
              icon: s.icon,
            })),
          },
          {
            columnId: 'target',
            title: 'Target',
            options: courseTargets.map((t) => ({
              label: t.label,
              value: t.value,
            })),
          },
        ]}
      />
      <div className='overflow-hidden rounded-md border'>
        <Table className='min-w-xl'>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    className={cn(
                      header.column.columnDef.meta?.className,
                      header.column.columnDef.meta?.thClassName,
                    )}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={coursesColumns.length}
                  className='h-24 text-center text-muted-foreground'
                >
                  Caricamento corsi in corso…
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={cn(
                        cell.column.columnDef.meta?.className,
                        cell.column.columnDef.meta?.tdClassName,
                      )}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={coursesColumns.length}
                  className='h-24 text-center'
                >
                  Nessun corso. Avvia il primo con «Nuovo Corso».
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <DataTablePagination table={table} className='mt-auto' />
    </div>
  )
}
