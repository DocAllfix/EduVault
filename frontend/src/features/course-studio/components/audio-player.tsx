/**
 * AudioPlayer — riproduce il singolo MP3 della slide (FASE 10).
 *
 * La voce (edge-tts) di ogni slide è servita da
 * GET /api/courses/{id}/audio/{idx}. NB: il tag <audio> nativo non invia
 * l'header Authorization, quindi qui aggiungiamo ?token= come per il WS
 * (BP §08.8).
 *
 * Toggle narrazione (FASE 6 restyling): l'operatore può attivare/disattivare
 * la riproduzione vocale globalmente. La preferenza è persistita
 * (useAudioNarration store → localStorage) e vale per tutte le slide.
 *
 * Stato "audio non ancora pronto" (FIX #32): l'audio bg può richiedere alcuni
 * minuti. Se il <audio> emette onError (404 / file mancante), mostriamo un
 * placeholder informativo invece di un controllo audio rotto.
 */

import { useEffect, useState } from 'react'
import { Volume2, VolumeX } from 'lucide-react'

import { api, tokenStorage } from '@/lib/api'
import { useAudioNarration } from '@/stores/audio-narration-store'
import { Switch } from '@/components/ui/switch'

export function AudioPlayer({
  courseId,
  slideIndex,
}: {
  courseId: string
  slideIndex: number
}) {
  const { enabled, toggle } = useAudioNarration()

  // Il backend FASE 7 protegge l'endpoint con Bearer; per <audio> nativo
  // passiamo il token in query string (stesso pattern del WebSocket BP §08.8).
  const token = tokenStorage.getAccess()
  const baseUrl = api.slideAudioUrl(courseId, slideIndex)
  const src = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl

  // FIX #32: reset stato error quando cambia slide (src change).
  const [hasError, setHasError] = useState(false)
  useEffect(() => {
    setHasError(false)
  }, [src])

  return (
    <div className='border-border bg-muted/50 flex items-center gap-3 rounded-md border px-3 py-2'>
      <button
        type='button'
        onClick={toggle}
        className='text-muted-foreground hover:text-foreground flex shrink-0 items-center gap-1.5 text-xs font-medium transition-colors'
        aria-pressed={enabled}
        aria-label={
          enabled ? 'Disattiva narrazione vocale' : 'Attiva narrazione vocale'
        }
      >
        {enabled ? (
          <Volume2 className='size-4' aria-hidden='true' />
        ) : (
          <VolumeX className='size-4' aria-hidden='true' />
        )}
        <span>Narrazione</span>
      </button>

      <Switch
        checked={enabled}
        onCheckedChange={toggle}
        aria-label='Attiva o disattiva la narrazione vocale'
      />

      {!enabled ? (
        <span className='text-muted-foreground text-xs italic'>
          Narrazione disattivata
        </span>
      ) : hasError ? (
        <span
          className='text-muted-foreground line-clamp-2 flex-1 text-xs leading-snug italic'
          title='La generazione audio avviene in background e può richiedere alcuni minuti dopo la creazione del corso'
        >
          Audio in elaborazione… (può richiedere alcuni minuti)
        </span>
      ) : (
        <audio
          controls
          src={src}
          className='h-8 min-w-0 flex-1'
          onError={() => setHasError(true)}
        >
          Il tuo browser non supporta l'audio HTML5.
        </audio>
      )}
    </div>
  )
}
