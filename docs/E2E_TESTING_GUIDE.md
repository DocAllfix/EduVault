# E2E Testing Guide — Nexus EduVault

Guida operativa per test end-to-end della webapp in produzione + workaround
per evitare blocchi infrastruttura (Vercel Bot Protection).

## Workaround Vercel Bot Protection

**Sintomo**: dopo ~30+ chiamate JavaScript automatizzate (script evaluate,
fetch in serie, etc.) Vercel mostra "Impossibile verificare il tuo browser
— Codice 21" su tutte le pagine, blocco ~5-10 min.

**Causa**: Vercel Security Checkpoint protegge da scraping/bot via challenge
JS lato edge.

**Workaround**:

1. **Pacing**: non eseguire più di 1-2 `browser_evaluate` complessi per
   minuto. Tra una sequenza di test e l'altra inserire `wait_for(time=30)`.
2. **Backend-first**: testare il backend via `curl` (login + token + API
   diretti). Solo dopo confermare UI in browser.
3. **Cache busting**: aggiungere `?v=<timestamp>` agli URL per forzare
   reload senza triggerare detection bot.
4. **Sessione browser persistente**: NON aprire `new_page` ripetutamente
   — usare `navigate_page` per riusare il context con cookies challenge.
5. **In caso di blocco attivo**: aspettare 5-10 min, poi un singolo
   `navigate_page` ad una route pubblica (`/login`) prima di tornare al
   workflow autenticato.

## Sequenza E2E completa (~30 min)

1. Login admin@cfp-montessori.it via UI
2. Dashboard widgets + tabella corsi
3. /regulations sheet F9
4. /admin/catalog F1
5. /courses/{completed_id} detail + download
6. /courses/{completed_id}/studio:
   - F4 quality panel (slide 2 con issue)
   - F4b "Rigenera con AI" dialog
   - F5 image picker Library tab (su slide CONTENT_IMAGE)
   - F6 Tabs Quality/Chat + send + history
   - F7 audio player (badge appare solo se provider=azure)
7. /courses/new wizard 6-step (crea corso skeleton_pending)
8. F3.AI 4 azioni (su corso skeleton_pending)
9. Cleanup: archive corso test

## Backend-only smoke (~5 min, no rate limit Vercel)

```bash
TOKEN=$(curl -s -X POST $API/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@cfp-montessori.it","password":"$PW"}' \
  | python -c "import sys,json; print(json.loads(sys.stdin.read())['access_token'])")

# Dashboard stats
curl -s $API/api/dashboard/stats -H "Authorization: Bearer $TOKEN"

# F1 catalog
curl -s $API/api/admin/catalog/summary -H "Authorization: Bearer $TOKEN"

# F9 compatible
curl -s $API/api/regulations/dlgs_81_08/compatible-courses -H "Authorization: Bearer $TOKEN"

# F5 library
curl -s "$API/api/admin/images/library?per_page=10" -H "Authorization: Bearer $TOKEN"

# F6 chat
curl -s "$API/api/courses/$CID/chat/history" -H "Authorization: Bearer $TOKEN"
```

## Migration auto-runner (post 2026-05-31)

Il backend ora applica automaticamente le migrations pending in
`app/db/migrations/*.sql` al startup (vedi `app/services/migration_runner.py`).

**Convention**:
- File `001_*.sql` ... `999_*.sql` = migration regolari, applicate auto
- File `setup_*.sql` o `_*.sql` = script one-shot, NON applicati auto (vanno
  eseguiti manualmente via TCP proxy)

**Tabella tracking**: `_schema_migrations(filename PRIMARY KEY, applied_at,
checksum)`. Per re-applicare una migration: `DELETE FROM _schema_migrations
WHERE filename = '012_audio_provider.sql'` + restart deploy.
