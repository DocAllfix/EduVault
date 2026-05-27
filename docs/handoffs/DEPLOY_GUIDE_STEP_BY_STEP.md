# Guida Deploy Step-by-Step — Railway (backend) + Vercel (frontend)

**Data**: 2026-05-27 — preparata in attesa OK utente per partire.

**Contesto**: l'utente ha **altri progetti già su Railway e Vercel**.
Questa guida è scritta per non confondere/sovrascrivere niente:
ogni step indica esattamente cosa fare nella UI, quali dropdown
selezionare, quali variabili settare, quali errori potresti vedere.

**Premesse VERIFICATE prima di partire** (checklist pre-flight):
- [ ] Branch `main` aggiornato con squash merge PR #1 (FATTO post-A2)
- [ ] Account Railway esistente loggato (`railway whoami` OK)
- [ ] Account Vercel esistente collegato a GitHub
- [ ] 3 PPTX su Desktop: CFP_4h_E25_REBUILD_31.7A_v2.pptx,
      DEMO2_Generale_4h_v3.pptx, DEMO3_Preposti_8h_v2.pptx
- [ ] 3 JSON dump generati in storage/dumps/ (script eseguito)
- [ ] Trufflehog scan zero secret leak (FATTO)

═══════════════════════════════════════════════════════════════════
# PARTE 1 — RAILWAY (backend FastAPI + Postgres pgvector)
═══════════════════════════════════════════════════════════════════

## 1.A — Login + verifica account

```powershell
railway login
# Apre browser → autorizza CLI → "Logged in as <email>"
railway whoami
# Mostra email account loggato
```

**Se hai più account Railway**: `railway logout` e poi `railway login`
con account giusto.

## 1.B — Creare NUOVO progetto (NON confonderlo con esistenti)

**Via WEB UI** (più sicuro per non sbagliare):
1. Vai su https://railway.com/dashboard
2. Click **"+ New Project"** (in alto a destra)
3. Selezione popup → click **"Empty Project"** (NON "Deploy from
   GitHub repo" — lo collegheremo dopo manualmente per controllo
   maggiore)
4. **Nome progetto**: `nexus-eduvault-demo` (descrittivo, distingue
   dai tuoi altri progetti)
5. Click **"Create"**

**Risultato**: vedi il dashboard del progetto vuoto, nessun service.
URL del progetto tipo `https://railway.com/project/abc123-def-456`.

## 1.C — Aggiungere service PostgreSQL con pgvector custom

**ATTENZIONE**: NON usare il plugin "Database → PostgreSQL" standard
Railway perché NON include pgvector extension. Usiamo image custom.

1. Nel progetto, click **"+ New"** (in alto al centro o tasto N)
2. Selezione popup → click **"Empty Service"**
3. Service appena creato → click sul service per aprire i settings
4. Tab **"Settings"** (sidebar destra)
5. Sezione **"Source"**:
   - Click **"Connect"** o **"Configure"**
   - Selezione **"Docker Image"**
   - Image name: `pgvector/pgvector:pg16`
   - Click **"Deploy"** (in basso)
6. Tab **"Variables"**:
   - Click **"+ New Variable"** per ognuna (oppure "Raw Editor" per
     incollare insieme):
   ```
   POSTGRES_DB=nexus
   POSTGRES_USER=nexus_admin
   POSTGRES_PASSWORD=<GENERA con `openssl rand -base64 32`>
   PGDATA=/var/lib/postgresql/data/pgdata
   ```
7. Tab **"Settings" → "Volumes"**:
   - Click **"+ Add Volume"**
   - Mount path: `/var/lib/postgresql/data`
   - Size: 5 GB (Hobby plan default)
8. Tab **"Settings" → "Networking"**:
   - **Public Networking**: lascia DISABILITATO (Postgres NO accesso
     pubblico per sicurezza, accesso solo da rete interna Railway)
   - **Private Networking**: già abilitato (default Railway), genera
     hostname tipo `postgres.railway.internal`
9. Click **"Deploy"** in alto → attendi che il service diventi
   verde ("Active")
