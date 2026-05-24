/**
 * Step 2 — Destinatario.
 *
 * Radio choice between `discente` and `formatore` (BP §04 `TargetType`).
 * Rendered as full-width cards (Stripe-style) so the affordance reads
 * as "this is a major decision" rather than a hidden radio button.
 */

import { Users, GraduationCap } from 'lucide-react'
import { useFormContext } from 'react-hook-form'

import { cn } from '@/lib/utils'
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import type { WizardValues } from '../schema'

const OPTIONS = [
  {
    value: 'discente',
    label: 'Discente',
    description: 'Lavoratore che riceve la formazione obbligatoria.',
    icon: Users,
  },
  {
    value: 'formatore',
    label: 'Formatore',
    description: 'Docente o RSPP che eroga la formazione.',
    icon: GraduationCap,
  },
] as const

export function Step2Target() {
  const form = useFormContext<WizardValues>()
  return (
    <FormField
      control={form.control}
      name='target'
      render={({ field }) => (
        <FormItem>
          <FormLabel>A chi è destinato il corso?</FormLabel>
          <FormControl>
            <RadioGroup
              value={field.value}
              onValueChange={field.onChange}
              className='grid gap-3 sm:grid-cols-2'
            >
              {OPTIONS.map((opt) => {
                const Icon = opt.icon
                const active = field.value === opt.value
                return (
                  <Label
                    key={opt.value}
                    htmlFor={`target-${opt.value}`}
                    className={cn(
                      'flex cursor-pointer items-start gap-3 rounded-md border p-4 transition-colors',
                      'hover:bg-muted/40',
                      active &&
                        'border-brand-primary bg-brand-primary/5 ring-1 ring-brand-primary/20',
                    )}
                  >
                    <RadioGroupItem
                      value={opt.value}
                      id={`target-${opt.value}`}
                      className='mt-0.5'
                    />
                    <div className='flex-1'>
                      <div className='flex items-center gap-2'>
                        <Icon className='size-4 text-muted-foreground' aria-hidden='true' />
                        <span className='font-medium'>{opt.label}</span>
                      </div>
                      <p className='mt-1 text-sm text-muted-foreground'>
                        {opt.description}
                      </p>
                    </div>
                  </Label>
                )
              })}
            </RadioGroup>
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}
