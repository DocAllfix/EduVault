/**
 * F10 HelpButton — icona "?" in topbar globale per riaprire il tour della
 * pagina corrente.
 *
 * Render condizionale: se la pagina corrente non ha un tour registrato
 * (es. /login, /settings, /chats), il bottone non appare → niente UI noise.
 *
 * Click → reset localStorage + lancia driver.js tour.
 *
 * Pattern visivo coerente con ThemeSwitch / ConfigDrawer (size icon, ghost
 * variant).
 */

import { useEffect, useState } from 'react'
import { HelpCircle } from 'lucide-react'
import { useRouter } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

import { findTourForPath, restartTourForPath } from './tour-registry'

export function HelpButton() {
  const router = useRouter()
  const [available, setAvailable] = useState(false)
  const [label, setLabel] = useState<string>('')

  useEffect(() => {
    // Subscribe a router state changes so the help button hides/appears
    // when navigating to pages without a registered tour.
    const updateForPath = () => {
      const pathname = router.state.location.pathname
      const entry = findTourForPath(pathname)
      setAvailable(!!entry)
      setLabel(entry?.label ?? '')
    }
    updateForPath()
    const unsub = router.subscribe('onLoad', updateForPath)
    return unsub
  }, [router])

  if (!available) return null

  const onClick = () => {
    const pathname = router.state.location.pathname
    restartTourForPath(pathname)
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant='ghost'
            size='icon'
            onClick={onClick}
            aria-label={`Rivedi il tour: ${label}`}
            className='text-muted-foreground hover:text-foreground'
          >
            <HelpCircle className='size-4' />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <span className='text-xs'>Rivedi il tour della pagina</span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
