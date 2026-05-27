# Fattibilità Chat Conversational LLM-Driven in Course Studio

**Data**: 2026-05-27 (sessione #32, post analista review 12).
**Trigger**: utente ha chiesto valutazione fattibilità chat elegante
in Course Studio che permetta "scrivere richieste in linguaggio
naturale per modificare testo / far rifare moduli / sostituire
immagini" — riferimento conversational LLM-driven moderno (tipo
Cursor, v0.dev, ChatGPT canvas).

═══════════════════════════════════════════════════════════════════
## VERDETTO ESECUTIVO
═══════════════════════════════════════════════════════════════════

**Fattibile: SÌ**.
**Stima totale: 7-10 ore lavoro** (4-6h backend + 3-4h frontend).
**Demand: feature WOW per la demo cliente** (non bloccante MVP).
**Scope: post-demo, FASE 8** (out-of-scope sessione #32 corrente).

═══════════════════════════════════════════════════════════════════
## ANALISI STATO CODICE ATTUALE
═══════════════════════════════════════════════════════════════════

### Backend (cosa c'è già)
- ✅ `app/agents/` con LangGraph 2-node pipeline (research + content)
- ✅ Anthropic SDK installato (utilizzato in content_agent)
- ✅ Voyage embeddings client (per RAG)
- ✅ Endpoint `/api/courses/{id}/slides/{idx}` PATCH (editing slide)
- ✅ Endpoint `/api/courses/{id}/slides/{idx}/regenerate` POST
  (rigenera slide singola)
- ✅ Endpoint `/api/courses/{id}/rebuild` POST (rebuild PPTX/PDF)
- ✅ Endpoint `/api/courses/{id}/image/search` GET (Pexels)
- ✅ Endpoint `/api/courses/{id}/slides/{idx}/image` PATCH
- ✅ WebSocket `/ws/jobs/{job_id}` (BP §08.8, pattern auth via
  query token)

### Backend (cosa manca per chat)
- ❌ Endpoint `/api/courses/{id}/chat` con streaming SSE/EventSource
- ❌ Endpoint `/api/courses/{id}/modules/{m_idx}/regenerate` POST
  (per "rigenera intero modulo" — esiste solo per slide singola)
- ❌ Agent dedicato `course_editor_agent` con tool calling

### Frontend (cosa c'è già)
- ✅ Pattern UI residuo `frontend/src/features/chats/` da template
  shadcn-admin (mock-only convo.json, ma struttura DOM riusabile:
  Conversations list + Message bubbles + Input area)
- ✅ Tutti 5 shadcn components chiave installati:
  - Dialog, Sheet, Textarea, ScrollArea, Avatar
- ✅ Course Studio (`frontend/src/features/course-studio/`) con
  layout 3-colonne (sidebar slide list / viewer / editor)

### Frontend (cosa manca per chat)
- ❌ Vercel AI SDK (`ai` + `@ai-sdk/anthropic`) NON installato
- ❌ `react-markdown` per render LLM output NON installato
- ❌ Hook `useChat()` non esiste (è esposto da `@ai-sdk/react`)
- ❌ Component `ChatPanel` / `MessageList` / `ChatInput`
- ❌ Streaming SSE client (`EventSource` o `ReadableStream` consumer)

═══════════════════════════════════════════════════════════════════
## IMPLEMENTAZIONE RICHIESTA — DETTAGLIO TECNICO
═══════════════════════════════════════════════════════════════════

### BACKEND (~4-6h)

**1. Nuovo endpoint streaming** (`app/api/routes/chat.py`):
```python
@router.post("/api/courses/{course_id}/chat")
async def chat_with_course(
    course_id: str,
    request: ChatRequest,
    user: dict = Depends(require_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> StreamingResponse:
    async def event_stream():
        async for chunk in course_editor_agent.astream(
            course_id=course_id,
            user_message=request.message,
            history=request.history,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**2. Agent LangGraph `course_editor_agent`** (`app/agents/course_editor.py`):
```python
# Tools esposti all'LLM Claude:
TOOLS = [
    Tool("read_slide", desc="Leggi una slide", schema=SlideRead),
    Tool("read_module_titles", desc="Lista titoli di un modulo"),
    Tool("edit_slide_text", desc="Modifica un campo testo della slide"),
    Tool("regenerate_slide", desc="Rigenera slide singola con
         istruzioni"),
    Tool("regenerate_module", desc="Rigenera intero modulo"),
    Tool("change_slide_image", desc="Cambia immagine via search Pexels"),
]
# Loop: LLM decide tool → backend esegue → risultato torna a LLM →
# LLM decide se chiudere o chiamare altro tool.
```

Tempo: tool calling Claude funziona out-of-box con Anthropic SDK
(metodo `tools=` di `messages.create`), no librerie extra.

**3. NUOVO endpoint `regenerate_module`** (`app/api/routes/courses.py`):
```python
@router.post("/api/courses/{course_id}/modules/{m_idx}/regenerate")
async def regenerate_module(
    course_id: str, m_idx: int,
    request: ModuleRegenRequest,  # con istruzioni LLM-style
    ...
) -> JobResponse:
    # Spawn task background che riusa:
    #   - retrieve_chunks_per_module() limitato a m_idx
    #   - content_agent.generate_module() per quel modulo
    # Aggiorna slide_contents_json[m_idx] in DB
    # Triggera rebuild PPTX/PDF
    ...
```

Tempo: ~2h (riuso research_agent + content_agent esistenti, ma
serve coordinamento DB update + race condition con altri edit
in corso).

### FRONTEND (~3-4h)

**1. Installa dipendenze**:
```bash
pnpm add ai @ai-sdk/anthropic @ai-sdk/react react-markdown
```

**2. Component `CourseStudioChat`** (`frontend/src/features/course-studio/components/chat-panel.tsx`):
```tsx
import { useChat } from '@ai-sdk/react'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import { Textarea, ScrollArea, Avatar } from '@/components/ui/...'
import ReactMarkdown from 'react-markdown'

export function CourseStudioChat({ courseId }: { courseId: string }) {
  const { messages, input, handleSubmit, isLoading } = useChat({
    api: `/api/courses/${courseId}/chat`,
    headers: { Authorization: `Bearer ${getToken()}` },
  })

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button>✨ Chiedi all'AI</Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[420px]">
        <ScrollArea className="h-[calc(100vh-200px)]">
          {messages.map(m => (
            <MessageBubble key={m.id} role={m.role}>
              <ReactMarkdown>{m.content}</ReactMarkdown>
            </MessageBubble>
          ))}
        </ScrollArea>
        <form onSubmit={handleSubmit}>
          <Textarea value={input} placeholder="Es: 'rigenera M3 più
            specifico su near miss'" />
          <Button type="submit" disabled={isLoading}>Invia</Button>
        </form>
      </SheetContent>
    </Sheet>
  )
}
```

**3. Toast notification per tool executions** (sonner già installato):
```tsx
// In CourseStudio listener su query invalidation:
useEffect(() => {
  if (lastMessage?.toolCalls?.includes('edit_slide_text')) {
    toast.success('Slide aggiornata')
    qc.invalidateQueries({ queryKey: ['course-slides', courseId] })
  }
}, [lastMessage])
```

═══════════════════════════════════════════════════════════════════
## RISCHI E COMPLICAZIONI
═══════════════════════════════════════════════════════════════════

### Rischio MEDIO — Race condition edit/chat in parallelo
Se utente edita una slide via SlideEditor mentre la chat sta
rigenerando lo stesso modulo, il DB ha stato inconsistente. Serve:
- Optimistic locking (course version_number incrementato a ogni
  edit, chat verifica versione prima di scrivere)
- O semplificazione: disabilita SlideEditor durante chat-in-corso

### Rischio MEDIO — Streaming SSE su Vercel
Vercel serverless functions hanno timeout 10s default. La chat
con tool calling può durare 30-60s. Soluzione:
- Backend streaming è su Railway (timeout 600s impostabile), no
  problema
- Frontend SSE consumer è in `useChat()`, gira nel browser, no
  serverless involved per il consumer

### Rischio BASSO — Costo token LLM
Ogni chat consuma 2K-10K token Claude per turno (input chat
history + tool definitions + tool results). Con uso intenso
cliente: ~$1-3/sessione 30 min. Sostenibile per demo cliente,
da monitorare per produzione.

### Rischio BASSO — Validation Pydantic dopo edit chat
Quando l'LLM chiama `edit_slide_text(slide_idx, "body", new_value)`,
il backend deve validare il `new_value` contro `SlideConstraints`
(es. CONTENT_TEXT min 4 bullets). Se validation fallisce, l'LLM
deve riprovare con guidance. Pattern già noto: instructor retry
loop usato in content_agent.

═══════════════════════════════════════════════════════════════════
## RACCOMANDAZIONE SCOPE / TIMING
═══════════════════════════════════════════════════════════════════

**Per la demo cliente stanotte (#32)**: **NON implementiamo**.
- Stiamo già stretti su tempi (BLOCCO A-F ~5-6h fila)
- Chat conversational è nuova superficie codice non collaudata
- Cliente vede già: 3 demo PPTX puliti + Course Studio con
  ImagePicker funzionante + Wizard nuovo corso live + audio
  download = abbondante WOW factor per la demo

**Post-demo (FASE 8)**: implementiamo come prima feature
di upgrade qualità. Sequenza:
1. **Settimana 1**: backend chat endpoint + course_editor_agent
   + regenerate_module endpoint (4-6h work + 1 giorno test E2E)
2. **Settimana 2**: frontend ChatPanel + integrazione Sheet
   right-side di Course Studio + Vercel AI SDK install
   (3-4h work + 1 giorno polish UI con skills design-system)
3. **Settimana 2-3**: E2E test edge cases (race condition,
   token budget, validation failures), demo internal al cliente,
   ship a produzione

**Stima realistic: 2 settimane calendar** (incluso slack per
edge cases) per chat completa, deployata, validata.

═══════════════════════════════════════════════════════════════════
## REFERENZE / RIFERIMENTI ONLINE (per design)
═══════════════════════════════════════════════════════════════════

Pattern UI raccomandati da seguire (da skills design-system +
ricerca online):
- **Vercel v0.dev**: Sheet right-side con MessageList + Textarea
  bottom-anchored
- **Cursor IDE**: tool calling con preview diff prima di applicare
  modifiche
- **ChatGPT Canvas**: split view editor + chat panel laterale
- **Anthropic Claude UI**: streaming token-per-token + animated
  cursor

**Pattern shadcn riusabili**:
- `Sheet` (slide-out right-side già installato)
- `ScrollArea` (auto-scroll a bottom su nuovo messaggio)
- `Avatar` (user vs assistant message bubbles)
- `Textarea` (auto-resize con `resize-y`)

═══════════════════════════════════════════════════════════════════
## CONCLUSIONE
═══════════════════════════════════════════════════════════════════

**Fattibilità tecnica**: SÌ, ben fattibile, no blocker tecnici.
Pattern conosciuti, librerie disponibili (Vercel AI SDK production-grade),
backend già ha tutti i pezzi (LangGraph + Anthropic + tool calling).

**Effort**: 7-10 ore implementazione + 1-2 settimane calendar
per validazione production.

**Scope**: **POST-DEMO**. Aggiunto a `VERIFICATION_DEBT.md` come
**#R-chat-conversational** (FASE 8, priority HIGH come prima
feature upgrade UX post-firma contratto cliente).