10. Tab **"Connect"**: copia `DATABASE_URL` (formato
    `postgresql://nexus_admin:PASSWORD@postgres.railway.internal:5432/nexus`)
    → SALVALA in un editor, ti servirà al passo 1.E

**Verifica**: tab "Deployments" → ultimo deploy "Active" + log
mostra `database system is ready to accept connections`.

## 1.D — Aggiungere service Backend FastAPI

1. Nel progetto, click **"+ New"** di nuovo
2. Selezione popup → click **"GitHub Repo"**
3. **Connect GitHub** (se primo deploy del progetto):
   - Autorizza Railway su GitHub (tab pop-up)
   - Selezione repository: `DocAllfix/EduVault`
   - Branch: `main` (post-squash merge)
4. Service creato → click per aprire
5. Tab **"Settings"**:
   - **Service name**: `nexus-eduvault-backend`
   - **Root directory**: `/` (default, contiene Dockerfile)
   - **Build settings**: Railway auto-rileva `Dockerfile` e lo usa.
     NB: image build ~8-12 min al primo deploy (LibreOffice 800MB
     + Python deps 1.5GB = ~2.31GB totali)
   - **Watch paths**: lascia `**` (auto-deploy su ogni push a `main`)
6. Tab **"Variables"** → "Raw Editor":
   ```
   # === Database (URL dal passo 1.C) ===
   DATABASE_URL=postgresql://nexus_admin:PASSWORD@postgres.railway.internal:5432/nexus
   DATABASE_ADMIN_URL=postgresql://nexus_admin:PASSWORD@postgres.railway.internal:5432/nexus

   # === External API keys (USA le tue chiavi reali) ===
   ANTHROPIC_API_KEY=sk-ant-...
   VOYAGE_API_KEY=pa-...
   BRAVE_SEARCH_API_KEY=BSA-...

   # === JWT (genera con `openssl rand -hex 64`) ===
   JWT_SECRET=<GENERA-LUNGO-128-CHAR>
   JWT_ALGORITHM=HS256
   JWT_EXPIRY_MINUTES=60
   JWT_REFRESH_EXPIRY_DAYS=7

   # === Runtime / CORS (FRONTEND_URL si setta DOPO Vercel deploy, vedi 2.E) ===
   APP_DOMAIN=<IL-DOMINIO-RAILWAY-DEL-BACKEND>
   APP_BASE_URL=https://<IL-DOMINIO-VERCEL>.vercel.app
   API_BASE_URL=https://<IL-DOMINIO-RAILWAY-BACKEND>.up.railway.app
   FRONTEND_URL=https://<IL-DOMINIO-VERCEL>.vercel.app
   PIPELINE_TIMEOUT=1800
   LLM_REQUEST_TIMEOUT=120
   MAX_CONCURRENT_JOBS=1

   # === TTS edge-tts (no key) ===
   TTS_VOICE=it-IT-DiegoNeural

   # === Seed admin (USA tue credenziali reali) ===
   ADMIN_BOOTSTRAP_EMAIL=admin@cfp-montessori.demo
   ADMIN_BOOTSTRAP_PASSWORD=<GENERA con `openssl rand -base64 24`>

   # === Branding ===
   ORGANIZATION_NAME=corsi8108

   # === Frontend Vite (passa al build Vercel, qui irrilevante) ===
   # NEXT_PUBLIC_API_URL non usata da backend, è var di build Vercel
   ```
7. Tab **"Settings" → "Networking"**:
   - Click **"+ Generate Domain"** (Public Networking)
   - Railway genera tipo `nexus-eduvault-backend-production.up.railway.app`
   - SALVALA → servirà al passo 2.D (Vercel env VITE_API_URL)
8. Tab **"Settings" → "Volumes"**:
   - Click **"+ Add Volume"**
   - Mount path: `/app/output` (per PPTX/PDF generati)
   - Size: 5 GB
9. Click **"Deploy"** in alto → attendi ~8-12 min primo build
   (segui log in tab "Deployments")

**Risultato atteso log**: `INFO: Uvicorn running on http://0.0.0.0:8000`

