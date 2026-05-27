/**
 * AudioPlayer — riproduce il singolo MP3 della slide (FASE 10).
 *
 * La voce DiegoNeural (edge-tts) di ogni slide è servita da
 * GET /api/courses/{id}/audio/{idx}. NB: il tag <audio> nativo non invia
 * l'header Authorization, quindi qui aggiungiamo ?token= come per il WS
 * (BP §08.8).
 *
 * FIX #32 (analista review 12): gestione graziosa stato "audio non ancora
 * pronto" (audio bg può richiedere fino a 12 min su corsi 8h). Se il
 * <audio> emette onError (404 / file mancante), mostriamo un placeholder
 * informativo invece di un controllo audio rotto.
 */

import { useEffect, useState } from 'react'

import { api, tokenStorage } from '@/lib/api'

export function AudioPlayer({
  courseId,
  slideIndex,
}: {
  courseId: string
  slideIndex: number
}) {
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
    <div className="border-border bg-muted/50 flex items-center gap-3 rounded-md border px-3 py-2">
      <span className="text-muted-foreground text-xs font-medium">🔊 Voce</span>
      {hasError ? (
        <span className="text-muted-foreground text-xs italic">
          Audio in elaborazione… (la generazione audio avviene in background
          e può richiedere alcuni minuti dopo la creazione del corso)
        </span>
      ) : (
        <audio
          controls
          src={src}
          className="h-8 flex-1"
          onError={() => setHasError(true)}
        >
          Il tuo browser non supporta l'audio HTML5.
        </audio>
      )}
    </div>
  )
}
