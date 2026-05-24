/**
 * Step 6 — Riepilogo + conferma.
 *
 * Summarises every value chosen + computes the estimated slide count and
 * total spoken duration using THE SAME constants as the backend PacingEngine
 * (FASE 3.2, GAP-1 v2.0):
 *
 *   SECONDS_PER_SLIDE = 30
 *   slides = duration_hours * 60 * 60 / 30 = duration_hours * 120
 *
 * Keeping the formula client-side guarantees the user sees the same
 * number the backend will produce — no "I clicked Generate and got a
 * different size" surprise. If pacing changes server-side, this constant
 * must be updated in lockstep.
 */

import { useQuery } from '@tanstack/react-query'
import { useFormContext } from 'react-hook-form'
import { CheckCircle2 } from 'lucide-react'

import { api } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import {
  DENSITY_OPTIONS,
  OUTPUT_OPTIONS,
  REGIONS,
  type WizardValues,
} from '../schema'

const SECONDS_PER_SLIDE = 30 // mirrors PacingEngine.SECONDS_PER_SLIDE

export function Step6Confirm() {
  const form = useFormContext<WizardValues>()
  const values = form.watch()
  const catalogQ = useQuery({
    queryKey: ['catalog'] as const,
    queryFn: () => api.getCatalog(),
    staleTime: 5 * 60 * 1000,
  })
  const presetsQ = useQuery({
    queryKey: ['brand-presets'] as const,
    queryFn: () => api.getBrandPresets(),
    staleTime: 10 * 60 * 1000,
  })

  const entry = catalogQ.data?.[values.course_type] as { title?: string } | undefined
  const preset = presetsQ.data?.find((p) => p.id === values.brand_preset_id)
  const region = REGIONS.find((r) => r.value === values.region)
  const density = DENSITY_OPTIONS.find((d) => d.value === values.slide_density)

  const slides = Math.round((values.duration_hours ?? 0) * 3600 / SECONDS_PER_SLIDE)
  const minutes = Math.round((values.duration_hours ?? 0) * 60)

  return (
    <div className='space-y-4'>
      <p className='text-sm text-muted-foreground'>
        Controlla i parametri. Premendo «Genera Corso» la pipeline parte
        immediatamente. Potrai seguirne lo stato nel monitor di progresso.
      </p>

      <dl className='divide-y rounded-md border'>
        <SummaryRow label='Tipo corso' value={entry?.title ?? values.course_type} />
        <SummaryRow
          label='Destinatario'
          value={values.target === 'discente' ? 'Discente' : 'Formatore'}
        />
        <SummaryRow
          label='Durata'
          value={`${values.duration_hours} h (${minutes} min)`}
        />
        <SummaryRow label='Regione' value={region?.label ?? values.region} />
        <SummaryRow label='Densità slide' value={density?.label ?? values.slide_density} />
        <SummaryRow label='Brand preset' value={preset?.name ?? '—'} />
        <SummaryRow
          label='Output'
          value={
            <div className='flex flex-wrap gap-1'>
              {values.outputs.map((o) => {
                const m = OUTPUT_OPTIONS.find((x) => x.value === o)
                return (
                  <Badge key={o} variant='secondary'>
                    {m?.label ?? o}
                  </Badge>
                )
              })}
            </div>
          }
        />
      </dl>

      <div className='flex items-center gap-3 rounded-md border border-brand-primary/30 bg-brand-primary/5 p-4'>
        <CheckCircle2 className='size-5 text-brand-primary' aria-hidden='true' />
        <div className='flex-1 text-sm'>
          <div className='font-medium'>
            Stima: <span className='tabular-nums'>{slides}</span> slide
          </div>
          <div className='text-muted-foreground'>
            Calcolato come {values.duration_hours} h × 120 slide/h
            ({SECONDS_PER_SLIDE}s per slide). Tempo medio pipeline: ~5–15 minuti.
          </div>
        </div>
      </div>
    </div>
  )
}

function SummaryRow({
  label,
  value,
}: {
  label: string
  value: React.ReactNode
}) {
  return (
    <div className='grid grid-cols-3 gap-4 px-4 py-3 text-sm'>
      <dt className='text-muted-foreground'>{label}</dt>
      <dd className='col-span-2 font-medium'>{value}</dd>
    </div>
  )
}
