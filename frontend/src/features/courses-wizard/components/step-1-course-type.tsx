/**
 * Step 1 — Tipo Corso.
 *
 * Loads COURSE_CATALOG via `api.getCatalog()`. Selecting a course type
 * also bubbles up `min_hours/max_hours/regional` so Step 3 (Params) can
 * constrain `duration_hours` and Step 6 (Confirm) can show the right
 * resolved data — wired through react-hook-form's `setValue` on the
 * parent form (via `useFormContext`).
 *
 * UI: a single Select. The catalog has only 6 entries today so a Select
 * is correct (a Combobox would be over-engineered). A "regs" hint and
 * a "default modules" preview appear under the field once a value is
 * picked — orientates the user without forcing the next step.
 */

import { useQuery } from '@tanstack/react-query'
import { useFormContext } from 'react-hook-form'

import { api, type Catalog } from '@/lib/api'
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import type { WizardValues } from '../schema'

type CatalogEntry = {
  title?: string
  regs?: string[]
  min_hours?: number
  max_hours?: number
  regional?: boolean
  default_modules?: string[]
}

export function Step1CourseType() {
  const form = useFormContext<WizardValues>()
  const catalogQ = useQuery({
    queryKey: ['catalog'] as const,
    queryFn: () => api.getCatalog(),
    staleTime: 5 * 60 * 1000, // catalog is config-driven, change is rare
  })

  const selected = form.watch('course_type')
  const catalog: Catalog = catalogQ.data ?? {}
  const entries = Object.entries(catalog) as [string, CatalogEntry][]
  const selectedEntry = selected ? catalog[selected] as CatalogEntry | undefined : undefined

  return (
    <div className='space-y-4'>
      <FormField
        control={form.control}
        name='course_type'
        render={({ field }) => (
          <FormItem>
            <FormLabel>Tipo di corso</FormLabel>
            <FormControl>
              {catalogQ.isLoading ? (
                <Skeleton className='h-10 w-full' />
              ) : (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder='Seleziona un tipo di corso…' />
                  </SelectTrigger>
                  <SelectContent>
                    {entries.length === 0 && (
                      <div className='px-3 py-2 text-sm text-muted-foreground'>
                        Catalogo non disponibile.
                      </div>
                    )}
                    {entries.map(([slug, info]) => (
                      <SelectItem key={slug} value={slug}>
                        {info.title ?? slug}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormControl>
            <FormDescription>
              Il tipo determina le normative consultate e la struttura predefinita.
            </FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />

      {selectedEntry && (
        <div className='rounded-md border bg-muted/30 p-4 text-sm'>
          <div className='mb-2 font-medium text-foreground'>
            {selectedEntry.title}
          </div>
          {selectedEntry.regs && selectedEntry.regs.length > 0 && (
            <p className='mb-2 text-muted-foreground'>
              <span className='font-medium text-foreground'>Normative:</span>{' '}
              {selectedEntry.regs.join(', ')}
            </p>
          )}
          {selectedEntry.default_modules && selectedEntry.default_modules.length > 0 && (
            <div>
              <span className='font-medium text-foreground'>Moduli predefiniti:</span>
              <ul className='mt-1 list-inside list-disc text-muted-foreground'>
                {selectedEntry.default_modules.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}
          {(selectedEntry.min_hours || selectedEntry.max_hours) && (
            <p className='mt-2 text-xs text-muted-foreground'>
              Durata richiesta: {selectedEntry.min_hours ?? '?'}
              {selectedEntry.min_hours !== selectedEntry.max_hours
                ? `–${selectedEntry.max_hours ?? '?'}`
                : ''}{' '}
              ore.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function getCatalogEntry(catalog: Catalog, slug: string): CatalogEntry | undefined {
  return catalog[slug] as CatalogEntry | undefined
}