**Verifica via curl** (dal tuo PowerShell):
```powershell
curl https://nexus-eduvault-backend-production.up.railway.app/health
# Atteso: {"status":"healthy","database":"connected"}
```

⚠️ **Se /health torna 500 con "database not configured"**: env
DATABASE_URL non risolto. Verifica che hostname `postgres.railway.internal`
sia corretto (vai a service Postgres → tab Connect → copia URL).

## 1.E — Eseguire migrations + ingestion normative

Migration SQL (le 4 file .sql in `app/db/migrations/`):

```powershell
# Da locale PowerShell, ti colleghi al DB Railway via railway run:
railway link
# Selezione progetto: nexus-eduvault-demo → service: postgres

# Esegui migrations in ordine
railway run -- psql -f app/db/migrations/001_initial.sql
railway run -- psql -f app/db/migrations/002_audio_target.sql
railway run -- psql -f app/db/migrations/003_course_studio.sql
railway run -- psql -f app/db/migrations/004_add_citation_label.sql
railway run -- psql -f app/db/migrations/setup_roles.sql
railway run -- psql -f app/db/migrations/setup_langgraph_grants.sql
```

Setup admin user (seed):
```powershell
railway run -- python scripts/seed.py
# Atteso: "Admin user created: admin@cfp-montessori.demo"
```

Ingestion normative (~30 min totali):
```powershell
# Upload PDF normative al volume Railway backend (o usa scripts/ingest_*.py
# che li scaricano automaticamente da gazzettaufficiale.it)
railway run -- python scripts/ingest_dlgs_81_08.py    # ~20 min, 1819 chunk
railway run -- python scripts/ingest_accordi.py       # ~5 min, 133 chunk ASR 2025
railway run -- python scripts/ingest_dm388.py          # ~2 min, 23 chunk
```

**Verifica DB popolato**:
```powershell
railway run -- psql -c "SELECT title, COUNT(c.id) AS chunks FROM regulations r LEFT JOIN regulation_chunks c ON c.regulation_id = r.id GROUP BY r.title;"
# Atteso:
#  D.Lgs 81/08          | 1819
#  Accordo SR 2025     |  133
#  DM 388/2003         |   23
```

═══════════════════════════════════════════════════════════════════
# PARTE 2 — VERCEL (frontend Vite SPA)
═══════════════════════════════════════════════════════════════════

## 2.A — Login Vercel

Via WEB UI (preferito per non confondere account):
1. Vai su https://vercel.com/login
2. Login con stesso account GitHub di `DocAllfix/EduVault`

**Verifica account**: il dashboard mostra i progetti esistenti.
NON ci devono essere conflitti perché creeremo un nuovo progetto.

## 2.B — Importare il progetto

