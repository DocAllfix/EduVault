Messaggio separato — domanda strutturata sul deploy Vercel + Railway + GitHub + DevTools + code cleanup. L'utente vuole testare in produzione il prima possibile, e mi ha chiesto di mappare TUTTO quello che serve PRIMA di chiederti OK al deploy. Ho fatto un'analisi read-only dello stato app per portarti dati veri, non ipotesi.

═══════════════════════════════════════════════════════════════════
STATO ATTUALE APP (dati verificati ora)
═══════════════════════════════════════════════════════════════════

BACKEND (Python FastAPI + LangGraph)
- Stack: Python 3.12, FastAPI, asyncpg, PostgreSQL 16 + pgvector
- Storage: container Docker locale, NO cloud auth (REI-4)
- Audio: edge-tts (no API key)
- Concorrenza: asyncio.Semaphore(1) BLINDATO (REI-3, python-pptx
  + lxml thread-unsafe — NON SI PUÒ ALZARE senza convertire a
  process pool o Celery)
- Dockerfile: presente (build: . in docker-compose.yml)
- Volumes: output_data (PPTX/PDF generati) + pg_data (DB)
- Healthcheck postgres: configurato (pg_isready)

FRONTEND (React + Vite + shadcn-admin v2.2.1)
- Stack: Vite + tsc, pnpm workspace, type=module
- Build: pnpm install && pnpm build → genera dist/
- preview: vite preview (SPA pura, NO SSR)
- netlify.toml presente con SPA fallback rewrite (/* → /index.html)
- vercel.json NON presente (da creare)
- Test: vitest browser headless + playwright chromium
- Lint: eslint, format: prettier, dead-code: knip

DOCKER-COMPOSE (locale)
- backend: build . con env_file .env, port 8000:8000
- postgres: pgvector/pgvector:pg16, NO port mapping esterno
  (solo rete interna Docker), env POSTGRES_ADMIN_PASSWORD
- frontend: profile "full" (opt-in), build ./frontend, port 3000
- nginx: profile "full" (opt-in), reverse proxy 80+443

ENV VARS (.env.example)
- Secrets vuoti che il deploy DEVE compilare: JWT_SECRET,
  POSTGRES_ADMIN_PASSWORD, POSTGRES_APP_PASSWORD,
  ANTHROPIC_API_KEY, VOYAGE_API_KEY, BRAVE_SEARCH_API_KEY,
  ADMIN_BOOTSTRAP_PASSWORD
- Placeholder dominio (REI-13: DA DECIDERE al deploy):
  APP_DOMAIN=<DOMAIN_TBD>, ADMIN_BOOTSTRAP_EMAIL=admin@<DOMAIN_TBD>
- Default ok: TTS_VOICE=it-IT-DiegoNeural, ORGANIZATION_NAME=corsi8108,
  PIPELINE_TIMEOUT=1800, MAX_CONCURRENT_JOBS=1
- 2 user DB: nexus_admin (DDL/migrazioni) e nexus_app (runtime, no
  DELETE/UPDATE audit_log) — separazione di privilegi BP §02.6

GIT / GITHUB
- Branch corrente: feat/phase6-frontend-shadcn (LOCALE, mai pushato)
- Branch main esiste
- Ultimo commit: 8958e89 "fix(31): pipeline surgery"
- Nessuna PR aperta (gh pr list = [])
- 8 file Python backend modificati non committati (#31.5/6/7) +
  fix #31.8 in arrivo
- 18+ docs ?? non tracciati (REPLY_TO_ANALYST_*, SCALING_ANALYSIS,
  H6_IMPLEMENTATION_PLAN, HANDOFF_PHASE*, GAPS_TO_DEFINE_BEFORE_PHASE7)
- .gitignore copre: __pycache__, .env, output/, *.pptx.bak,
  storage/pdfs/*.pdf — sembra ragionevole, ma da verificare
  esplicitamente che storage/output/ e frontend/dist/ siano coperti

CORPUS DB (~2000 chunk)
- D.Lgs 81/08: 1819 chunk
- ASR 17/04/2025: 133 chunk
- ASR 21/12/2011: 27 chunk (legacy residuo)
- DM 388/2003 Primo Soccorso: 23 chunk
- ASR 07/07/2016: 1 chunk (residuo)
- Totale: 2003 chunk con embedding voyage-3 (1024 dim)
- Indici HNSW pgvector

═══════════════════════════════════════════════════════════════════
COSA È FEASIBLE OGGI (data l'analisi)
═══════════════════════════════════════════════════════════════════

✅ Backend FastAPI Dockerizzato → deployabile su Railway via
   Dockerfile (Railway supporta nativamente Docker)
✅ PostgreSQL + pgvector → Railway ha plugin PostgreSQL ma NON
   pgvector di default (DA VERIFICARE: serve immagine custom o
   plugin Marketplace?)
✅ Frontend SPA pura → Vercel ideale (static hosting + edge CDN)
✅ pnpm + vite → Vercel ha runtime nativo
✅ WebSocket backend → FastAPI WS funziona, ma su Vercel SOLO
   reverse-proxy a Railway (Vercel serverless functions NON
   reggono WS persistenti); il client FE si connette
   DIRETTAMENTE all'URL Railway via wss://
✅ Build artifacts ready: frontend/dist/ esiste già
✅ Edge-tts: no key, no rate limit grave (~6 paralleli OK)

═══════════════════════════════════════════════════════════════════
COSA NON È FEASIBLE OGGI / RICHIEDE LAVORO PREP
═══════════════════════════════════════════════════════════════════

❌ pgvector su Railway PostgreSQL plugin → DA VERIFICARE.
   Opzione fallback: deployare un container PostgreSQL custom
   con pgvector estensione installata (Railway Template
   "PostgreSQL + pgvector" disponibile?). Se no, dobbiamo:
     - Creare Dockerfile su pgvector/pgvector:pg16
     - Deploy come service separato Railway
     - Costo: piano hobby gratuito 512MB RAM dovrebbe bastare per
       2000 chunk, ma le query HNSW pgvector saranno lente sotto
       512MB. Probabile bisogno piano Hobby $5/mese (5GB RAM).

❌ Storage volumes per PPTX/PDF generati → Railway volumes
   esistono ma sono LIMITATI a 5GB su piano Hobby. Demo #3 è
   76 MB, 50 corsi = 3.8 GB. Va bene per la demo ma a scala
   serve S3/R2.
   Soluzione: per la demo iniziale uso volume Railway 5GB.
   Quando il cliente firma, migro a Cloudflare R2.

❌ Ingestion normative (~30 min al primo run): va eseguita UNA
   TANTUM sul Postgres Railway dopo il primo deploy. Posso usare
   lo stesso script `scripts/ingest_*.py` esistente puntandolo
   al DATABASE_URL Railway.

❌ Secret management produzione: oggi tutte le keys sono in
   .env locale. Su Railway/Vercel vanno settate come env vars
   ENCRYPTED via UI/CLI. Le mie keys personali (Anthropic +
   Voyage + Brave) sono in .env locale — l'utente le ha già
   detto utilizzabili per la demo cliente ("le mie chiavi", da
   memoria sessioni precedenti).

❌ Branch feat/phase6-frontend-shadcn mai pushato → bisogna
   pushare per Railway/Vercel possano puntare al repo GitHub.
   Quanti commit accumuli e con quale strategia?

❌ Audit code cleanup pre-commit: ruff + mypy + pytest non
   girati post-#31.5/6/7. Probabile debt accumulato.

❌ Aggiornamento Tracker (REI-12) e VERIFICATION_DEBT (REI-17):
   non aggiornati per le ultime 5 sotto-fasi #31.5 → #31.8.

❌ Custom domain HTTPS: REI-13 dice "dominio NON deciso fino
   al deploy". Sul deploy iniziale Vercel usa
   eduvault-<hash>.vercel.app gratis. Per dominio custom serve
   DNS setup del cliente (corsi8108.it?).

═══════════════════════════════════════════════════════════════════
DOMANDE STRUTTURATE PER DOMINIO
═══════════════════════════════════════════════════════════════════

──── RAILWAY (backend + PostgreSQL pgvector) ────

R1. Hai esperienza con pgvector su Railway o usiamo un Postgres
    self-hosted custom? Se self-hosted, va bene `pgvector/pgvector:pg16`
    come image nostra in un service Railway?

R2. Piano Railway: Hobby $5/mese (5GB RAM, 5GB volume) basta per
    demo cliente (max 50 corsi paralleli mai)? Oppure Starter
    gratuito (512MB) prima e vediamo?

R3. Dockerfile attuale (backend) include LibreOffice per
    PDF/PPTX rendering? Lo build sarà ~2GB image, Railway
    sostiene? (Da verificare image size locale prima di
    deployare).

R4. CORS: dopo deploy Vercel ottengo URL tipo
    https://eduvault-prod.vercel.app — lo metto in
    FRONTEND_URL backend env. Va bene wildcard temporanea
    *.vercel.app per i preview deploy o preferisci esplicito?

──── VERCEL (frontend shadcn-admin) ────

V1. Sostituisco netlify.toml → vercel.json con:
      { "rewrites": [{"source": "/(.*)", "destination": "/index.html"}] }
    Sufficiente per SPA fallback, o vuoi configurazione più
    elaborata (custom headers, redirects)?

V2. Env var Vercel:
      VITE_API_URL=https://<railway-domain>.up.railway.app
    (mi ricordo che il codice usa `import.meta.env.VITE_API_URL`
    dato Vite, NON `process.env.NEXT_PUBLIC_API_URL` — da
    verificare nel codice FE). Confermi sì?

V3. WebSocket: il client FE si connette a
      wss://<railway-domain>/ws/<job_id>
    direttamente, bypassando Vercel. Va bene questa scelta o
    vuoi proxy Vercel?

V4. Branch deploy: Vercel auto-deploya da feat/phase6-frontend-shadcn
    (preview URL per ogni push) oppure da main (production URL
    sola)?

──── GITHUB (commit strategy + PR) ────

G1. Strategia commit per i fix #31.5/6/7/8:
      OPZIONE A: 4 commit atomici separati (uno per fix), storia
                 pulita, code review modulare
      OPZIONE B: 1 commit consolidato "fix(31.5-8): scaling +
                 diagrammi + retrieval", più veloce
    Tu preferisci storia pulita (A) o velocità (B)?

G2. Per Phase 6 frontend ho il branch feat/phase6-frontend-shadcn
    mai pushato. Lo pusho subito e apro PR `→ main` con squash
    merge? Oppure pusho prima di tutto, lavoriamo direttamente
    su feat/ con PR finale solo al deploy?

G3. Code review: chi fa la review della PR? Te la faccio passare
    tu (preferibile) o uso la skill ultrareview di Claude Code
    (review semi-automatica multi-agente, ~10 min)?

G4. Branch protection: vuoi che main richieda review approval +
    CI verde prima del merge? Oppure niente protezioni per ora
    (siamo solo io + tu)?

──── CODE CLEANUP pre-commit ────

C1. I 18+ docs `??` (REPLY_TO_ANALYST_*, SCALING_ANALYSIS,
    GAPS_*, HANDOFF_*) li committo come trail di audit
    (utile per posterità) o li cancello e tengo solo i fix
    di codice?

C2. ruff/mypy/pytest pre-commit (REI-6): li faccio girare TUTTI
    PRIMA del commit dei fix #31, fixo i lint/type issues
    accumulati, OPPURE accetti debt e lo fixiamo dopo deploy?

C3. Aggiornamento REI-12 (Project Status Tracker) + REI-17
    (VERIFICATION_DEBT) per #31.5/6/7/8: lo faccio adesso PRIMA
    del commit, oppure batchiamo con altre cose?

C4. Audit secret: i miei docs REPLY_TO_ANALYST_* NON contengono
    API keys (li ho rivisti). Ma confermo? Posso lanciare
    `git secret scan` o usare tool tipo trufflehog?

──── CHROME DEVTOOLS test pre-deploy ────

D1. Flow critico da testare end-to-end:
      OPZIONE A: Login admin → wizard nuovo corso → vedere
                 progress real-time → scaricare PPTX/PDF
      OPZIONE B: Studio editing slide singola (creata in A) →
                 rebuild → confronto pre/post
      OPZIONE C: Tutti i flow (più completo, ~40 min)
    Quale priorità?

D2. Test browser: usiamo Chrome DevTools MCP installato
    (memoria sessioni: 6 MCP attivi incluso chrome-devtools)
    o Playwright dell'estensione frontend?

D3. Lighthouse audit: necessario o overkill per la prima demo?
    (Demo NON cerca SEO, è admin-only).

──── DEPLOY ORDINE + TIMING ────

DP1. Sequenza:
       1. Cleanup + commit + push GitHub
       2. Deploy Postgres pgvector custom su Railway
       3. Run ingestion script con DATABASE_URL Railway
       4. Deploy backend FastAPI su Railway (puntando a Postgres
          Railway interno)
       5. Get backend Railway URL
       6. Update FE env var con backend URL
       7. Deploy frontend su Vercel
       8. Update backend CORS con frontend URL
       9. Verifica end-to-end via DevTools
    Va bene questo ordine?

DP2. Tempo realistico atteso per primo deploy "test" che
    l'utente vuole vedere: 4-6 ore lavoro mio (cleanup commit
    1h, deploy Railway 2h, deploy Vercel 30min, DevTools test
    1h, fix issues emergenti 1-2h). Confermi questa stima o
    eri su tempo diverso?

DP3. Risk: il primo deploy potrebbe richiedere 2-3 iterazioni
    per fix specifici (env vars sbagliate, build issues, CORS).
    Posso fare i deploy "tentativi" senza chiederti conferma
    per ogni piccolo fix incrementale, o vuoi essere notificato
    a ogni step?

═══════════════════════════════════════════════════════════════════
LA MIA PROPOSTA SEQUENZA (modificabile)
═══════════════════════════════════════════════════════════════════

GIORNATA 1 (parallela al lavoro fix #31.8 Demo #3):
  09:00-10:00 Cleanup code (ruff/mypy/pytest), aggiornamento
              Tracker + VERIFICATION_DEBT
  10:00-11:00 Commit atomici #31.5/6/7/8 + push branch +
              apertura PR feat/phase6-frontend-shadcn → main
  11:00-12:00 Setup Railway: provisioning Postgres pgvector
              + backend service + env vars
  14:00-15:00 Ingestion normative su DB Railway (~30 min auto)
  15:00-16:00 Deploy backend FastAPI Railway + smoke test
              endpoint /health
  16:00-17:00 Setup Vercel: vercel.json + env vars + first deploy

GIORNATA 2:
  09:00-10:00 DevTools end-to-end test (flow A: wizard + corso)
  10:00-12:00 Fix issues emergenti deploy (CORS, env vars,
              build issues, ecc.)
  14:00       Demo "tester" pronto per essere mostrato
              all'utente + cliente

═══════════════════════════════════════════════════════════════════
COSA NON HO ANCORA VERIFICATO (incertezze residue)
═══════════════════════════════════════════════════════════════════

? Dimensione Docker image backend (LibreOffice incluso) — da
  misurare con `docker images`
? Compatibilità Vercel SPA con WebSocket proxy diretto Railway
  (esempio: alcuni firewall corporate bloccano WSS subdomains)
? Migrazioni Alembic vs raw SQL — uso il file
  `app/db/migrations/*.sql` puro o c'è Alembic configurato?
? Eventuali secret hardcoded nel codice (lancio grep prima del
  commit per sicurezza)
? Dimensione volume Railway necessaria oltre PostgreSQL
  (PPTX cumulative storage)

═══════════════════════════════════════════════════════════════════

Aspetto le tue risposte R1-R4, V1-V4, G1-G4, C1-C4, D1-D3, DP1-DP3.
Quando le ho, parto col deploy testabile entro 1-2 giorni
lavorativi.

(Messaggio separato: ho fatto anche lo spot-check Demo #2 M3
"Diritti e doveri" che mi avevi chiesto in review 11 — vedi
REPLY_TO_ANALYST_DEMO2_SPOTCHECK.md o il messaggio gemello in
chat — verdetto: 23% off-topic, gate borderline ROSSO.)
