/**
 * Step 5 — Output formati.
 *
 * Checkbox group. At least one must be selected (Pydantic refuses
 * empty `outputs` in `CourseRequest.validate_outputs`). We enforce the
 * same constraint client-side with Zod (`min(1)`).
 *
 * The four formats correspond to backend `_ALLOWED_OUTPUTS`:
 *   pptx, pdf, audio, quiz. `quiz` is delivered as JSON sidecar (BP)
 *   and intentionally listed for parity, even though the v1.0 wizard
 *   defaults to ["pptx","pdf"].
 */

import { useFormContext } from 'react-hook-form'

import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { OUTPUT_OPTIONS, type OutputValue, type WizardValues } from '../schema'

export function Step5Output() {
  const form = useFormContext<WizardValues>()

  return (
    <FormField
      control={form.control}
      name='outputs'
      render={({ field }) => {
        const value = field.value ?? []
        const toggle = (val: OutputValue, checked: boolean) => {
          if (checked) {
            if (!value.includes(val)) field.onChange([...value, val])
          } else {
            field.onChange(value.filter((v) => v !== val))
          }
        }
        return (
          <FormItem>
            <FormLabel>Cosa generare</FormLabel>
            <FormControl>
              <div className='grid gap-3 sm:grid-cols-2'>
                {OUTPUT_OPTIONS.map((opt) => {
                  const checked = value.includes(opt.value)
                  return (
                    <Label
                      key={opt.value}
                      htmlFor={`output-${opt.value}`}
                      className={cn(
                        'flex cursor-pointer items-start gap-3 rounded-md border p-4 transition-colors',
                        'hover:bg-muted/40',
                        checked &&
                          'border-brand-primary bg-brand-primary/5 ring-1 ring-brand-primary/20',
                      )}
                    >
                      <Checkbox
                        id={`output-${opt.value}`}
                        checked={checked}
                        onCheckedChange={(c) => toggle(opt.value, c === true)}
                        className='mt-0.5'
                      />
                      <div className='flex-1'>
                        <div className='flex items-center gap-2'>
                          <span className='font-medium uppercase'>{opt.label}</span>
                        </div>
                        <p className='mt-1 text-sm text-muted-foreground'>
                          {opt.desc}
                        </p>
                      </div>
                    </Label>
                  )
                })}
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )
      }}
    />
  )
}