1. Dashboard Vercel → click **"Add New..."** (in alto a destra)
2. Selezione popup → click **"Project"**
3. Tab **"Import Git Repository"**:
   - Cerca `DocAllfix/EduVault` (Vercel lo trova se hai autorizzato
     GitHub all'inizio)
   - Click **"Import"** sulla riga del repo
4. Pagina **"Configure Project"**:
   - **Project Name**: `nexus-eduvault-demo` (stesso nome Railway
     per coerenza)
   - **Framework Preset**: dovrebbe rilevare **"Vite"**
     automaticamente. Se no, selezione manuale "Vite".
   - **Root Directory**: click **"Edit"** → seleziona `frontend`
     (IMPORTANTE: il repo ha frontend in subdirectory, NON root)
   - **Build Command**: Vercel auto-rileva `pnpm build` da
     `vercel.json` (FATTO commit pre-deploy). Se sbagliato → sovrascrivi
     a `pnpm build`.
   - **Output Directory**: `dist` (default da vercel.json)
   - **Install Command**: `pnpm install --frozen-lockfile` (da vercel.json)
5. **Environment Variables** (espansione "Environment Variables"):
   - Click **"+ Add"**
   - Name: `VITE_API_URL`
   - Value: `https://nexus-eduvault-backend-production.up.railway.app`
     (URL Railway dal passo 1.D)
   - Environment: selezione **Production, Preview, Development** (tutti)
6. Click **"Deploy"**

**Risultato atteso**: build verde in ~2 minuti. Vercel mostra
"Congratulations! 🎉" con URL del production deploy tipo
`https://nexus-eduvault-demo.vercel.app`. SALVALA.

## 2.C — Verifica deploy frontend

```powershell
curl https://nexus-eduvault-demo.vercel.app
# Atteso: HTML 200 OK con <title>Nexus EduVault</title> o simile
```

Apri nel browser: dovresti vedere la pagina di login C.F.P. Montessori.

⚠️ **Se mostra 404 su qualsiasi route diversa da `/`**: vercel.json
SPA rewrite non applicato → ricontrolla che `vercel.json` sia in
`frontend/` (NON root repo).

## 2.D — Aggiornare CORS backend con URL Vercel

Torna su Railway → service backend → tab Variables → modifica:
```
APP_BASE_URL=https://nexus-eduvault-demo.vercel.app
FRONTEND_URL=https://nexus-eduvault-demo.vercel.app
```
Click **"Deploy"** in alto per re-deploy con nuove env vars (~30s,
no rebuild image, solo restart container).

⚠️ NON usare wildcard `*.vercel.app` (analista R4: violazione policy
security).

═══════════════════════════════════════════════════════════════════
# PARTE 3 — CARICAMENTO 3 DEMO PPTX + RECORDS DB
═══════════════════════════════════════════════════════════════════

## 3.A — Upload PPTX nel volume Railway

```powershell
# Copia i 3 PPTX dal Desktop al volume Railway
railway link  # se non già linkato
railway run -- mkdir -p /app/output

# Copia 1 PPTX alla volta (railway run non supporta scp diretto,
# usa workaround tramite cat | base64 pipe)
# Workaround alternativo: rinominare i file su Desktop e poi caricarli via
# uno script Python che usa Railway API (più stabile)
```

**Approccio raccomandato** (più affidabile): script Python che
INSERT direttamente i 3 records DB + upload PPTX:

```powershell
# Da locale PowerShell con railway link attivo:
railway run -- python scripts/seed_3_demo_on_railway.py
```

Lo script `scripts/seed_3_demo_on_railway.py` (da creare):
- Legge i 3 JSON dump in `storage/dumps/` (preparati pre-deploy)
- INSERT 3 records in `courses` con status='completed'
- Per ogni record, fa anche upload PPTX/PDF via Railway volume API
  (o se non disponibile, ti istruisce su come uploadarli via SCP
  manuale)

**Alternativa manuale** (più lenta ma sicura):
1. Sul backend Railway, esponi temporaneamente endpoint upload PPTX
2. Da PowerShell: `curl -X POST -F "file=@C:\Users\user\Desktop\DEMO2_..."
   https://backend.railway.app/admin/upload-demo-pptx`
3. Lo script seed_3_demo_on_railway.py poi INSERT i records che
   puntano ai PPTX appena caricati

⚠️ Decisione UTENTE: A o B? Domanda da fare quando arriviamo qui.

## 3.B — Verifica 3 demo visibili in app

```powershell
curl https://backend.railway.app/api/courses
# Atteso: 3 courses con status='completed', pptx_path settato
```

Apri browser → URL Vercel → login admin → Dashboard:
- Vedi 3 demo come cards
- Click su 1 → vedi dettaglio + download PPTX/PDF funziona

═══════════════════════════════════════════════════════════════════
# PARTE 4 — CHROME DEVTOOLS TEST FLOW A (gate pre-consegna)
═══════════════════════════════════════════════════════════════════

## 4.A — Flow A test (analista review deploy DP1)

Usa Chrome DevTools MCP (già installato in `.mcp.json`):

1. Apri Chrome → URL Vercel
2. Apri DevTools (F12) → Network tab
3. Login admin → controlla che POST /auth/login risponda 200
4. Dashboard → controlla 3 corsi visibili
5. Click "Nuovo corso" → wizard 5 step → seleziona "Specifica
   Rischio Basso 4h" → submit
6. Verifica POST /api/courses risponde 201 con `course_id` + `job_id`
7. Redirect a /course-progress/{job_id} → controlla WebSocket
   connection (Network → WS tab → frame `101 Switching Protocols`)
8. Watch progress bar real-time per ~10 min
9. Status `completed` → redirect /course-detail/{id}
10. Click Download PPTX → file scaricato

**Gate**: se Flow A passa → demo pronto consegna. Se salta a metà
→ debug step specifico (network logs).

## 4.B — Flow B (Course Studio) opzionale

Apri 1 demo → click "Apri Studio" → modifica titolo slide → save
→ click Rebuild → download nuovo PPTX → verifica modifica visibile.

═══════════════════════════════════════════════════════════════════
# CHECKLIST FINALE PRE-CONSEGNA CLIENTE
═══════════════════════════════════════════════════════════════════

- [ ] Backend Railway /health risponde 200
- [ ] Frontend Vercel pagina login si apre
- [ ] Login admin funziona
- [ ] Dashboard mostra 3 corsi demo
- [ ] Download PPTX/PDF dei 3 demo funziona
- [ ] Wizard nuovo corso completa end-to-end (Flow A test)
- [ ] WebSocket progress real-time funziona
- [ ] Course Studio aprile + modifica + rebuild + download (Flow B)
- [ ] URL mandata all'analista per sanity check finale
- [ ] OK analista ottenuto
- [ ] Email cliente con: URL + credenziali admin + nota framing

═══════════════════════════════════════════════════════════════════
# TROUBLESHOOTING COMUNI
═══════════════════════════════════════════════════════════════════

| Errore | Causa probabile | Fix |
|---|---|---|
| Railway backend `503` | Image build fallito (LibreOffice timeout) | Aspetta retry automatico, controlla log "Building image..." |
| `pgvector extension does not exist` | Service Postgres usa plugin standard non `pgvector/pgvector` | Ricreare service con image custom (passo 1.C) |
| Vercel `Module not found '@/...'` | Path alias Vite non risolti su Vercel | Verifica `tsconfig.json` paths esistono in `frontend/` (dovrebbero) |
| Frontend Vercel: blank page | `VITE_API_URL` mancante o sbagliata | Settings → Environment Variables → controlla URL Railway corretto |
| Frontend: 404 su /dashboard | SPA rewrite non funziona | Verifica vercel.json in `frontend/` (NON root) |
| WebSocket non si connette | CORS backend non include URL Vercel | Aggiorna FRONTEND_URL su Railway (passo 2.D) |
| Login: `Invalid token` | JWT_SECRET cambia tra restart Railway | Verifica env JWT_SECRET sia FISSO (non rigenerare a ogni deploy) |
| `relation "courses" does not exist` | Migrations non eseguite | Passo 1.E `railway run -- psql -f ...` |
| Ingestion `voyageai 401` | VOYAGE_API_KEY sbagliata | Verifica chiave reale (NON placeholder .env.example) |

═══════════════════════════════════════════════════════════════════
# COSTI STIMATI (per stima utente)
═══════════════════════════════════════════════════════════════════

**Railway Hobby Plan**: $5/mese
- Postgres pgvector custom: ~512MB RAM ($2.50)
- Backend FastAPI con LibreOffice: ~512MB RAM ($2.50)
- Storage volumes: 10 GB totali (incluso nel piano)
- Total: $5/mese fissi + $0.000463/GB-h network out

**Vercel Hobby Plan**: $0 (gratuito per progetti non-commercial)
- 100 GB bandwidth/mese
- Build minutes: 6000/mese
- Per la demo cliente: ampiamente sufficiente

**API esterne** (costi a uso, no abbonamento):
- Anthropic Claude API: ~$0.10-0.30 per corso 4h, $0.20-0.50 per 8h
- Voyage embeddings: ~$0.01 per corso (embedding query, no
  re-ingestion)
- Pexels: gratuito (rate limit 200 req/h)
- edge-tts (audio): gratuito (no API key)

**Costo demo cliente totale**: ~$5/mese hosting + ~$1-2 per
generazione 3-5 corsi test = ~$10-15 totali primo mese.
