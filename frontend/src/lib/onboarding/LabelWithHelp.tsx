/**
 * F10 LabelWithHelp — Label shadcn + icona ? Tooltip per spiegare termini
 * tecnici (es. "Note relatore", "Riferimento normativo", "voce skeleton").
 *
 * Pattern Stripe Dashboard: il ? non e` invadente, e` un'icona muted accanto
 * al label. Hover mostra un tooltip 2-3 righe. Sempre disponibile, non solo
 * onboarding.
 */

import { HelpCircle } from 'lucide-react'

import { Label } from '@/components/ui/label'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

export interface LabelWithHelpProps {
  htmlFor?: string
  children: React.ReactNode
  /** Testo che appare nel tooltip on hover. */
  help: React.ReactNode
  /** className extra sul wrapper. */
  className?: string
}

export function LabelWithHelp({
  htmlFor,
  children,
  help,
  className,
}: LabelWithHelpProps) {
  return (
    <div className={`inline-flex items-center gap-1.5 ${className ?? ''}`}>
      <Label htmlFor={htmlFor}>{children}</Label>
      <TooltipProvider delayDuration={150}>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type='button'
              aria-label='Spiegazione'
              className='text-muted-foreground hover:text-foreground inline-flex h-4 w-4 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-primary)]'
            >
              <HelpCircle className='h-3.5 w-3.5' />
            </button>
          </TooltipTrigger>
          <TooltipContent
            side='top'
            align='start'
            className='max-w-xs text-xs leading-relaxed'
          >
            {help}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  )
}
