/**
 * ChatPanel — F6 Course Studio (vast-hopping post-MVP 2026-05-31).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: chat NL ancorata alla slide corrente. Memoria conversation
 *   cross-session (1 conv per corso), streaming token-by-token (typing
 *   effect), preview diff + Applica idempotente.
 * Tone: bubbles user (brand-primary/10 right-aligned) vs assistant
 *   (muted left-aligned). Anchor chip "Slide #N" su ogni messaggio. Input
 *   sticky bottom con Enter-to-send.
 * Constraints: REI-1 shadcn only (Button, Textarea, Badge, ScrollArea).
 *   D7 vincolo: chat SEMPRE ancorata a una slide (slideIndex prop required).
 *
 * Streaming: fetch + ReadableStream + parser SSE manuale (NO EventSource
 * perche' non supporta header Authorization Bearer). Token JWT preso da
 * tokenStorage.getAccess().
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  Loader2,
  Send,
  Sparkles,
  User,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  api,
  ApiError,
  tokenStorage,
  type ChatMessage,
  type ProposedPatchDTO,
} from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface Props {
  courseId: string
  slideIndex: number
}

interface PartialMessage {
  assistant_message: string
  proposed_patch: ProposedPatchDTO | null
}

export function ChatPanel({ courseId, slideIndex }: Props) {
  const queryClient = useQueryClient()
  const [input, setInput] = useState('')
  const [streamingPartial, setStreamingPartial] = useState<PartialMessage | null>(null)
  const [streaming, setStreaming] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const historyQ = useQuery({
    queryKey: ['chat-history', courseId] as const,
    queryFn: () => api.getChatHistory(courseId),
    staleTime: 30_000,
  })

  // Memoria cross-session: messages flow dal server, ordinati cronologici
  const messages: ChatMessage[] = useMemo(
    () => historyQ.data?.messages ?? [],
    [historyQ.data],
  )

  // Auto-scroll su nuovo messaggio o streaming partial
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, streamingPartial])

  const applyMut = useMutation({
    mutationFn: (messageId: string) => api.applyChatMessage(courseId, messageId),
    onSuccess: async () => {
      toast.success('Modifica applicata alla slide')
      await queryClient.invalidateQueries({ queryKey: ['chat-history', courseId] })
      await queryClient.invalidateQueries({ queryKey: ['course-slides', courseId] })
      await queryClient.invalidateQueries({ queryKey: ['quality-issues', courseId] })
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? e.message : 'Applicazione fallita',
      ),
  })

  async function sendMessage() {
    const text = input.trim()
    if (text.length < 2 || streaming) return
    setStreaming(true)
    setStreamingPartial({ assistant_message: '', proposed_patch: null })
    setInput('')

    try {
      const url = api.chatStreamUrl(courseId)
      const token = tokenStorage.getAccess()
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: text, slide_index: slideIndex }),
      })
      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`)
      }
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let done = false

      while (!done) {
        const { value, done: streamDone } = await reader.read()
        done = streamDone
        if (value) {
          buffer += decoder.decode(value, { stream: true })
          // Parse SSE: eventi separati da blocchi vuoti \n\n
          const events = buffer.split('\n\n')
          buffer = events.pop() ?? '' // ultimo incompleto → riprende dopo
          for (const block of events) {
            if (!block.trim()) continue
            const lines = block.split('\n')
            const evt: Record<string, string> = {}
            for (const line of lines) {
              if (line.startsWith('event:')) evt.event = line.slice(6).trim()
              else if (line.startsWith('data:')) evt.data = line.slice(5).trim()
            }
            if (!evt.event || !evt.data) continue

            if (evt.event === 'partial') {
              try {
                const partial = JSON.parse(evt.data) as PartialMessage
                setStreamingPartial(partial)
              } catch {
                // ignore parse errors on partial chunks
              }
            } else if (evt.event === 'done') {
              setStreamingPartial(null)
              await queryClient.invalidateQueries({
                queryKey: ['chat-history', courseId],
              })
            } else if (evt.event === 'error') {
              try {
                const err = JSON.parse(evt.data) as { detail?: string }
                toast.error(err.detail ?? 'Errore stream chat')
              } catch {
                toast.error('Errore stream chat')
              }
            }
          }
        }
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Streaming chat fallito')
    } finally {
      setStreaming(false)
      setStreamingPartial(null)
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const placeholder = `Chiedi all'AI: "rendi piu' operativo il bullet 3", "espandi le note a 60s", "riformula il titolo"…`

  return (
    <div className="flex h-full flex-col">
      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto pr-2"
        aria-live="polite"
        aria-label="Cronologia chat"
      >
        {historyQ.isLoading && (
          <>
            <Skeleton className="h-16 w-3/4" />
            <Skeleton className="h-12 w-2/3 ms-auto" />
          </>
        )}

        {!historyQ.isLoading && messages.length === 0 && !streamingPartial && (
          <div className="border-border bg-muted/30 rounded-md border border-dashed p-4 text-center">
            <Sparkles className="text-brand-primary mx-auto mb-2 size-5" />
            <p className="text-muted-foreground text-xs">
              Chat ancorata alla slide corrente. La memoria si conserva tra le sessioni.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            currentSlideIndex={slideIndex}
            onApply={() => applyMut.mutate(m.id)}
            applying={applyMut.isPending && applyMut.variables === m.id}
          />
        ))}

        {/* Streaming partial: typing effect */}
        {streamingPartial !== null && (
          <div className="bg-muted mr-8 space-y-1.5 rounded-2xl rounded-tl-sm p-3 text-sm">
            <div className="flex items-center gap-1.5 text-xs">
              <Sparkles className="text-brand-primary size-3" />
              <span className="text-muted-foreground">AI sta scrivendo…</span>
            </div>
            <p className="whitespace-pre-wrap">
              {streamingPartial.assistant_message}
              <span className="bg-brand-primary ms-0.5 inline-block h-3 w-1 animate-pulse" />
            </p>
          </div>
        )}
      </div>

      <div className="border-border mt-3 border-t pt-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          rows={2}
          disabled={streaming}
          className="text-xs"
          aria-label="Messaggio chat"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-muted-foreground text-[10px]">
            ⌘ Enter per inviare
          </span>
          <Button
            size="sm"
            onClick={sendMessage}
            disabled={input.trim().length < 2 || streaming}
            className="h-7 text-xs"
          >
            {streaming ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Send className="size-3" />
            )}
            <span className="ms-1">{streaming ? 'In corso…' : 'Invia'}</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── MessageBubble ──────────────────────────────────────────────────────────

