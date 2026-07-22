/**
 * Step 3 — Parametri.
 *
 * Three controls: duration_hours (number), region (select),
 * slide_density (select). When the course type chosen at step 1 has
 * `min_hours == max_hours` (most cases in the current catalog — 4h, 8h,
 * 12h fixed), we display that as a hint and pre-fill if the user hasn't
 * touched the field yet. We do NOT lock it: the operator might legally
 * override for internal exercises (BP doesn't forbid it; the backend
 * `Field(gt=0, le=16)` is the hard guardrail).
 */

import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useFormContext } from 'react-hook-form'

import { api } from '@/lib/api'
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DENSITY_OPTIONS, REGIONS, type WizardValues } from '../schema'

export function Step3Params() {
  const form = useFormContext<WizardValues>()
  const catalogQ = useQuery({
    queryKey: ['catalog'] as const,
    queryFn: () => api.getCatalog(),
    staleTime: 5 * 60 * 1000,
  })

  const courseType = form.watch('course_type')
  const entry = catalogQ.data?.[courseType] as
    | { min_hours?: number; max_hours?: number }
    | undefined

  // Pre-fill duration from catalog when the course type changes — but
  // only if the user hasn't dirtied the field. Otherwise an operator
  // who set 8h and then jumped back to step 1 would lose their input.
  useEffect(() => {
    if (!entry?.min_hours) return
    const dirty = form.getFieldState('duration_hours').isDirty
    if (!dirty) form.setValue('duration_hours', entry.min_hours)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry?.min_hours, entry?.max_hours, courseType])

  const minH = entry?.min_hours ?? 0.5
  const maxH = Math.min(entry?.max_hours ?? 16, 16)

  return (
    <div className='space-y-4'>
      <FormField
        control={form.control}
        name='duration_hours'
        render={({ field }) => (
          <FormItem>
            <FormLabel>Durata (ore)</FormLabel>
            <FormControl>
              <Input
                type='number'
                min={minH}
                max={maxH}
                step={0.5}
                value={field.value ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  field.onChange(v === '' ? undefined : Number(v))
                }}
                onBlur={field.onBlur}
              />
            </FormControl>
            <FormDescription>
              {entry?.min_hours && entry.min_hours === entry.max_hours
                ? `Durata standard per questo corso: ${entry.min_hours} ore.`
                : `Da ${minH} a ${maxH} ore (vincolo Pydantic gt=0, le=16).`}
            </FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name='region'
        render={({ field }) => (
          <FormItem>
            <FormLabel>Regione</FormLabel>
            <FormControl>
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger>
                  <SelectValue placeholder='Seleziona regione…' />
                </SelectTrigger>
                <SelectContent>
                  {REGIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormControl>
            <FormDescription>
              Imposta il filtro normative regionali. «Nazionale» è il default.
            </FormDescription>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name='seconds_per_slide'
        render={({ field }) => {
          const secs = Number(field.value) || 45
          const mins = Math.floor(secs / 60)
          const rest = secs % 60
          const human =
            secs < 60
              ? `${secs} secondi`
              : `${mins} min${rest ? ` ${rest}s` : ''}`
          return (
            <FormItem>
              <FormLabel>Durata per slide</FormLabel>
              <FormControl>
                <Input
                  type='number'
                  min={40}
                  max={240}
                  step={5}
                  value={field.value ?? ''}
                  onChange={(e) => {
                    const v = e.target.value
                    field.onChange(v === '' ? undefined : Number(v))
                  }}
                  onBlur={field.onBlur}
                />
              </FormControl>
              <FormDescription>
                Quanto dura ogni slide ({human}). Più alta = meno slide, ognuna
                con narrazione più lunga. Da 40 secondi a 4 minuti; il default è
                45 secondi.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )
        }}
      />

      <FormField
        control={form.control}
        name='slide_density'
        render={({ field }) => (
          <FormItem>
            <FormLabel>Densità slide</FormLabel>
            <FormControl>
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DENSITY_OPTIONS.map((d) => (
                    <SelectItem key={d.value} value={d.value}>
                      <div className='flex flex-col'>
                        <span>{d.label}</span>
                        <span className='text-xs text-muted-foreground'>{d.desc}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </div>
  )
}
