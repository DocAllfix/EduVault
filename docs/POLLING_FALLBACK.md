# Polling fallback — WebSocket progress

> **Referenza:** BLUEPRINT v7.0 §10.3.
> **Scopo:** documentare il contratto frontend↔backend per quando il
> WebSocket `/ws/jobs/{job_id}?token=...` non è disponibile (rete instabile,
> proxy che chiude long-lived connections, blocco firewall WS).

## Strategia frontend

Il client (FASE 6) usa due canali in cascata:

1. **WebSocket primario** — `wss://<host>/ws/jobs/{job_id}?token=<access>`
   - Aperto subito dopo POST `/api/courses` con il `job_id` ricevuto.
   - Stream JSON ogni 1s con `{status, progress_percent, current_step, error_message}`.
   - Si chiude da solo quando `status ∈ {completed, failed, cancelled}` (vedi `TERMINAL_STATES` in [app/api/websocket.py](../app/api/websocket.py)).
   - Close codes: 4001 token, 4003 ownership, 4004 job not found.

2. **Polling REST fallback** — `GET /api/courses/{course_id}` ogni **30 secondi**.
   - Attivato dal frontend quando: (a) `onerror` sul WS, (b) `onclose` con code diverso da 1000/1001/4xxx pulito, (c) reconnect fallisce 2 volte di seguito.
   - Stessa risposta tipizzata di `CourseDetail` (status incluso).
   - Termina quando `status ∈ {completed, failed, cancelled, archived}`.

## Perché 30 secondi

- WS: granularità reale 1s (vedi `POLL_INTERVAL_SECONDS` in `websocket.py`).
- Polling REST: 30s è il bilanciamento BP §10.3 — abbastanza frequente per UX accettabile, abbastanza rado da non saturare il rate limit globale dell'API (FastAPI/slowapi rate limiter applicato per IP).
- Una pipeline 1h-corso (120 slide) dura ~5-15 min: con polling 30s l'utente vede ≤30 update — più che sufficiente per una progress bar.

## Implementazione attesa lato frontend (FASE 6.9)

```typescript
// pseudo-code — il vero codice React arriverà in 6.9
function watchJob(jobId: string, courseId: string, token: string) {
  const ws = new WebSocket(`wss://.../ws/jobs/${jobId}?token=${token}`)
  ws.onmessage = (e) => updateProgress(JSON.parse(e.data))
  ws.onclose = (e) => {
    if (e.code !== 1000 && !TERMINAL_STATES.has(lastStatus)) {
      startPollingFallback(courseId, token)  // ← GET ogni 30s
    }
  }
}
```

## Endpoint usati

| Canale | Path | Frequenza | Auth |
|---|---|---|---|
| WebSocket primario | `WS /ws/jobs/{job_id}?token=...` | 1s server-driven | JWT in query string |
| Polling fallback | `GET /api/courses/{course_id}` | 30s client-driven | `Authorization: Bearer ...` |

## Stati terminali (loop exit)

Sia WS sia polling devono fermarsi quando `status` ∈
`{completed, failed, cancelled}` (vedi `TERMINAL_STATES`
in [app/api/websocket.py](../app/api/websocket.py); `archived` è
incluso lato polling perché un corso può essere soft-deleted dall'UI
mentre il polling è attivo).

## Rate limit considerations

POST `/api/courses` è limitato a 5/min/IP (BP §10.4) — il polling GET
`/api/courses/{id}` NON ha rate limit dedicato attualmente; affidato al
limit globale del reverse proxy in FASE 7 (deploy).
