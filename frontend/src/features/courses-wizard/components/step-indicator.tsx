/**
 * Wizard step indicator — Stripe-Checkout-inspired horizontal bar.
 *
 * Six numbered dots connected by a track. The track fills with brand
 * pink up to the current step, current dot is the brand colour, past
 * dots show a check mark, future dots are muted.
 *
 * Built ad-hoc (no shadcn `Progress` primitive — it's not in the
 * template, REI-5: don't pull a dep for 6 dots). Pure Tailwind, ~50
 * LOC, no animation needed beyond the transition on width changes.
 */

import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

type StepIndicatorProps = {
  current: number // 1-based
  total: number
  /** Labels rendered under each dot. Length must equal `total`. */
  labels: readonly string[]
}

export function StepIndicator({ current, total, labels }: StepIndicatorProps) {
  if (labels.length !== total) {
    // Surface mis-wiring loudly in dev (impossible in prod typings).
    // eslint-disable-next-line no-console
    console.warn('StepIndicator: labels.length !== total')
  }
  const pct = ((current - 1) / Math.max(total - 1, 1)) * 100

  return (
    <div className='w-full' role='progressbar' aria-valuenow={current} aria-valuemin={1} aria-valuemax={total}>
      <div className='relative px-2'>
        {/* Track (muted) */}
        <div className='absolute inset-x-2 top-3.5 h-0.5 -translate-y-1/2 bg-border' aria-hidden='true' />
        {/* Filled track (brand) */}
        <div
          className='absolute left-2 top-3.5 h-0.5 -translate-y-1/2 bg-brand-primary transition-[width] duration-300 ease-out'
          style={{ width: `calc(${pct}% - ${pct === 0 ? 0 : 16}px + 16px)` }}
          aria-hidden='true'
        />
        {/* Dots */}
        <ol className='relative flex justify-between'>
          {labels.map((label, i) => {
            const step = i + 1
            const done = step < current
            const active = step === current
            return (
              <li key={label} className='flex flex-col items-center gap-2 text-center'>
                <span
                  className={cn(
                    'grid size-7 place-items-center rounded-full text-xs font-medium transition-colors',
                    done && 'bg-brand-primary text-brand-primary-foreground',
                    active && 'bg-brand-primary text-brand-primary-foreground ring-4 ring-brand-primary/15',
                    !done && !active && 'bg-background text-muted-foreground ring-1 ring-border',
                  )}
                  aria-current={active ? 'step' : undefined}
                >
                  {done ? <Check className='size-3.5' aria-hidden='true' /> : step}
                </span>
                <span
                  className={cn(
                    'hidden text-xs sm:block',
                    active && 'font-medium text-foreground',
                    !active && 'text-muted-foreground',
                  )}
                >
                  {label}
                </span>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
