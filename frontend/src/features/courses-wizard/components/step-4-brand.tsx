/**
 * Step 4 — Brand preset.
 *
 * Loads `api.getBrandPresets()` (admin-gated — operators see 403; we
 * surface a friendly message). Each preset shows a swatch row of its
 * palette colours so the operator confirms visually that they picked
 * the right one. The default preset is pre-selected.
 *
 * `palette` is `dict[str, Any]` in the OpenAPI schema (BP admin endpoint
 * returns the JSONB column as-is). At runtime values are CSS hex strings
 * (seed.py initializes 5 named slots: primary/secondary/accent/danger/
 * success). We render whatever string-valued entries exist — robust to
 * additional brand presets seeded later.
 */

import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useFormContext } from 'react-hook-form'

import { api, ApiError, type BrandPresetSummary } from '@/lib/api'
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

function paletteSwatches(palette: Record<string, unknown>): { name: string; hex: string }[] {
  const out: { name: string; hex: string }[] = []
  for (const [name, value] of Object.entries(palette)) {
    if (typeof value === 'string' && /^#[0-9a-f]{3,8}$/i.test(value)) {
      out.push({ name, hex: value })
    }
  }
  return out
}

export function Step4Brand() {
  const form = useFormContext<WizardValues>()
  const presetsQ = useQuery({
    queryKey: ['brand-presets'] as const,
    queryFn: async () => {
      try {
        return await api.getBrandPresets()
      } catch (err) {
        // 403 (operator role): show empty list + helpful message.
        if (err instanceof ApiError && err.status === 403) return [] as BrandPresetSummary[]
        throw err
      }
    },
    staleTime: 10 * 60 * 1000,
  })

  const value = form.watch('brand_preset_id')
  const presets = presetsQ.data ?? []
  const selected = presets.find((p) => p.id === value)

  // Pre-fill the default preset on first load if nothing is selected.
  useEffect(() => {
    if (value || presets.length === 0) return
    const def = presets.find((p) => p.is_default) ?? presets[0]
    if (def) form.setValue('brand_preset_id', def.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presets.length, value])

  return (
    <div className='space-y-4'>
      <FormField
        control={form.control}
        name='brand_preset_id'
        render={({ field }) => (
          <FormItem>
            <FormLabel>Brand preset</FormLabel>
            <FormControl>
              {presetsQ.isLoading ? (
                <Skeleton className='h-10 w-full' />
              ) : (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder='Seleziona brand preset…' />
                  </SelectTrigger>
                  <SelectContent>
                    {presets.length === 0 && (
                      <div className='px-3 py-2 text-sm text-muted-foreground'>
                        Nessun brand preset disponibile per il tuo ruolo.
                      </div>
                    )}
                    {presets.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                        {p.is_default && (
                          <span className='ms-2 text-xs text-muted-foreground'>(default)</span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormControl>
            <FormDescription>
              Definisce palette colori e font del PPTX / PDF generato.
            </FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />

      {selected && (
        <div className='rounded-md border bg-muted/30 p-4'>
          <div className='mb-2 text-sm font-medium'>Anteprima palette</div>
          <div className='flex flex-wrap gap-3'>
            {paletteSwatches(selected.palette).map((sw) => (
              <div key={sw.name} className='flex flex-col items-center gap-1'>
                <span
                  className='size-10 rounded-md border'
                  style={{ backgroundColor: sw.hex }}
                  aria-label={`${sw.name}: ${sw.hex}`}
                />
                <span className='text-[10px] uppercase tracking-wide text-muted-foreground'>
                  {sw.name}
                </span>
                <span className='font-mono text-[10px] text-muted-foreground'>{sw.hex}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