interface BubbleProps {
  message: ChatMessage
  currentSlideIndex: number
  onApply: () => void
  applying: boolean
}

function MessageBubble({ message, currentSlideIndex, onApply, applying }: BubbleProps) {
  const isUser = message.role === 'user'
  const proposedPatch = message.tool_calls?.proposed_patch
  const hasPatch =
    proposedPatch &&
    (proposedPatch.title || proposedPatch.body || proposedPatch.speaker_notes)
  const isApplied = message.applied_at !== null

  return (
    <div className={cn('space-y-1', isUser ? 'ms-8' : 'me-8')}>
      <div
        className={cn(
          'space-y-1.5 rounded-2xl p-3 text-sm',
          isUser
            ? 'bg-brand-primary/10 rounded-tr-sm'
            : 'bg-muted rounded-tl-sm',
        )}
      >
        <div className="flex items-center gap-1.5 text-xs">
          {isUser ? (
            <>
              <User className="text-brand-primary size-3" />
              <span className="text-muted-foreground">Tu</span>
            </>
          ) : (
            <>
              <Sparkles className="text-brand-primary size-3" />
              <span className="text-muted-foreground">AI</span>
            </>
          )}
          {message.slide_index !== null && message.slide_index !== currentSlideIndex && (
            <Badge variant="outline" className="ms-1 text-[10px]">
              Slide {message.slide_index + 1}
            </Badge>
          )}
        </div>
        <p className="whitespace-pre-wrap">{message.content}</p>

        {/* Patch preview + Applica/Applicato */}
        {hasPatch && !isUser && (
          <div className="border-border space-y-1.5 rounded-md border bg-background/60 p-2 text-xs">
            <div className="text-muted-foreground text-[10px] font-medium uppercase">
              Modifica proposta
            </div>
            {proposedPatch.title !== null && proposedPatch.title !== undefined && (
              <div>
                <span className="text-muted-foreground text-[10px]">Titolo: </span>
                <span className="font-medium">{proposedPatch.title}</span>
              </div>
            )}
            {proposedPatch.body && (
              <div>
                <span className="text-muted-foreground text-[10px]">Bullets:</span>
                <ul className="ms-3 list-disc text-xs">
                  {proposedPatch.body.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            )}
            {proposedPatch.speaker_notes !== null && proposedPatch.speaker_notes !== undefined && (
              <div>
                <span className="text-muted-foreground text-[10px]">Note: </span>
                <span className="line-clamp-3">{proposedPatch.speaker_notes}</span>
              </div>
            )}
            <div className="flex justify-end">
              {isApplied ? (
                <Badge
                  variant="outline"
                  className="border-brand-secondary/40 bg-brand-secondary/10 text-brand-secondary text-[10px]"
                >
                  <Check className="me-1 size-3" />
                  Applicato
                </Badge>
              ) : (
                <Button
                  size="sm"
                  onClick={onApply}
                  disabled={applying}
                  className="h-6 px-2 text-[10px]"
                >
                  {applying ? (
                    <Loader2 className="size-3 animate-spin" />
                  ) : (
                    <Check className="size-3" />
                  )}
                  <span className="ms-1">Applica</span>
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
