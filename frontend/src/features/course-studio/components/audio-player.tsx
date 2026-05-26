/**
 * AudioPlayer — riproduce il singolo MP3 della slide (FASE 10).
 *
 * La voce DiegoNeural (edge-tts) di ogni slide è servita da
 * GET /api/courses/{id}/audio/{idx}. NB: il tag <audio> nativo non invia
 * l'header Authorization, quindi qui aggiungiamo ?token= come per il WS
 * (BP §08.8). Mostra un badge se l'audio è off-target (durata fuori 25-35s).
 */

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

  return (
    <div className="border-border bg-muted/50 flex items-center gap-3 rounded-md border px-3 py-2">
      <span className="text-muted-foreground text-xs font-medium">🔊 Voce</span>
      {/* key forza il reload quando cambia slide */}
      <audio key={src} controls src={src} className="h-8 flex-1">
        Il tuo browser non supporta l'audio HTML5.
      </audio>
    </div>
  )
}
