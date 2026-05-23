# NEXUS EDUVAULT — ABSOLUTE MASTER ARCHITECTURAL BLUEPRINT

## SUPREME PRODUCTION READY v7.0

**Classificazione:** Confidenziale — Solo per uso interno
**Data:** 12 Maggio 2026
**Versione:** 6.0 Supreme Production Ready
**Stato:** Costituzione Tecnica Definitiva — Unica Fonte di Verità
**Sviluppatore:** axialoop
**Dominio:** corsi8108.it

> **Questo documento è l'unica fonte di verità del progetto Nexus EduVault.**
> È autosufficiente e onnicomprensivo. Contiene ogni specifica operativa — inclusi tutti i contratti Pydantic, la logica completa del PacingEngine con titoli semantici dal COURSE_CATALOG, lo StylePatternExtractor deterministico, i prompt engineering, la strategia di chunking ibrida (rule-based + LLM) con coverage check normalizzato, la query RAG semantica (non slug) con threshold di rilevanza, la gestione errori LLM con timeout globale e circuit breaker, la concorrenza blindata, il rate limiting, il seeding, il pattern di dependency injection per pool e shutdown event e Voyage client, il COURSE_CATALOG completo, lo schema SQL con protezione compliance dell'audit log e indici di integrità, la sanitizzazione SVG, e gli endpoint preview/ZIP.
> Non esistono errata, audit, appendici o documenti supplementari da consultare.
> Chi sviluppa tramite Claude Code deve usare questo documento come sorgente esclusiva.

---

## §00 — EXECUTIVE SUMMARY

Nexus EduVault è un motore di produzione corsi AI-driven costruito per generare corsi di formazione normativamente corretti per costruzione, non per approssimazione. Il sistema ingesta normative italiane ed europee, le decompone semanticamente in unità citabili (articolo/comma), le indicizza in una Knowledge Base stratificata a due livelli e le trasforma in corsi completi — slide PPTX branded, dispense PDF strutturate, quiz di verifica — con tracciabilità punto-per-punto tra ogni affermazione e l'articolo di legge che la sostiene.

**Principio architetturale fondamentale:** la normativa è la fonte di verità, non l'intelligenza artificiale. L'AI compone contenuti a partire da testi legislativi reali recuperati dalla Knowledge Base interna. Ogni affermazione presente in una slide è ancorata a un riferimento normativo verificabile. Il sistema sa cosa sta citando e perché.

### Parametri Operativi

| Parametro | Valore |
|---|---|
| **Utenti** | 5–15 simultanei — 3 ruoli (Admin, Operatore, Revisore) |
| **Deploy** | Istanza privata dedicata single-tenant, datacenter EU, VPS 4 vCPU / 8 GB RAM |
| **Pipeline** | 2 agenti LangGraph (Research + Content) + 1 Production Builder deterministico, orchestrati con checkpointing PostgreSQL, timeout globale 30 minuti e circuit breaker sui moduli |
| **Output** | PPTX branded + PDF dispensa + Quiz JSON + log con fingerprint normativo |
| **Tempo** | Corso 8h (250+ slide) in < 15 minuti |
| **Concorrenza** | 1 job alla volta per istanza (asyncio.Semaphore — vincolo architetturale, non solo di risorse), job successivi in coda con posizione visibile |
| **Autenticazione** | JWT custom + bcrypt (TOTP predisposto nello schema, attivabile in v1.1) — nessun Supabase |
| **Multi-tenancy** | Single-tenant by design — nessun rischio di contaminazione cross-istanza |

### Decisione Architetturale: Perché Non Supabase

Supabase (Auth, DB, Storage) è stato valutato e scartato. Per un deploy single-tenant su VPS dedicato, Supabase aggiunge un layer di astrazione inutile: il suo Auth è progettato per SaaS multi-tenant, le sue Row Level Security policies sono ridondanti quando l'intera istanza appartiene a un solo cliente, e il suo Storage introduce una dipendenza esterna non necessaria per file serviti da filesystem locale. L'architettura usa PostgreSQL diretto con asyncpg, JWT custom con bcrypt, e storage su volume Docker locale. Questo garantisce sovranità totale del dato, deploy riproducibile e zero dipendenze cloud proprietarie.

### Feature Differite a v1.1 (Schema DB Pronto, Logica Non Implementata)

| Feature | Stato in v1.0 | Piano v1.1 |
|---|---|---|
| TOTP 2FA | Colonna `totp_secret` presente nello schema. Nessun flusso frontend/backend | Flusso completo: QR code setup, verifica al login |
| Delta-Update | `normative_fingerprint` + `source_chunk_ids` salvati. Nessuna logica di diff | Diff automatico al cambio normativo, ri-generazione selettiva moduli |
| Recovery intelligente | Job bloccati resettati a `failed` al restart | Resume da checkpoint LangGraph per fasi `research`/`content` |
| Diagrammi SVG generati da LLM | Tipo DIAGRAM presente nel modello SlideType ma escluso dalla distribuzione PacingEngine. Se l'LLM lo genera spontaneamente, viene sanitizzato e renderizzato con fallback a placeholder | PacingEngine include DIAGRAM nella distribuzione. Template SVG preconfezionati dove l'LLM popola solo i testi |

---

## §01 — STACK TECNOLOGICO BLINDATO

### 1.1 Stack Backend

| Componente | Tecnologia | Versione | Ruolo |
|---|---|---|---|
| Runtime | Python | 3.12 | Linguaggio backend |
| API Framework | FastAPI | ≥0.111 | REST + WebSocket, async nativo, validazione Pydantic v2, auto-documentazione OpenAPI |
| Orchestrazione AI | LangGraph | ≥0.2 | State machine per i 2 agenti (Research + Content), checkpointing PostgreSQL, retry automatico, tracing. Il Production Builder è una funzione post-pipeline, non un nodo LangGraph |
| Modello AI | Claude Sonnet 4 (Anthropic) | — | Generazione contenuti, classificazione chunk, generazione diagrammi SVG. Context window 200K token |
| Embedding | Voyage AI (voyage-3) | — | Embedding vettoriali per ricerca RAG, ottimizzati per testo normativo multilingua (1024 dim) |
| Generazione PPTX | python-pptx | ≥0.6.23 | Creazione slide con controllo completo su layout, font, colori, posizionamento logo. **NON thread-safe** — usare solo con Semaphore(1) |
| Rendering SVG→PNG | cairosvg | ≥2.7 | Conversione diagrammi SVG (generati dall'LLM) in immagini PNG per embedding in PPTX |
| Generazione PDF | WeasyPrint | ≥61 | HTML/CSS → PDF con supporto per impaginazione, header/footer, indice automatico |
| Database | PostgreSQL 16 + pgvector | 16.x | Relazionale + estensione vettoriale. Indice HNSW per ricerca similarità sub-secondo |
| DB Driver | asyncpg | ≥0.29 | Connection pool async per PostgreSQL, min 5 / max 20 connessioni |
| Ricerca immagini | Brave Search API | — | Ricerca immagini contestuali con filtri per risoluzione, licenza, tipo |
| Validazione dati | Pydantic v2 | ≥2.7 | Contratti di interfaccia tra tutti i moduli (eccezione: LangGraph state = TypedDict) |
| Logging | structlog | ≥24.1 | Logging JSON strutturato, una riga per evento, parsabile con `jq` |
| Retry | tenacity | ≥8.2 | Exponential backoff per chiamate LLM (429/500/529) e Voyage AI |
| Rate Limiting | slowapi | ≥0.1.9 | Protezione endpoint API contro flood e abuso |
| Memory Monitor | psutil | ≥5.9 | Verifica RAM disponibile prima del build PPTX |
| Middleware | CORSMiddleware | — | Cross-Origin per comunicazione Next.js ↔ FastAPI (origin specifico, MAI wildcard) |
| HTTP Client | httpx | ≥0.27 | Chiamate async verso API esterne (Anthropic, Brave, Voyage) |
| Immagini | Pillow | ≥10.0 | Conversione formato immagini (WebP→PNG) + validazione integrità per compatibilità PPTX |
| PDF Parsing | pdfplumber | ≥0.11 | Estrazione testo strutturato da PDF normativi (migliore di PyMuPDF per metadati) |
| Password Hashing | bcrypt | ≥4.1 | Hashing sicuro password utenti |
| TOTP (v1.1) | pyotp | ≥2.9 | Generazione e verifica codici 2FA — presente in pyproject.toml, non usato in v1.0 |

### 1.2 Stack Frontend

| Componente | Tecnologia | Versione | Ruolo |
|---|---|---|---|
| Framework | Next.js 15 (App Router) | 15.x | Interfaccia web moderna, server components, routing file-based |
| UI Components | shadcn/ui + TailwindCSS 4 | — | Componenti accessibili, coerenti, personalizzabili |
| State Management | TanStack Query + Zustand | — | Cache server-side intelligente + stato client leggero per wizard |

### 1.3 Infrastruttura

| Componente | Tecnologia | Ruolo |
|---|---|---|
| Container | Docker + docker-compose | Build riproducibile, isolamento servizi |
| Web Server | Nginx | Reverse proxy, build statica, CSP headers |
| Hosting | VPS dedicato (datacenter EU) | Single-tenant, 4 vCPU / 8 GB RAM minimo |
| SSL/DNS | Cloudflare / Let's Encrypt | HTTPS automatico, protezione DDoS base |

### 1.4 Decisioni Architetturali Vincolanti

| ID | Decisione | Motivazione |
|---|---|---|
| D-01 | FastAPI, non Django/Flask | Async nativo per WebSocket + concorrenza I/O |
| D-02 | asyncio nativo + semaforo, non Celery/Redis | Sufficiente per 5-15 utenti; `Semaphore(1)` è un **vincolo architetturale** (python-pptx + lxml non sono thread-safe); zero overhead broker. Non alzare MAI a Semaphore(2+) senza passare a process pool o Celery |
| D-03 | PostgreSQL single-instance, non Supabase | Un solo DB per relazionale + vettoriale + checkpoint. Auth custom JWT, nessuna dipendenza cloud |
| D-04 | LangGraph, non catena lineare | Checkpointing automatico, retry per nodo, stato ispezionabile |
| D-05 | python-pptx, non LibreOffice | Controllo programmatico totale su ogni pixel della slide |
| D-06 | WeasyPrint, non wkhtmltopdf | CSS moderno, nessun binario esterno problematico |
| D-07 | Pydantic v2 per tutti i contratti | Schema autoconsistente, validazione a runtime. Eccezione unica: LangGraph state (TypedDict) |
| D-08 | structlog per logging | JSON una riga per evento, grepable e parsabile con `jq` |
| D-09 | pdfplumber, non PyMuPDF | Estrae metadati strutturali migliori (tabelle, box di testo) per il chunking normativo |
| D-10 | tenacity per retry LLM | Exponential backoff gestito dal decoratore, zero boilerplate nei service |
| D-11 | slowapi per rate limiting | Protezione API nativa FastAPI, zero infrastruttura aggiuntiva |
| D-12 | psutil per memory check | Previene OOM durante build PPTX di corsi lunghi (16h, 700 slide) |
| D-13 | Due ruoli PostgreSQL (nexus_app / nexus_admin) | Audit log immutabile a livello SQL, non solo applicativo |
| D-14 | SVG inline generato dall'LLM, non Mermaid.js — con sanitizzazione | Il Content Agent genera SVG direttamente; `sanitize_svg()` rimuove `<script>`, `<foreignObject>`, event handler e URL esterni; cairosvg lo converte in PNG. Elimina la dipendenza da un runtime Mermaid server-side |
| D-15 | Dependency injection via modulo `dependencies.py` | Pool asyncpg, shutdown event e Voyage client accessibili in modo uniforme da agenti LangGraph, service e route. Pattern esplicito, Claude Code-friendly |
| D-16 | Timeout globale pipeline 30 min | `asyncio.wait_for()` wrappa l'intera pipeline; un job bloccato non monopolizza l'istanza indefinitamente |
| D-17 | Diagrammi SVG declassificati a v1.1 nella distribuzione PacingEngine | Gli LLM sono inconsistenti nel generare SVG valido. Il tipo DIAGRAM è presente nel modello (per gestione spontanea dall'LLM) ma escluso dalla distribuzione automatica del PacingEngine. Reintrodurre in v1.1 con template SVG preconfezionati |
| D-18 | Shutdown event condiviso via dependencies.py | Un UNICO `asyncio.Event()` in `dependencies.py`, usato sia da `main.py` che da `generation_service.py`. Nessun evento duplicato tra moduli |
| D-19 | Classificazione chunk ibrida (rule-based + LLM) | Le keyword normative italiane sono sufficientemente predicibili per una classificazione rule-based al 60-70%. Il LLM interviene solo sui casi ambigui, riducendo costi e tempi di ingestion |
| D-20 | Query RAG semantica, non basata su slug | L'embedding della query RAG è costruito da `COURSE_CATALOG["title"] + default_modules`, non da slug/enum. Produce una query in linguaggio naturale con alta similarità coseno rispetto ai chunk normativi |

---

## §02 — DOCKER, DEPLOY & CONNECTION POOL

### 2.1 Dockerfile Backend

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Dipendenze C per WeasyPrint + cairosvg + font per branding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-open-sans \
    unzip \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Montserrat (non nei repo Debian — copia manuale da assets committati in git)
COPY assets/fonts/Montserrat/ /usr/share/fonts/truetype/montserrat/
RUN fc-cache -fv

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> **Nota critica sui font:** WeasyPrint usa i font di sistema. Senza Montserrat e Open Sans installati, il PDF usa fallback generici che rompono il branding. I file `.ttf` di Montserrat (~1.5MB) vanno scaricati da Google Fonts e committati nel repo in `assets/fonts/Montserrat/` per build riproducibili.

### 2.2 docker-compose.yml

```yaml
version: "3.9"

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - output_data:/app/output

  postgres:
    image: pgvector/pgvector:pg16
    # NESSUN port mapping esterno — accessibile solo dalla rete Docker interna
    expose:
      - "5432"
    environment:
      POSTGRES_DB: nexus
      POSTGRES_USER: nexus_admin
      POSTGRES_PASSWORD: ${POSTGRES_ADMIN_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexus_admin"]
      interval: 5s
      timeout: 3s
      retries: 5

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
      - frontend

volumes:
  pg_data:
  output_data:
```

### 2.3 Connection Pool (asyncpg)

```python
# db/connection.py
import asyncpg
from app.config import DATABASE_URL

async def create_pool() -> asyncpg.Pool:
    """Crea il connection pool per PostgreSQL.
    VINCOLI VPS: PostgreSQL single-instance con max_connections=100.
    LangGraph checkpointer usa le sue connessioni, quindi limitare il pool applicativo a 20.
    IMPORTANTE: l'applicazione si connette come nexus_app, NON come nexus_admin."""
    return await asyncpg.create_pool(
        dsn=DATABASE_URL,  # usa nexus_app come ruolo
        min_size=5,
        max_size=20,
        command_timeout=60,
    )
```

### 2.4 Dependency Injection — Pool, Shutdown Event e Voyage Client Accessibili Ovunque

Il pool asyncpg, lo shutdown event e il Voyage AI client devono essere accessibili da agenti LangGraph, service e route API. Pattern esplicito con modulo dedicato — niente variabili globali sparse, niente oggetti duplicati tra moduli.

```python
# services/dependencies.py
"""Dependency injection per risorse condivise.
Il pool e il Voyage client vengono inizializzati una volta in main.py startup(),
lo shutdown event è creato qui e condiviso tra main.py e generation_service.py.
Ogni risorsa è accessibile da qualsiasi modulo tramite le funzioni get_*()."""

import asyncio
import asyncpg
import voyageai

_pool: asyncpg.Pool | None = None
_voyage_client: voyageai.AsyncClient | None = None
_shutdown_event = asyncio.Event()


def set_pool(pool: asyncpg.Pool) -> None:
    """Chiamato UNA volta in main.py startup(). Non chiamare altrove."""
    global _pool
    _pool = pool


def get_pool() -> asyncpg.Pool:
    """Restituisce il pool. Alza RuntimeError se non inizializzato.
    Usato da: agenti LangGraph, service, route API."""
    if _pool is None:
        raise RuntimeError(
            "Pool non inizializzato — set_pool() non è stato chiamato in startup()"
        )
    return _pool


def set_voyage_client(client: voyageai.AsyncClient) -> None:
    """Chiamato UNA volta in main.py startup(). Non chiamare altrove."""
    global _voyage_client
    _voyage_client = client


def get_voyage_client() -> voyageai.AsyncClient:
    """Restituisce il Voyage AI client. Alza RuntimeError se non inizializzato.
    Usato da: ingestion_service, research_agent."""
    if _voyage_client is None:
        raise RuntimeError(
            "Voyage client non inizializzato — set_voyage_client() non è stato chiamato in startup()"
        )
    return _voyage_client


def get_shutdown_event() -> asyncio.Event:
    """Restituisce lo shutdown event CONDIVISO.
    ═══ VINCOLO ARCHITETTURALE ═══
    Questo è l'UNICO shutdown event dell'intero progetto.
    main.py lo setta in shutdown(), generation_service.py lo legge in _run_pipeline_inner().
    NON creare altri asyncio.Event() per shutdown in nessun altro modulo."""
    return _shutdown_event
```

### 2.5 Entry Point (main.py)

```python
# app/main.py
import asyncio
import shutil
import os
import structlog
import voyageai
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.connection import create_pool
from services.dependencies import set_pool, set_voyage_client, get_shutdown_event
from services.generation_service import recover_interrupted_jobs
from app.config import FRONTEND_URL, configure_logging

logger = structlog.get_logger()

app = FastAPI(title="Nexus EduVault API", version="6.0")

# ═══ RATE LIMITING ═══
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# ═══ CORS — ORIGIN SPECIFICO, MAI WILDCARD ═══
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],  # es. "https://corsi8108.it"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ═══ NESSUN _shutdown_event LOCALE ═══
# Lo shutdown event è in services/dependencies.py — get_shutdown_event()
# NON creare asyncio.Event() qui. È un vincolo architetturale (D-18).

@app.on_event("startup")
async def startup():
    configure_logging()
    pool = await create_pool()
    app.state.db = pool
    set_pool(pool)  # ← rende il pool accessibile a tutti i moduli via get_pool()
    set_voyage_client(voyageai.AsyncClient(api_key=os.environ["VOYAGE_API_KEY"]))
    await recover_interrupted_jobs(pool)
    logger.info("nexus_started", version="6.0")

@app.on_event("shutdown")
async def shutdown():
    """Graceful shutdown: segnala ai job in corso di fermarsi,
    aspetta max 30 secondi, poi chiude il pool.
    ═══ USA LO SHUTDOWN EVENT CONDIVISO DA dependencies.py ═══"""
    from services.generation_service import _job_semaphore
    get_shutdown_event().set()  # ← segnala alla pipeline di fermarsi
    try:
        await asyncio.wait_for(_job_semaphore.acquire(), timeout=30)
    except asyncio.TimeoutError:
        logger.warning("shutdown_timeout", msg="Job in corso non terminato entro 30s")
    await app.state.db.close()
    logger.info("nexus_shutdown")
```

### 2.6 Variabili d'ambiente (.env.example)

```bash
# ═══ DATABASE ═══
# L'applicazione si connette come nexus_app (senza permessi DELETE/UPDATE su audit_log)
DATABASE_URL=postgresql://nexus_app:${POSTGRES_APP_PASSWORD}@postgres:5432/nexus
# URL admin per seed.py e migration — usa nexus_admin
DATABASE_ADMIN_URL=postgresql://nexus_admin:${POSTGRES_ADMIN_PASSWORD}@postgres:5432/nexus
POSTGRES_ADMIN_PASSWORD=CHANGE_ME_ADMIN_64_CHARS
POSTGRES_APP_PASSWORD=CHANGE_ME_APP_64_CHARS

# ═══ API KEYS ═══
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
BRAVE_API_KEY=BSA...

# ═══ AUTH ═══
JWT_SECRET=CHANGE_ME_RANDOM_64_CHARS
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
JWT_REFRESH_EXPIRY_DAYS=7

# ═══ CORS ═══
FRONTEND_URL=https://corsi8108.it

# ═══ BRANDING ═══
ORGANIZATION_NAME=corsi8108

# ═══ PIPELINE ═══
PIPELINE_TIMEOUT=1800
```

### 2.7 Script di Seeding (primo avvio)

```python
# scripts/seed.py
"""Crea l'utente admin iniziale e il brand preset di default.
Eseguire DOPO il primo docker-compose up e la migration.
Usa DATABASE_ADMIN_URL (nexus_admin) per avere permessi completi."""

import asyncio
import asyncpg
import bcrypt
import os

async def seed():
    pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_ADMIN_URL"])

    # Admin
    admin = await pool.fetchrow("SELECT id FROM users WHERE role='admin'")
    if not admin:
        pw_hash = bcrypt.hashpw(b"CHANGE_ME", bcrypt.gensalt()).decode()
        await pool.execute(
            "INSERT INTO users (email, password_hash, role) VALUES ($1, $2, 'admin')",
            "admin@corsi8108.it", pw_hash
        )
        print("✓ Admin creato: admin@corsi8108.it / CHANGE_ME")

    # Brand preset di default
    preset = await pool.fetchrow("SELECT id FROM brand_presets WHERE is_default=true")
    if not preset:
        await pool.execute(
            "INSERT INTO brand_presets (name, palette, fonts, is_default) VALUES ($1, $2, $3, true)",
            "Default",
            '{"primary": "#1a365d", "secondary": "#2b6cb0", "accent": "#ed8936", "danger": "#e53e3e", "success": "#38a169"}',
            '{"heading": "Montserrat", "body": "Open Sans"}'
        )
        print("✓ Brand preset di default creato")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(seed())
```

---

## §03 — DATABASE SCHEMA

### 3.1 Schema SQL Completo

```sql
-- ═══════════════════════════════════════════════
-- NEXUS EDUVAULT — Schema v7.0 Supreme Production
-- PostgreSQL 16 + pgvector
-- DUE RUOLI: nexus_admin (owner) + nexus_app (applicazione)
-- ═══════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ────────────────────────────────────────────
-- RUOLI PostgreSQL
-- nexus_admin: owner del database, usato per maintenance e seed
-- nexus_app: usato dall'applicazione, SENZA permessi destructivi su audit_log
-- ────────────────────────────────────────────
-- NOTA: nexus_admin è creato dal docker-compose (POSTGRES_USER).
-- nexus_app va creato manualmente dopo il primo avvio:
--   CREATE ROLE nexus_app LOGIN PASSWORD 'CHANGE_ME_APP_64_CHARS';
--   GRANT CONNECT ON DATABASE nexus TO nexus_app;
--   GRANT USAGE ON SCHEMA public TO nexus_app;
--   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nexus_app;
--   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app;
--   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nexus_app;
--   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO nexus_app;
--   REVOKE DELETE, UPDATE, TRUNCATE ON audit_log FROM nexus_app;

-- ────────────────────────────────────────────
-- TRIGGER: aggiornamento automatico di updated_at
-- ────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ────────────────────────────────────────────
-- UTENTI E AUTENTICAZIONE
-- totp_secret: predisposto per v1.1 (non usato in v1.0)
-- ────────────────────────────────────────────
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'operator', 'reviewer')),
    totp_secret VARCHAR(64),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ────────────────────────────────────────────
-- PRESET BRANDING (PRIMA di courses — courses ha FK verso brand_presets)
-- ────────────────────────────────────────────
CREATE TABLE brand_presets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    logo_path VARCHAR(500),
    logo_light_path VARCHAR(500),
    palette JSONB NOT NULL,
    fonts JSONB NOT NULL,
    footer_template VARCHAR(500),
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TRIGGER trg_brand_presets_updated BEFORE UPDATE ON brand_presets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ────────────────────────────────────────────
-- NORMATIVE (Livello 1 — Source of Truth)
-- ────────────────────────────────────────────
CREATE TABLE regulations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    type VARCHAR(50) NOT NULL,
    issuing_body VARCHAR(200),
    issue_date DATE,
    effective_date DATE,
    region VARCHAR(50) DEFAULT 'NAZIONALE',
    status VARCHAR(20) NOT NULL DEFAULT 'VIGENTE'
        CHECK (status IN ('VIGENTE', 'ABROGATA', 'MODIFICATA')),
    slug VARCHAR(50) UNIQUE,
    source_url VARCHAR(500),
    full_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_regulations_status ON regulations(status);
CREATE INDEX idx_regulations_region ON regulations(region);
CREATE INDEX idx_regulations_slug ON regulations(slug);
CREATE TRIGGER trg_regulations_updated BEFORE UPDATE ON regulations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ────────────────────────────────────────────
-- CHUNKS NORMATIVI
-- content_hash: UNIQUE parziale per deduplicare chunk attivi
-- ────────────────────────────────────────────
CREATE TABLE regulation_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    regulation_id UUID NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
    article VARCHAR(50),
    paragraph VARCHAR(50),
    hierarchy_path VARCHAR(500),
    body TEXT NOT NULL,
    chunk_type VARCHAR(30) NOT NULL
        CHECK (chunk_type IN ('OBBLIGO', 'SANZIONE', 'DEFINIZIONE', 'PROCEDURA', 'GENERALE')),
    tags TEXT[] DEFAULT '{}',
    embedding VECTOR(1024),
    content_hash VARCHAR(64),
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_chunks_regulation ON regulation_chunks(regulation_id);
CREATE INDEX idx_chunks_type ON regulation_chunks(chunk_type);
CREATE INDEX idx_chunks_tags ON regulation_chunks USING GIN(tags);
CREATE INDEX idx_chunks_embedding ON regulation_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE UNIQUE INDEX idx_chunks_content_hash ON regulation_chunks(content_hash)
    WHERE is_current = true;

-- ────────────────────────────────────────────
-- CORSI
-- regulation_snapshot: non presente in v1.0 (si ricostruisce con JOIN).
-- source_chunk_ids: indicizzato con GIN per future query Delta-Update.
-- ────────────────────────────────────────────
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    course_type VARCHAR(100) NOT NULL,
    target VARCHAR(20) NOT NULL CHECK (target IN ('discente', 'formatore')),
    duration_hours DECIMAL(4,1) NOT NULL,
    region VARCHAR(50) DEFAULT 'NAZIONALE',
    brand_preset_id UUID REFERENCES brand_presets(id),
    created_by UUID NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'generating'
        CHECK (status IN ('generating', 'completed', 'reviewed', 'certified', 'failed', 'archived')),
    pptx_path VARCHAR(500),
    pdf_path VARCHAR(500),
    quiz_json JSONB,
    slide_contents_json JSONB,
    normative_fingerprint JSONB,
    source_chunk_ids TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_courses_status ON courses(status);
CREATE INDEX idx_courses_type ON courses(course_type);
CREATE INDEX idx_courses_created_by ON courses(created_by);
CREATE INDEX idx_courses_chunk_ids ON courses USING GIN(source_chunk_ids);
CREATE TRIGGER trg_courses_updated BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ────────────────────────────────────────────
-- CORSI APPROVATI (Livello 2 — Apprendimento Stilistico)
-- Il decadimento temporale si ottiene con ORDER BY certified_at DESC.
-- style_pattern contiene SOLO metadati strutturali (MAI testo normativo).
-- ────────────────────────────────────────────
CREATE TABLE approved_courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_type VARCHAR(100) NOT NULL,
    target VARCHAR(20) NOT NULL,
    style_pattern JSONB NOT NULL,
    certified_by UUID REFERENCES users(id),
    source_course_id UUID REFERENCES courses(id),
    certified_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_approved_type_target ON approved_courses(course_type, target);

-- ────────────────────────────────────────────
-- JOB DI GENERAZIONE
-- ────────────────────────────────────────────
CREATE TABLE generation_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id),
    status VARCHAR(20) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'research', 'content', 'building', 'completed', 'failed', 'cancelled')),
    progress_percent INT DEFAULT 0,
    current_step VARCHAR(100),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_jobs_status ON generation_jobs(status);
CREATE INDEX idx_jobs_course ON generation_jobs(course_id);

-- ────────────────────────────────────────────
-- CACHE IMMAGINI
-- ────────────────────────────────────────────
CREATE TABLE image_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query VARCHAR(500) NOT NULL,
    image_url VARCHAR(1000),
    local_path VARCHAR(500),
    license_type VARCHAR(50),
    format VARCHAR(10),
    usage_count INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_images_query ON image_cache(query);

-- ────────────────────────────────────────────
-- AUDIT LOG (append-only — IMMUTABILE)
-- nexus_app NON può fare DELETE, UPDATE o TRUNCATE su questa tabella.
-- Solo INSERT e SELECT sono consentiti.
-- Usato anche per metriche pipeline (action='pipeline_metrics').
-- ────────────────────────────────────────────
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_created ON audit_log(created_at);

-- ═══ BLINDATURA AUDIT LOG ═══
-- Eseguire DOPO la creazione del ruolo nexus_app:
-- REVOKE DELETE, UPDATE, TRUNCATE ON audit_log FROM nexus_app;
-- Questo rende l'audit log tecnicamente immutabile per l'applicazione.
-- Solo nexus_admin (usato per maintenance) può modificare audit_log.

-- ────────────────────────────────────────────
-- TABELLE GESTITE DA LANGGRAPH (NON MODIFICARE MANUALMENTE)
-- checkpoints, checkpoint_writes, checkpoint_migrations
-- Gestite dal framework. Se scompaiono, LangGraph le ricrea all'avvio.
-- ────────────────────────────────────────────
```

### 3.2 Script di Setup Ruoli (post primo avvio)

```sql
-- scripts/setup_roles.sql
-- Eseguire UNA VOLTA dopo il primo docker-compose up, connessi come nexus_admin.

CREATE ROLE nexus_app LOGIN PASSWORD 'CHANGE_ME_APP_64_CHARS';
GRANT CONNECT ON DATABASE nexus TO nexus_app;
GRANT USAGE ON SCHEMA public TO nexus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nexus_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nexus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO nexus_app;

-- ═══ BLINDATURA AUDIT LOG ═══
REVOKE DELETE, UPDATE, TRUNCATE ON audit_log FROM nexus_app;

-- ═══ GRANT PER TABELLE LANGGRAPH ═══
-- LangGraph crea le proprie tabelle al primo avvio del backend.
-- Eseguire QUESTA sezione DOPO il primo avvio del backend (Sprint 3).
-- Se eseguita prima che le tabelle esistano, PostgreSQL darà errore —
-- in quel caso, rieseguire dopo il primo avvio.
-- GRANT SELECT, INSERT, UPDATE, DELETE ON checkpoints, checkpoint_writes, checkpoint_migrations TO nexus_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app;
```

---

## §04 — CONTRATTI PYDANTIC — SPECIFICA COMPLETA

Tutti i contratti di interfaccia tra moduli usano Pydantic BaseModel v2. Ogni modello è definito qui. Claude Code NON deve inventare campi o strutture: deve copiare questi modelli esattamente.

**Eccezione unica:** `NexusPipelineState` in `agents/pipeline.py` è l'UNICO TypedDict del progetto (richiesto da LangGraph). Tutti gli altri contratti usano Pydantic.

### 4.1 Modelli Core

```python
# models/core.py
from pydantic import BaseModel, Field
from enum import Enum


class TargetType(str, Enum):
    DISCENTE = "discente"
    FORMATORE = "formatore"


class SlideDensity(str, Enum):
    LEGGERA = "leggera"
    STANDARD = "standard"
    INTENSIVA = "intensiva"


class SlideType(str, Enum):
    TITLE = "TITLE"
    CONTENT_TEXT = "CONTENT_TEXT"
    CONTENT_IMAGE = "CONTENT_IMAGE"
    DIAGRAM = "DIAGRAM"
    QUIZ = "QUIZ"
    CASE_STUDY = "CASE_STUDY"
    RECAP = "RECAP"
    CLOSING = "CLOSING"


class ChunkType(str, Enum):
    OBBLIGO = "OBBLIGO"
    SANZIONE = "SANZIONE"
    DEFINIZIONE = "DEFINIZIONE"
    PROCEDURA = "PROCEDURA"
    GENERALE = "GENERALE"
```

### 4.2 Modelli Request/Response

```python
# models/requests.py
from pydantic import BaseModel, Field
from models.core import TargetType, SlideDensity


class CourseRequest(BaseModel):
    """Input dal wizard. Tutti i campi obbligatori per avviare la pipeline."""
    course_type: str = Field(..., description="Slug del tipo corso da COURSE_CATALOG, es. 'sicurezza_lavoratori_generale'")
    target: TargetType
    duration_hours: float = Field(..., gt=0, le=16)
    region: str = Field(default="NAZIONALE")
    brand_preset_id: str
    slide_density: SlideDensity = SlideDensity.STANDARD
    outputs: list[str] = Field(default=["pptx", "pdf"], description="Formati richiesti: pptx, pdf, quiz")


class CourseResponse(BaseModel):
    """Risposta alla creazione di un corso.
    queue_position: 0 = in esecuzione subito, 1+ = in coda."""
    course_id: str
    job_id: str
    estimated_slides: int
    estimated_minutes: float
    queue_position: int = 0
```

### 4.3 Modelli Knowledge Base

```python
# models/knowledge.py
from pydantic import BaseModel, Field
from models.core import ChunkType


class NormativeChunk(BaseModel):
    """Unità atomica di conoscenza legislativa recuperata dal RAG."""
    chunk_id: str
    regulation_id: str
    article: str | None = None
    paragraph: str | None = None
    hierarchy_path: str
    body: str
    chunk_type: ChunkType
    tags: list[str] = []
    relevance_score: float | None = None


class StylePattern(BaseModel):
    """Pattern stilistico estratto dal Livello 2 (corsi approvati).
    CONTIENE SOLO METADATI STRUTTURALI. Mai frasi intere, mai formulazioni
    normative, mai blocchi di testo. Questo previene il loop di
    auto-avvelenamento (Model Collapse) del Livello 2."""
    avg_words_per_slide: int
    preferred_slide_sequence: list[str]  # es. ["CONTENT_TEXT", "CONTENT_IMAGE", "QUIZ", "RECAP"]
    tone_register: str  # "tecnico-divulgativo" | "formale" | "accessibile"
    recurring_section_titles: list[str]  # es. ["Introduzione", "Obblighi del datore", "Riepilogo"]
    avg_quiz_per_module: float
    preferred_image_ratio: float  # % di slide con immagine, es. 0.20

    # ═══ VINCOLO ANTI-AVVELENAMENTO ═══
    # Questo modello NON contiene mai:
    # - Frasi intere da corsi precedenti
    # - Formulazioni normative testuali
    # - Blocchi di testo di qualsiasi tipo
    # Se un futuro sviluppatore aggiunge campi testuali qui,
    # sta rompendo la barriera anti-Model-Collapse.
```

### 4.4 Modelli Pipeline

```python
# models/pipeline.py
from pydantic import BaseModel, Field, field_validator
from models.core import SlideType
from models.knowledge import NormativeChunk, StylePattern


class ImageStrategy(BaseModel):
    """Strategia per il supporto visivo di una slide.
    diagram_code: SVG inline (NON Mermaid). Generato direttamente dall'LLM."""
    strategy: str = "none"  # "none" | "web_search" | "diagram"
    query: str | None = None
    query_url: str | None = None
    diagram_code: str | None = None  # codice SVG inline (rettangoli + frecce + testo)


class SlideContent(BaseModel):
    """Contenuto di una singola slide generato dal Content Agent."""
    index: int
    module_index: int
    slide_type: SlideType
    title: str = Field(..., max_length=80)
    body: str
    speaker_notes: str = ""
    normative_ref: str = ""
    source_chunk_ids: list[str] = []
    image: ImageStrategy = Field(default_factory=lambda: ImageStrategy(strategy="none"))
    quiz_options: list[str] | None = None
    quiz_correct: int | None = None

    @field_validator("body")
    @classmethod
    def validate_body_length(cls, v, info):
        """Soft validator: TRONCA il body se supera il limite per tipo slide.
        Il troncamento viene loggato e il warning esportato nel GenerationReport.
        Questo previene il testo che sborda dai placeholder PPTX."""
        limits = {
            "CONTENT_TEXT": 90, "CONTENT_IMAGE": 60, "QUIZ": 60,
            "CASE_STUDY": 100, "DIAGRAM": 50, "RECAP": 70,
        }
        slide_type = info.data.get("slide_type", "")
        max_words = limits.get(str(slide_type), 100)
        words = v.split()
        if len(words) > max_words:
            import structlog
            structlog.get_logger().warning(
                "slide_body_truncated",
                slide_index=info.data.get("index"),
                original_words=len(words),
                max_words=max_words
            )
            return ' '.join(words[:max_words]) + '…'
        return v


class ModuleSpec(BaseModel):
    """Specifica di un modulo nel piano di pacing."""
    module_index: int
    title: str
    slide_count: int
    slide_distribution: dict[str, int]  # es. {"CONTENT_TEXT": 10, "QUIZ": 2, "RECAP": 1}


class PacingPlan(BaseModel):
    """Piano di distribuzione slide calcolato dal PacingEngine."""
    total_slides: int
    modules: list[ModuleSpec]


class ModuleContent(BaseModel):
    """Output del Content Agent per un singolo modulo."""
    module_index: int
    title: str
    slides: list[SlideContent]


class CourseContext(BaseModel):
    """Contesto completo prodotto dal Research Agent per il Content Agent."""
    chunks: list[NormativeChunk]
    chunks_by_module: dict[int, list[NormativeChunk]]
    pacing_plan: PacingPlan
    style_patterns: list[StylePattern]
    regulation_ids: list[str]
    regulation_slugs: list[str]


class GenerationReport(BaseModel):
    """Report finale della generazione."""
    total_slides: int
    slides_with_images: int
    slides_with_diagrams: int
    quiz_count: int
    modules_completed: int
    modules_failed: int
    normative_refs_count: int
    warnings: list[str] = []
    truncation_warnings: list[str] = []  # slide troncate dal body validator — visibili all'operatore
    generation_time_seconds: float
```

---

## §05 — ARCHITETTURA AGENTICA & CONTRATTI DI STATO

### 5.1 Pipeline — 2 Agenti LangGraph + 1 Production Builder Deterministico

```
═══ LANGGRAPH STATE MACHINE (2 nodi) ═══
Wizard → Research Agent → Content Agent → [salva slide_contents_json nel DB]
              §05.4            §05.5
           Ricerca RAG     Generazione
           Piano Pacing    Modulo×Modulo
           Gate min chunk  Retry JSON+LLM
           Chunk distrib.  Circuit breaker
           (keyword-based) 50% fail → abort

═══ POST-PIPELINE (funzione Python, NON nodo LangGraph) ═══
[Image Pre-Fetch] → Production Builder → Output
     §07.0               §07.1
  Download async       Build PPTX/PDF
  (Brave + Pillow)     (sincrono in thread)
  Semaphore(5)         Memory check
  SVG→PNG (cairosvg)   Disk check
```

**Chiarimento architetturale:** Il grafo LangGraph contiene SOLO 2 nodi: `research` e `content`. Il Production Builder è una funzione Python pura chiamata DOPO che LangGraph ha completato con successo. Se il builder fallisce, i contenuti LLM sono già salvati nel DB (`slide_contents_json`) e il build si può ritentare senza costo API.

**Guardrail Pipeline:** L'intera esecuzione è wrappata in `asyncio.wait_for(timeout=1800)` — se la pipeline non completa entro 30 minuti, il job passa a `failed` e il semaforo viene rilasciato.

### 5.2 State LangGraph — L'UNICO TypedDict del Progetto

```python
# agents/pipeline.py
import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

class NexusPipelineState(TypedDict):
    """ATTENZIONE: Questo è l'UNICO TypedDict dell'intero progetto.
    LangGraph richiede TypedDict — non supporta Pydantic BaseModel per lo state.
    NON usare TypedDict in nessun altro file.

    I campi sono dict perché LangGraph serializza in JSON.
    La validazione Pydantic avviene all'INGRESSO e all'USCITA di ogni nodo
    tramite CourseRequest(**state["course_request"]), CourseContext(**state["course_context"]), ecc.
    Questo garantisce type safety senza violare i vincoli di LangGraph."""

    # Input (validato con CourseRequest, BrandConfig)
    course_request: dict
    brand_config: dict

    # Research Agent output (validato con CourseContext, PacingPlan)
    course_context: dict | None
    pacing_plan: dict | None

    # Content Agent output
    # operator.add è il REDUCER: quando il Content Agent restituisce
    # completed_modules: [new_module], LangGraph lo APPENDE alla lista
    # esistente invece di sovrascriverla.
    completed_modules: Annotated[list[dict], operator.add]
    current_module_index: int

    # ═══ NOTA: pptx_path, pdf_path e generation_report NON sono nello state ═══
    # Il Production Builder è una funzione post-pipeline, non un nodo LangGraph.
    # I path dei file vengono salvati direttamente nel DB da _run_pipeline_inner()
    # in §09.1, non dallo state del grafo. Se questi campi fossero qui,
    # Claude Code potrebbe creare un terzo nodo "production" per popolarli.

    # Metadata
    job_id: str
    errors: Annotated[list[str], operator.add]
```

### 5.3 Costruzione del Grafo

```python
# agents/pipeline.py (continua)

async def create_pipeline(database_url: str) -> StateGraph:
    """Crea il grafo LangGraph con checkpointing PostgreSQL."""
    checkpointer = AsyncPostgresSaver.from_conn_string(database_url)

    graph = StateGraph(NexusPipelineState)
    graph.add_node("research", research_agent)
    graph.add_node("content", content_agent)

    graph.set_entry_point("research")
    graph.add_edge("research", "content")
    graph.set_finish_point("content")

    return graph.compile(checkpointer=checkpointer)
```

### 5.4 Research Agent — Con Gate RAG, top_k Dinamico e Distribuzione Chunk

```python
# agents/research_agent.py
import structlog
from models.requests import CourseRequest
from models.pipeline import CourseContext, PacingPlan
from models.knowledge import NormativeChunk, StylePattern
from services.dependencies import get_pool
from services.knowledge_repo import KnowledgeRepository
from services.pacing_engine import PacingEngine
from services.ingestion_service import voyage_embed_with_retry
from config.catalog_config import COURSE_CATALOG

logger = structlog.get_logger()


def _keyword_overlap(title: str, body: str) -> int:
    """Conta le keyword condivise tra titolo modulo e corpo chunk.
    Per normative italiane strutturate è sufficiente: 'DPI' apparirà
    nel corpo dei chunk che parlano di DPI, 'antincendio' in quelli
    relativi all'antincendio, ecc. Zero costo API — nessun embedding."""
    title_words = set(title.lower().split())
    body_words = set(body.lower().split())
    return len(title_words & body_words)


def _rebalance_min(
    result: dict[int, list],
    min_per_module: int = 3
) -> None:
    """Garantisce almeno min_per_module chunk per modulo.
    Redistribuisce dai moduli sovrappopolati a quelli sottopopolati."""
    while True:
        under = [k for k, v in result.items() if len(v) < min_per_module]
        over = [k for k, v in result.items() if len(v) > min_per_module + 2]
        if not under or not over:
            break
        donor = max(over, key=lambda k: len(result[k]))
        receiver = min(under, key=lambda k: len(result[k]))
        result[receiver].append(result[donor].pop())


def _rebalance_max(
    result: dict[int, list],
    max_per_module: int
) -> None:
    """Redistribuisce chunk in eccesso ai moduli meno popolati.
    Previene la degenerazione del keyword overlap quando titoli generici
    (es. 'Concetti di rischio') attraggono TUTTI i chunk perché
    la parola 'rischio' è ubiqua nelle normative sulla sicurezza."""
    while True:
        over = [k for k, v in result.items() if len(v) > max_per_module]
        under = [k for k, v in result.items() if len(v) < max_per_module]
        if not over or not under:
            break
        donor = max(over, key=lambda k: len(result[k]))
        receiver = min(under, key=lambda k: len(result[k]))
        result[receiver].append(result[donor].pop())


def distribute_chunks_to_modules(
    chunks: list[NormativeChunk],
    pacing_plan: PacingPlan
) -> dict[int, list[NormativeChunk]]:
    """Distribuisce i chunk ai moduli basandosi sulla similarità semantica
    tra il titolo del modulo (dal COURSE_CATALOG) e il contenuto del chunk.
    Fallback a round-robin se i chunk sono troppo pochi per una distribuzione significativa.
    Garantisce almeno 3 chunk per modulo via ribilanciamento post-assegnazione."""
    result = {m.module_index: [] for m in pacing_plan.modules}

    if len(chunks) < len(pacing_plan.modules) * 3:
        # Troppo pochi chunk per distribuzione semantica → round-robin
        module_indices = [m.module_index for m in pacing_plan.modules]
        for i, chunk in enumerate(chunks):
            target = module_indices[i % len(module_indices)]
            result[target].append(chunk)
        return result

    # Assegna ogni chunk al modulo con titolo più simile (keyword overlap)
    for chunk in chunks:
        best_module = max(
            pacing_plan.modules,
            key=lambda m: _keyword_overlap(m.title, chunk.body)
        )
        result[best_module.module_index].append(chunk)

    # Garantisci almeno 3 chunk per modulo
    _rebalance_min(result, min_per_module=3)

    # Previeni sovrappopolazione da keyword overlap su titoli generici
    avg_per_module = len(chunks) // max(len(pacing_plan.modules), 1)
    _rebalance_max(result, max_per_module=avg_per_module + 5)

    return result


async def research_agent(state: NexusPipelineState) -> dict:
    """Ricerca RAG + pacing + distribuzione chunk per modulo.
    Validazione Pydantic all'ingresso e all'uscita.
    Il pool è recuperato via dependencies.get_pool()."""

    # ═══ VALIDAZIONE INPUT ═══
    request = CourseRequest(**state["course_request"])
    pool = get_pool()
    knowledge_repo = KnowledgeRepository(pool)

    # 1. Risolvi slug → UUID (con validazione che alza errore se mancano slug)
    catalog_entry = COURSE_CATALOG[request.course_type]
    regulation_slugs = catalog_entry["regs"]
    regulation_ids = await knowledge_repo.resolve_slugs_to_ids(regulation_slugs)

    # ═══ VALIDAZIONE REGIONALE ═══
    # I corsi con flag "regional": True nel COURSE_CATALOG (es. HACCP)
    # RICHIEDONO una regione specifica (non "NAZIONALE").
    # CourseRequest.region ha default "NAZIONALE" — non è mai None.
    # Un corso HACCP con region="NAZIONALE" produrrebbe solo chunk nazionali
    # senza le DGR regionali, rendendo il corso incompleto.
    if catalog_entry.get("regional") and request.region == "NAZIONALE":
        raise ValueError(
            f"Il tipo corso '{request.course_type}' richiede la specifica della regione "
            f"(es. 'LAZIO', 'LOMBARDIA'). Il valore 'NAZIONALE' non è valido per corsi regionali. "
            f"Selezionare una regione nel wizard prima di generare."
        )

    # 2. Genera embedding della query — SEMANTICA, non slug
    # ═══ VINCOLO ARCHITETTURALE (D-20) ═══
    # La query RAG è costruita dal COURSE_CATALOG usando il titolo e i moduli
    # in linguaggio naturale, NON da slug/enum. Questo produce embedding con
    # alta similarità coseno rispetto ai chunk normativi reali.
    query_parts = [catalog_entry["title"]] + catalog_entry.get("default_modules", [])
    query = " ".join(query_parts)
    # Es: "Formazione Generale Lavoratori Concetti di rischio Prevenzione e protezione
    #       Organizzazione della prevenzione Diritti e doveri"
    query_embedding = await voyage_embed_with_retry(query)

    # 3. Ricerca RAG filtrata — top_k DINAMICO in base alla durata
    top_k = max(30, int(request.duration_hours * 10))  # 30 per 1h, 80 per 8h
    chunks = await knowledge_repo.search_chunks(
        query_embedding=query_embedding,
        regulation_ids=regulation_ids,
        region=request.region,
        top_k=top_k
    )

    # ═══ GATE RAG: se troppo pochi chunk, la pipeline si ferma ═══
    if len(chunks) < 5:
        raise ValueError(
            f"RAG insufficiente: solo {len(chunks)} chunk trovati per "
            f"{regulation_slugs}. Verificare che l'ingestion sia stata "
            f"completata correttamente per queste normative."
        )

    # ═══ FILTRO RILEVANZA: rimuovi chunk con similarità troppo bassa ═══
    MIN_RELEVANCE = 0.3
    chunks = [c for c in chunks if c.relevance_score and c.relevance_score > MIN_RELEVANCE]

    if len(chunks) < 5:
        raise ValueError(
            f"RAG post-filtro insufficiente: solo {len(chunks)} chunk con "
            f"rilevanza > {MIN_RELEVANCE}. Verificare la qualità degli embedding."
        )

    # 4. Pre-raggruppa chunk per modulo — con titoli semantici dal COURSE_CATALOG
    module_titles = catalog_entry.get("default_modules")
    pacing_plan = PacingEngine().calculate(
        request.duration_hours, request.slide_density, module_titles=module_titles
    )
    chunks_by_module = distribute_chunks_to_modules(chunks, pacing_plan)

    # 5. Recupera pattern stilistici dal Livello 2
    style_patterns = await knowledge_repo.get_style_patterns(
        course_type=request.course_type,
        target=request.target.value
    )

    # ═══ VALIDAZIONE OUTPUT ═══
    context = CourseContext(
        chunks=chunks,
        chunks_by_module=chunks_by_module,
        pacing_plan=pacing_plan,
        style_patterns=style_patterns,
        regulation_ids=regulation_ids,
        regulation_slugs=regulation_slugs
    )

    logger.info("research_completed",
                chunks=len(chunks), top_k=top_k,
                modules=len(pacing_plan.modules),
                style_patterns=len(style_patterns))

    return {
        "course_context": context.model_dump(),
        "pacing_plan": pacing_plan.model_dump()
    }
```

### 5.5 Content Agent — Con Retry LLM, JSON Parsing e Circuit Breaker

```python
# agents/content_agent.py
import json
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import anthropic

from models.requests import CourseRequest
from models.pipeline import CourseContext, PacingPlan, SlideContent, ModuleContent
from agents.prompts import build_content_system_prompt, build_module_prompt, build_previous_summary

logger = structlog.get_logger()


# ═══ RETRY PER ERRORI LLM (429 rate limit, 500 server error, 529 overloaded) ═══
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    retry=retry_if_exception_type((
        anthropic.RateLimitError,
        anthropic.InternalServerError,
        anthropic.APIStatusError,
    ))
)
async def call_llm(messages: list, system: str) -> str:
    """Chiamata LLM con retry automatico. Timeout: 120 secondi.
    NOTA: il client viene creato dentro la funzione, MAI come globale."""
    client = anthropic.AsyncAnthropic(timeout=120.0)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=system,
        messages=messages
    )
    return response.content[0].text


def parse_slides_json(raw: str) -> list[dict] | None:
    """Parsing JSON robusto con pulizia del testo prima del parse."""
    text = raw.strip()
    # Rimuovi eventuale ```json ... ``` wrapper
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return None
    except json.JSONDecodeError:
        return None


async def content_agent(state: NexusPipelineState) -> dict:
    """Genera contenuto testuale modulo per modulo.
    Validazione Pydantic all'ingresso e all'uscita.
    CIRCUIT BREAKER: se >50% dei moduli fallisce, interrompe con errore."""

    # ═══ VALIDAZIONE INPUT ═══
    context = CourseContext(**state["course_context"])
    pacing = PacingPlan(**state["pacing_plan"])
    request = CourseRequest(**state["course_request"])

    completed = []
    failed_count = 0
    start_index = state.get("current_module_index", 0)

    for module in pacing.modules[start_index:]:
        # Chunk già raggruppati dal Research Agent
        module_chunks = context.chunks_by_module.get(module.module_index, [])

        # Riassunto moduli precedenti (titoli + key points, non testo intero)
        previous_summary = build_previous_summary(
            state.get("completed_modules", []) + completed
        )

        # Seleziona prompt-chain in base al target
        system_prompt = build_content_system_prompt(request.target)
        user_prompt = build_module_prompt(
            module=module,
            chunks=module_chunks,
            style_patterns=context.style_patterns,
            previous_summary=previous_summary,
            target=request.target
        )

        # Chiamata LLM con retry (max 3 tentativi per errori API)
        try:
            raw_response = await call_llm(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt
            )
        except Exception as e:
            logger.error("module_llm_failed", module_index=module.module_index, error=str(e))
            failed_count += 1
            continue

        # Parsing JSON con retry correttivo (max 2 tentativi per JSON malformato)
        slides = parse_slides_json(raw_response)
        if slides is None:
            correction_prompt = (
                f"Il tuo output precedente non era JSON valido. "
                f"Riscrivi SOLO l'array JSON di slide, senza testo aggiuntivo.\n\n"
                f"Output precedente (non valido):\n{raw_response[:2000]}"
            )
            try:
                raw_response = await call_llm(
                    messages=[{"role": "user", "content": correction_prompt}],
                    system=system_prompt
                )
                slides = parse_slides_json(raw_response)
            except Exception:
                slides = None

        if slides is None:
            logger.error("module_json_failed", module_index=module.module_index)
            failed_count += 1
            continue  # salta il modulo, procedi col successivo

        # ═══ VALIDAZIONE OUTPUT ═══
        validated_slides = []
        for s in slides:
            try:
                validated_slides.append(SlideContent(**s).model_dump())
            except Exception as e:
                logger.warning("slide_validation_failed", error=str(e), slide=s.get("index"))

        completed.append(ModuleContent(
            module_index=module.module_index,
            title=module.title,
            slides=validated_slides
        ).model_dump())

        logger.info("module_completed",
                     module=module.module_index,
                     slides=len(validated_slides))

    # ═══ CIRCUIT BREAKER: se troppi moduli falliti, interrompi la pipeline ═══
    total_modules = len(pacing.modules[start_index:])
    if failed_count > total_modules * 0.5:
        raise RuntimeError(
            f"Circuit breaker: {failed_count}/{total_modules} moduli falliti. "
            f"Verificare la qualità dei chunk RAG o lo stato delle API Anthropic."
        )

    return {
        "completed_modules": completed,
        "current_module_index": len(pacing.modules)
    }
```

### 5.6 Prompt Engineering — Specifica Completa

**System Prompt (Target: Discente):**

```
Sei un esperto di formazione sulla sicurezza sul lavoro in Italia. Generi slide per corsi normativi destinati ai DISCENTI (lavoratori che devono apprendere).

REGOLE INVIOLABILI:
1. Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito nel contesto. Non inventare MAI informazioni normative.
2. Ogni slide DEVE avere un normative_ref che cita l'articolo/comma di legge.
3. Tono: accessibile, diretto, con esempi concreti dalla vita lavorativa. Traduci il legalese in linguaggio quotidiano.
4. Struttura slide: Hook (scenario reale) → Concetto → Norma (sintetizzata) → Pratica ("cosa devi fare")
5. Per DIAGRAM: genera SVG inline semplice (rettangoli + frecce + testo). NON usare Mermaid.js. L'SVG sarà convertito in PNG lato server.
6. Rispondi ESCLUSIVAMENTE con un array JSON valido. Nessun testo prima o dopo il JSON.

FORMATO OUTPUT — Array JSON di oggetti SlideContent:
[
  {
    "index": 0,
    "module_index": 0,
    "slide_type": "CONTENT_TEXT",
    "title": "Titolo slide (max 80 caratteri)",
    "body": "Testo corpo slide (max 90 parole per CONTENT_TEXT)",
    "speaker_notes": "Note per il relatore",
    "normative_ref": "Art. 37, comma 1, D.Lgs 81/08",
    "source_chunk_ids": ["uuid-del-chunk-usato"],
    "image": {"strategy": "none"},
    "quiz_options": null,
    "quiz_correct": null
  }
]

TIPI SLIDE DISPONIBILI: TITLE, CONTENT_TEXT, CONTENT_IMAGE, DIAGRAM, QUIZ, CASE_STUDY, RECAP, CLOSING
LIMITI PAROLE: CONTENT_TEXT=90, CONTENT_IMAGE=60, QUIZ=60, CASE_STUDY=100, DIAGRAM=50, RECAP=70
```

**System Prompt (Target: Formatore):**

```
Sei un esperto di formazione sulla sicurezza sul lavoro in Italia. Generi slide per corsi destinati ai FORMATORI (chi deve insegnare).

REGOLE INVIOLABILI:
1. Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito nel contesto. Non inventare MAI.
2. Ogni slide DEVE avere un normative_ref con citazione puntuale (articolo, comma, decreto, data).
3. Tono: tecnico-normativo, registro professionale. Citazioni puntuali, non divulgative.
4. Struttura slide: Norma integrale → Interpretazione → Nota metodologica → Esercitazione suggerita
5. Per DIAGRAM: genera SVG inline semplice (rettangoli + frecce + testo). NON usare Mermaid.js.
6. Rispondi ESCLUSIVAMENTE con un array JSON valido. Nessun testo prima o dopo il JSON.

FORMATO OUTPUT: identico al target Discente (stesso schema JSON SlideContent).
```

**User Prompt Template (per singolo modulo):**

```python
# agents/prompts.py

from models.core import TargetType

def build_content_system_prompt(target: TargetType) -> str:
    if target == TargetType.DISCENTE:
        return SYSTEM_PROMPT_DISCENTE  # testo sopra
    return SYSTEM_PROMPT_FORMATORE  # testo sopra


def build_module_prompt(module, chunks, style_patterns, previous_summary, target):
    """Costruisce il prompt utente per generare un modulo.
    Differenzia istruzioni aggiuntive per target Formatore."""

    chunks_text = ""
    for i, chunk in enumerate(chunks):
        chunks_text += (
            f"---\n[Chunk {i+1}] {chunk.hierarchy_path}:\n"
            f'"{chunk.body}"\n'
            f"ID: {chunk.chunk_id} | Tipo: {chunk.chunk_type} | Tags: {chunk.tags}\n"
        )

    style_text = ""
    if style_patterns:
        sp = style_patterns[0]  # pattern più recente
        style_text = (
            f"PATTERN STILISTICI (metadati dai corsi approvati — NON usare come fonte normativa):\n"
            f"- Tono: {sp.tone_register}\n"
            f"- Media parole per slide: {sp.avg_words_per_slide}\n"
            f"- Sequenza slide tipica: {sp.preferred_slide_sequence}\n"
            f"- Sezioni ricorrenti: {sp.recurring_section_titles}\n"
        )

    base_prompt = (
        f"MODULO {module.module_index}: {module.title}\n"
        f"Slide da generare: {module.slide_count} (distribuzione: {module.slide_distribution})\n\n"
        f"CHUNK NORMATIVI PERTINENTI:\n{chunks_text}---\n\n"
        f"{style_text}\n"
        f"MODULI PRECEDENTI (riassunto per coerenza narrativa):\n{previous_summary}\n\n"
        f"Genera {module.slide_count} slide come array JSON."
    )

    # ═══ ISTRUZIONI AGGIUNTIVE PER FORMATORE ═══
    if target == TargetType.FORMATORE:
        base_prompt += """

ISTRUZIONI AGGIUNTIVE PER FORMATORE:
- Ogni modulo deve includere almeno 1 slide CASE_STUDY con esercitazione suggerita
- speaker_notes devono contenere note metodologiche (come presentare il concetto, tempi suggeriti, domande da porre all'aula)
- Le citazioni normative devono essere complete (articolo + comma + decreto + data di emanazione)
- Includi varianti regionali dove pertinenti
"""

    return base_prompt


def build_previous_summary(completed_modules: list[dict]) -> str:
    """Costruisce riassunto dei moduli completati per coerenza narrativa.
    Include titoli delle prime 5 slide per modulo, così l'LLM sa QUALI TEMI
    sono stati trattati e può evitare ripetizioni cross-modulo."""
    if not completed_modules:
        return "Nessun modulo precedente."
    lines = []
    for m in completed_modules:
        slide_titles = [s.get("title", "") for s in m.get("slides", [])[:5]]
        titles_str = ", ".join(t for t in slide_titles if t)
        lines.append(
            f"- Modulo {m['module_index']}: \"{m['title']}\" — "
            f"Argomenti trattati: {titles_str}"
        )
    return "\n".join(lines)
```

---

## §06 — KNOWLEDGE BASE, RAG & INGESTION PIPELINE

### 6.1 Livello 1 — Corpus Normativo (Source of Truth)

#### 6.1.1 Pipeline di Ingestion — Specifica Operativa

La pipeline di ingestion trasforma un PDF normativo in chunk indicizzati nel database. Quattro stadi sequenziali.

**Stadio 1 — Parsing (pdfplumber)**

```python
# services/ingestion_service.py
import pdfplumber
import structlog

logger = structlog.get_logger()

def parse_regulation_pdf(pdf_path: str) -> str:
    """Estrae testo strutturato da PDF normativo.
    pdfplumber è preferito a PyMuPDF perché estrae metadati strutturali
    (tabelle, box di testo, layout) necessari per il chunking."""
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text(layout=True) + "\n"
    logger.info("pdf_parsed", path=pdf_path, chars=len(full_text), pages=len(pdf.pages))
    return full_text
```

**Stadio 2 — Chunking Ibrido con Coverage Check Normalizzato**

```python
import re
import structlog

logger = structlog.get_logger()

# ═══ PATTERN CORRETTO per normative italiane ═══
# Supporta: Art. 37, Art. 37-bis, Art. 37-ter, Art. 37-quater,
# Art. 37-quinquies, Art. 37-sexies, Art. 37-septies, Art. 37-octies,
# Art. 37-novies, Art. 37-decies, Articolo 37
ART_PATTERN = re.compile(
    r'Art(?:icolo)?\.?\s*'
    r'(\d+(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?)'
    r'\s*[\.\-\—\s]+(.+?)'
    r'(?=Art(?:icolo)?\.?\s*\d+|$)',
    re.DOTALL | re.IGNORECASE
)

COMMA_PATTERN = re.compile(
    r'(\d+)\.\s+(.+?)(?=\d+\.\s+|$)',
    re.DOTALL
)

# Pattern per allegati
ALLEGATO_PATTERN = re.compile(
    r'(Allegato\s+[IVXLCDM\d]+(?:-(?:bis|ter))?)\s*[\.\-\—\s]*(.+?)'
    r'(?=Allegato\s+[IVXLCDM\d]+|$)',
    re.DOTALL | re.IGNORECASE
)


def normalize_for_coverage(text: str) -> str:
    """Normalizza testo per confronto coverage accurato.
    Rimuove spazi, header/footer PDF, numerazione pagina Gazzetta Ufficiale."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'Gazzetta Ufficiale.*?Serie.*?\d+', '', text)
    text = re.sub(r'— \d+ —', '', text)
    return text.strip()


def chunk_structured_regulation(full_text: str, regulation_id: str) -> list[dict]:
    """Chunking per normative strutturate (Decreti Legislativi, DM, Accordi).
    Ogni chunk = un articolo o un comma, con gerarchia completa."""
    chunks = []

    # ═══ FASE 1: Articoli e commi ═══
    for art_match in ART_PATTERN.finditer(full_text):
        art_num = art_match.group(1)
        art_body = art_match.group(2).strip()

        commas = COMMA_PATTERN.findall(art_body)
        if commas and len(commas) > 1:
            for comma_num, comma_body in commas:
                chunks.append({
                    "regulation_id": regulation_id,
                    "article": f"Art. {art_num}",
                    "paragraph": f"Comma {comma_num}",
                    "hierarchy_path": f"Art. {art_num} > Comma {comma_num}",
                    "body": comma_body.strip(),
                })
        else:
            chunks.append({
                "regulation_id": regulation_id,
                "article": f"Art. {art_num}",
                "paragraph": None,
                "hierarchy_path": f"Art. {art_num}",
                "body": art_body,
            })

    # ═══ FASE 2: Allegati ═══
    for all_match in ALLEGATO_PATTERN.finditer(full_text):
        all_name = all_match.group(1).strip()
        all_body = all_match.group(2).strip()
        if len(all_body) > 50:  # ignora allegati vuoti/corrotti
            chunks.append({
                "regulation_id": regulation_id,
                "article": all_name,
                "paragraph": None,
                "hierarchy_path": all_name,
                "body": all_body,
            })

    return chunks


def chunk_unstructured_regulation(full_text: str, regulation_id: str) -> list[dict]:
    """Fallback per normative non strutturate (delibere regionali, allegati, tabelle).
    Chunking per paragrafo con overlap di 1 frase dal paragrafo precedente."""
    paragraphs = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > 50]
    chunks = []
    for i, p in enumerate(paragraphs):
        if i > 0:
            prev_sentences = paragraphs[i-1].split('.')
            overlap = prev_sentences[-2].strip() + '.' if len(prev_sentences) > 1 else ''
            body = f"{overlap} {p}" if overlap else p
        else:
            body = p
        chunks.append({
            "regulation_id": regulation_id,
            "article": None,
            "paragraph": None,
            "hierarchy_path": f"Paragrafo {i+1}",
            "body": body
        })
    return chunks


def extract_uncaptured_text(full_text: str, chunks: list[dict]) -> str:
    """Estrae il testo che il chunking strutturato non ha catturato."""
    captured = set()
    for chunk in chunks:
        captured.add(chunk["body"][:100])  # primi 100 char come fingerprint
    residual_parts = []
    for paragraph in full_text.split('\n\n'):
        paragraph = paragraph.strip()
        if len(paragraph) > 50 and paragraph[:100] not in captured:
            residual_parts.append(paragraph)
    return '\n\n'.join(residual_parts)


def chunk_regulation(full_text: str, regulation_id: str) -> list[dict]:
    """Entry point: chunking ibrido con coverage check normalizzato.
    Se il regex strutturato cattura meno del 70% del testo NORMALIZZATO,
    il residuo viene chunkato per paragrafo con overlap."""

    # 1. Prova chunking strutturato
    chunks = chunk_structured_regulation(full_text, regulation_id)

    # 2. Calcola copertura con normalizzazione (rimuove header/footer PDF)
    captured_normalized = normalize_for_coverage(" ".join(c["body"] for c in chunks))
    full_normalized = normalize_for_coverage(full_text)
    coverage = len(captured_normalized) / max(len(full_normalized), 1)

    logger.info("chunking_coverage",
                regulation_id=regulation_id,
                structured_chunks=len(chunks),
                coverage=round(coverage, 2))

    # 3. Se copertura < 70%, fallback per il testo residuo
    if coverage < 0.7:
        residual = extract_uncaptured_text(full_text, chunks)
        fallback_chunks = chunk_unstructured_regulation(residual, regulation_id)
        chunks += fallback_chunks
        logger.warning("low_coverage_chunking",
                       coverage=round(coverage, 2),
                       regulation_id=regulation_id,
                       fallback_chunks=len(fallback_chunks))

    return chunks
```

**Stadio 3 — Classificazione (LLM-assisted con validazione)**

```python
import json
from tenacity import retry, stop_after_attempt, wait_exponential

CLASSIFICATION_PROMPT = """Classifica questo chunk normativo italiano. Rispondi SOLO con JSON valido.

Chunk: "{body}"

Formato richiesto:
{{"type": "OBBLIGO|SANZIONE|DEFINIZIONE|PROCEDURA|GENERALE", "tags": ["tag1", "tag2"]}}

Regole:
- OBBLIGO: impone un dovere ("deve", "è tenuto", "è obbligato", "assicura")
- SANZIONE: indica pene o ammende ("arresto", "ammenda", "sanzione", "euro")
- DEFINIZIONE: definisce un termine ("si intende", "ai fini del presente")
- PROCEDURA: descrive un processo ("modalità", "procedimento", "entro")
- GENERALE: nessuna delle precedenti
- tags: scegli tra [formazione, lavoratori, datore_lavoro, rspp, rls, antincendio, primo_soccorso, dpi, valutazione_rischi, cantieri, haccp, igiene]
"""

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=2, max=10))
async def classify_chunk(body: str) -> dict:
    raw = await call_llm(
        messages=[{"role": "user", "content": CLASSIFICATION_PROMPT.format(body=body[:1000])}],
        system="Sei un classificatore di testi normativi. Rispondi SOLO con JSON."
    )
    result = json.loads(raw)
    # Validazione: SANZIONE deve contenere parole legate a pene/ammende
    if result["type"] == "SANZIONE" and not any(
        w in body.lower() for w in ["ammenda", "arresto", "sanzione", "euro", "pena"]
    ):
        result["type"] = "GENERALE"
    return result
```

**Stadio 4 — Embedding, Deduplicazione e Indicizzazione (batch con retry)**

```python
import hashlib
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embedding batch via Voyage AI. Max 50 testi per batch (rate limit).
    Usa get_voyage_client() da dependencies.py — MAI variabile globale."""
    from services.dependencies import get_voyage_client
    client = get_voyage_client()
    response = await client.embed(texts, model="voyage-3")
    return response.embeddings


async def voyage_embed_with_retry(text: str) -> list[float]:
    """Embedding di un singolo testo (usato per la query RAG nel Research Agent)."""
    embeddings = await embed_batch([text])
    return embeddings[0]


async def index_chunks(chunks: list[dict], pool):
    """Indicizza chunk con embedding in batch di 50.
    Deduplicazione via content_hash: se un chunk identico esiste già, lo salta."""
    BATCH_SIZE = 50
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]
        texts = [c["body"] for c in batch]
        embeddings = await embed_batch(texts)

        for chunk, embedding in zip(batch, embeddings):
            content_hash = hashlib.sha256(chunk["body"].encode()).hexdigest()

            # ═══ DEDUPLICAZIONE: evita re-ingestion di chunk identici ═══
            existing = await pool.fetchval(
                "SELECT id FROM regulation_chunks WHERE content_hash = $1 AND is_current = true",
                content_hash
            )
            if existing:
                logger.info("chunk_deduplicated", hash=content_hash[:16])
                continue

            await pool.execute(
                "INSERT INTO regulation_chunks "
                "(regulation_id, article, paragraph, hierarchy_path, body, "
                "chunk_type, tags, embedding, content_hash) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                chunk["regulation_id"], chunk["article"], chunk["paragraph"],
                chunk["hierarchy_path"], chunk["body"],
                chunk["classification"]["type"],
                chunk["classification"]["tags"],
                embedding, content_hash
            )
        logger.info("chunks_indexed", batch=i//BATCH_SIZE+1, count=len(batch))
```

### 6.2 Livello 2 — Corsi Approvati & StylePatternExtractor

Il Livello 2 contiene i corsi certificati. Il sistema estrae da essi SOLO metadati strutturali (mai testo normativo). La separazione è la barriera primaria anti-Model-Collapse.

```python
# services/knowledge_repo.py

async def get_style_patterns(self, course_type: str, target: str) -> list[StylePattern]:
    """Recupera pattern stilistici dal Livello 2, i più recenti prima."""
    rows = await self.pool.fetch(
        "SELECT style_pattern FROM approved_courses "
        "WHERE course_type = $1 AND target = $2 "
        "ORDER BY certified_at DESC LIMIT 5",
        course_type, target
    )
    return [StylePattern(**json.loads(row['style_pattern'])) for row in rows]
```

```python
# services/certification_service.py
import statistics
from collections import Counter
from models.knowledge import StylePattern
from models.pipeline import SlideContent

class StylePatternExtractor:
    """Estrae metadati strutturali DETERMINISTICI da un corso approvato.
    NON usa LLM. NON estrae testo. NON estrae frasi.
    Solo statistiche numeriche e categoriche.

    ═══ VINCOLO ANTI-MODEL-COLLAPSE ═══
    Se un corso approvato contiene un errore normativo, quell'errore
    NON si propaga perché questo estrattore cattura solo:
    - Quante parole per slide (numero)
    - Quale sequenza di tipi slide (lista di enum)
    - Quale registro linguistico (stringa categorica)
    - Quali titoli ricorrenti (lista di stringhe brevi)
    - Quanti quiz per modulo (numero)
    - Quale percentuale di slide ha immagini (numero)
    Nessuna formulazione testuale, nessun contenuto normativo."""

    def extract(self, slides: list[SlideContent]) -> StylePattern:
        """Calcola il pattern stilistico da una lista di slide validate."""

        word_counts = [len(s.body.split()) for s in slides]
        avg_words = int(statistics.mean(word_counts)) if word_counts else 75

        type_sequence = [s.slide_type.value for s in slides]
        window_size = 6
        windows = [
            tuple(type_sequence[i:i+window_size])
            for i in range(len(type_sequence) - window_size + 1)
        ]
        if windows:
            most_common_window = Counter(windows).most_common(1)[0][0]
            preferred_sequence = list(most_common_window)
        else:
            preferred_sequence = ["CONTENT_TEXT", "CONTENT_TEXT", "CONTENT_IMAGE",
                                  "CONTENT_TEXT", "QUIZ", "RECAP"]

        quiz_count = sum(1 for s in slides if s.slide_type.value == "QUIZ")
        if avg_words > 80:
            tone = "formale"
        elif avg_words < 60:
            tone = "accessibile"
        else:
            tone = "tecnico-divulgativo"

        unique_titles = list(dict.fromkeys(
            s.title for s in slides if s.slide_type.value in ("TITLE", "RECAP")
        ))[:10]

        module_indices = set(s.module_index for s in slides)
        avg_quiz = quiz_count / max(len(module_indices), 1)

        image_slides = sum(
            1 for s in slides
            if s.slide_type.value in ("CONTENT_IMAGE", "DIAGRAM")
        )
        image_ratio = image_slides / max(len(slides), 1)

        return StylePattern(
            avg_words_per_slide=avg_words,
            preferred_slide_sequence=preferred_sequence,
            tone_register=tone,
            recurring_section_titles=unique_titles,
            avg_quiz_per_module=round(avg_quiz, 1),
            preferred_image_ratio=round(image_ratio, 2)
        )


async def certify_course(course_id: str, reviewer_id: str, pool) -> str:
    """Certifica un corso e inserisce il pattern stilistico nel Livello 2."""
    course = await pool.fetchrow("SELECT * FROM courses WHERE id = $1", course_id)
    if not course or not course['slide_contents_json']:
        raise ValueError("Corso non trovato o senza contenuto")

    slides = [SlideContent(**s) for s in json.loads(course['slide_contents_json'])]
    extractor = StylePatternExtractor()
    pattern = extractor.extract(slides)

    approved_id = await pool.fetchval(
        "INSERT INTO approved_courses "
        "(course_type, target, style_pattern, certified_by, source_course_id) "
        "VALUES ($1, $2, $3, $4, $5) RETURNING id",
        course['course_type'], course['target'],
        pattern.model_dump_json(),
        reviewer_id, course_id
    )

    await pool.execute(
        "UPDATE courses SET status = 'certified' WHERE id = $1", course_id
    )

    return str(approved_id)
```

### 6.3 KnowledgeRepository — Con Validazione Slug e Filtro Regionale Corretto

```python
# services/knowledge_repo.py
class KnowledgeRepository:

    def __init__(self, pool):
        self.pool = pool

    async def resolve_slugs_to_ids(self, slugs: list[str]) -> list[str]:
        """Risolve slug → UUID con VALIDAZIONE: se manca uno slug, alza errore.
        Senza questa validazione, un typo nel COURSE_CATALOG produce corsi incompleti."""
        sql = "SELECT id, slug FROM regulations WHERE slug = ANY($1::text[]) AND status = 'VIGENTE'"
        rows = await self.pool.fetch(sql, slugs)
        found_slugs = {row['slug'] for row in rows}
        missing = set(slugs) - found_slugs
        if missing:
            raise ValueError(
                f"Slug normativi non trovati nel database: {missing}. "
                f"Verificare COURSE_CATALOG e tabella regulations."
            )
        return [str(row['id']) for row in rows]

    async def search_chunks(self, query_embedding, regulation_ids, region, top_k=30):
        """Ricerca vettoriale filtrata per normativa e regione.
        Il filtro regionale usa regulations.region (JOIN affidabile),
        NON i tag dei chunk (che non contengono info regionali)."""
        sql = """
            SELECT rc.id, rc.regulation_id, rc.article, rc.paragraph, rc.hierarchy_path,
                   rc.body, rc.chunk_type, rc.tags,
                   1 - (rc.embedding <=> $1::vector) AS relevance_score
            FROM regulation_chunks rc
            JOIN regulations r ON rc.regulation_id = r.id
            WHERE rc.regulation_id = ANY($2::uuid[])
              AND rc.is_current = true
              AND (r.region = 'NAZIONALE' OR ($3 IS NOT NULL AND r.region = $3))
            ORDER BY rc.embedding <=> $1::vector
            LIMIT $4
        """
        rows = await self.pool.fetch(sql, query_embedding, regulation_ids, region, top_k)
        return [NormativeChunk(
            chunk_id=str(row['id']),
            regulation_id=str(row['regulation_id']),
            article=row['article'],
            paragraph=row['paragraph'],
            hierarchy_path=row['hierarchy_path'],
            body=row['body'],
            chunk_type=row['chunk_type'],
            tags=row['tags'] or [],
            relevance_score=float(row['relevance_score'])
        ) for row in rows]
```

---

## §06B — PACING ENGINE — SPECIFICA COMPLETA

```python
# services/pacing_engine.py
import math
from models.pipeline import PacingPlan, ModuleSpec
from models.core import SlideDensity


class PacingEngine:
    """Traduce durata + densità in un piano slide dettagliato.
    Non applica una formula lineare — calcola una distribuzione ponderata
    per tipo di slide, ciascuno con la propria durata media."""

    SECONDS_PER_TYPE = {
        "CONTENT_TEXT": 45,
        "CONTENT_IMAGE": 35,
        "DIAGRAM": 60,
        "QUIZ": 90,
        "CASE_STUDY": 90,
        "RECAP": 30,
    }

    DISTRIBUTION = {
        "CONTENT_TEXT": 0.45,
        "CONTENT_IMAGE": 0.20,
        "DIAGRAM": 0.10,
        "QUIZ": 0.10,
        "CASE_STUDY": 0.05,
        "RECAP": 0.10,
    }

    DENSITY_MULTIPLIER = {
        SlideDensity.LEGGERA: 0.8,
        SlideDensity.STANDARD: 1.0,
        SlideDensity.INTENSIVA: 1.25,
    }

    SLIDES_PER_MODULE_TARGET = 40

    def calculate(self, duration_hours: float, density: SlideDensity = SlideDensity.STANDARD, module_titles: list[str] | None = None) -> PacingPlan:
        """Calcola il piano di pacing. Se module_titles è fornito (dal COURSE_CATALOG),
        usa quei titoli per i moduli. Altrimenti usa titoli generici 'Modulo N'."""
        total_seconds = duration_hours * 3600
        multiplier = self.DENSITY_MULTIPLIER[density]

        avg_seconds_per_slide = sum(
            self.SECONDS_PER_TYPE[t] * self.DISTRIBUTION[t]
            for t in self.DISTRIBUTION
        )

        total_slides = int((total_seconds / avg_seconds_per_slide) * multiplier)
        num_modules = max(2, math.ceil(total_slides / self.SLIDES_PER_MODULE_TARGET))

        base_per_module = total_slides // num_modules
        remainder = total_slides % num_modules

        modules = []
        for i in range(num_modules):
            slide_count = base_per_module + (1 if i < remainder else 0)

            distribution = {}
            assigned = 0
            types_list = list(self.DISTRIBUTION.items())
            for j, (slide_type, ratio) in enumerate(types_list):
                if j == len(types_list) - 1:
                    distribution[slide_type] = slide_count - assigned
                else:
                    count = max(1, round(slide_count * ratio))
                    distribution[slide_type] = count
                    assigned += count

            modules.append(ModuleSpec(
                module_index=i,
                title=module_titles[i] if module_titles and i < len(module_titles) else f"Modulo {i+1}",
                slide_count=slide_count,
                slide_distribution=distribution
            ))

        return PacingPlan(total_slides=total_slides, modules=modules)
```

---

## §07 — MULTIMODAL GENERATION & PPTX FACTORY

### 7.0 Image Pre-Fetch con Concurrency Limiter e Validazione Integrità

```python
# services/image_service.py
import asyncio
import io
import os
import re
import uuid
import httpx
import structlog
import cairosvg
from PIL import Image
from models.pipeline import SlideContent

logger = structlog.get_logger()

_image_semaphore = asyncio.Semaphore(5)

# ═══ LIMITE DIMENSIONE DOWNLOAD ═══
MAX_IMAGE_BYTES = 5_000_000  # 5MB — previene OOM da immagini enormi


def sanitize_svg(svg_code: str) -> str:
    """Rimuove elementi pericolosi dall'SVG generato dall'LLM.
    ═══ VINCOLO DI SICUREZZA ═══
    L'SVG è un formato XML completo che supporta <script>, <foreignObject>,
    xlink:href verso URL esterni, e event handler. Un LLM che genera SVG
    malevolo (o un prompt injection nel chunk normativo) potrebbe causare
    SSRF via cairosvg o rendere contenuti inattesi."""
    svg_code = re.sub(r'<script[^>]*>.*?</script>', '', svg_code, flags=re.DOTALL)
    svg_code = re.sub(r'<foreignObject[^>]*>.*?</foreignObject>', '', svg_code, flags=re.DOTALL)
    svg_code = re.sub(r'xlink:href\s*=\s*["\']https?://[^"\']*["\']', '', svg_code)
    svg_code = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', svg_code)
    return svg_code


async def _download_one_image(
    slide: SlideContent, pool, client: httpx.AsyncClient
) -> tuple[int, str | None]:
    """Scarica una singola immagine con semaforo di concorrenza e validazione integrità.
    Riceve il client httpx CONDIVISO da prefetch_images — nessun client creato qui."""
    async with _image_semaphore:
        # Controlla cache
        cached = await pool.fetchrow(
            "SELECT local_path FROM image_cache WHERE query=$1",
            slide.image.query
        )
        if cached:
            await pool.execute(
                "UPDATE image_cache SET usage_count = usage_count + 1 WHERE query=$1",
                slide.image.query
            )
            return (slide.index, cached['local_path'])

        # Download con timeout e limite dimensione
        try:
            resp = await client.get(slide.image.query_url)
            resp.raise_for_status()

            raw_bytes = resp.content
            if len(raw_bytes) > MAX_IMAGE_BYTES:
                logger.warning("image_too_large", slide=slide.index,
                               size_mb=round(len(raw_bytes)/1_000_000, 1))
                return (slide.index, None)

            # ═══ VALIDAZIONE INTEGRITÀ — Pillow load() forza il decode completo ═══
            img = Image.open(io.BytesIO(raw_bytes))
            img.load()  # alza eccezione se corrotta — più robusto di verify() + re-open

            local_path = f"output/images/{uuid.uuid4()}.png"
            os.makedirs("output/images", exist_ok=True)
            img.convert("RGB").save(local_path, "PNG")

            await pool.execute(
                "INSERT INTO image_cache (query, image_url, local_path, format) "
                "VALUES ($1,$2,$3,'png')",
                slide.image.query, str(slide.image.query_url), local_path
            )
            return (slide.index, local_path)

        except Exception as e:
            logger.warning("image_download_failed", slide=slide.index, error=str(e))
            return (slide.index, None)


def _render_diagram_sync(slide: SlideContent) -> tuple[int, str | None]:
    """Renderizza SVG inline → PNG per slide DIAGRAM. SINCRONO.
    Il Content Agent genera SVG direttamente (non Mermaid).
    L'SVG viene sanitizzato PRIMA del rendering."""
    if not slide.image.diagram_code:
        return (slide.index, None)
    try:
        safe_svg = sanitize_svg(slide.image.diagram_code)
        local_path = f"output/diagrams/{uuid.uuid4()}.png"
        os.makedirs("output/diagrams", exist_ok=True)
        cairosvg.svg2png(
            bytestring=safe_svg.encode(),
            write_to=local_path,
            output_width=1200, output_height=800
        )
        return (slide.index, local_path)
    except Exception as e:
        logger.warning("diagram_render_failed", slide=slide.index, error=str(e))
        return (slide.index, None)


async def prefetch_images(slides: list[SlideContent], pool) -> dict[int, str]:
    """Scarica tutte le immagini web + renderizza diagrammi SVG PRIMA del build sincrono.
    Il SlideBuilder riceve solo path locali, MAI URL.
    ═══ CLIENT HTTPX CONDIVISO ═══
    Un unico httpx.AsyncClient con connection pooling per tutti i download.
    ═══ DIAGRAMMI IN PARALLELO ═══
    cairosvg è sincrono → wrappato in asyncio.to_thread() per concorrenza.
    Ritorna: {slide_index: local_path}"""

    image_map = {}

    # Web images — con client condiviso
    async with httpx.AsyncClient(timeout=10.0) as client:
        web_tasks = [
            _download_one_image(s, pool, client)
            for s in slides
            if s.image.strategy == 'web_search' and s.image.query_url
        ]
        web_results = await asyncio.gather(*web_tasks, return_exceptions=True)

    for result in web_results:
        if isinstance(result, tuple) and result[1] is not None:
            image_map[result[0]] = result[1]

    # Diagrammi SVG→PNG — in parallelo con asyncio.to_thread()
    diagram_slides = [s for s in slides if s.image.strategy == 'diagram']
    if diagram_slides:
        diagram_tasks = [
            asyncio.to_thread(_render_diagram_sync, s)
            for s in diagram_slides
        ]
        diagram_results = await asyncio.gather(*diagram_tasks, return_exceptions=True)
        for result in diagram_results:
            if isinstance(result, tuple) and result[1] is not None:
                image_map[result[0]] = result[1]

    logger.info("images_prefetched",
                web_requested=len(web_tasks) if 'web_tasks' in dir() else 0,
                diagrams=len(diagram_slides),
                total_resolved=len(image_map))
    return image_map
```

### 7.1 ProductionBuilder — Con Memory Check e Resilienza Immagini

```python
# builders/production_builder.py
import asyncio
import shutil
import os
import psutil
import structlog

logger = structlog.get_logger()


def check_memory_before_build(slide_count: int):
    """Verifica RAM disponibile prima del build PPTX.
    python-pptx tiene l'intero Presentation in RAM.
    700 slide con immagini possono richiedere 500MB-1GB."""
    available_mb = psutil.virtual_memory().available / (1024 * 1024)
    estimated_mb = slide_count * 1.5
    if estimated_mb > available_mb * 0.6:
        raise MemoryError(
            f"RAM insufficiente per build PPTX: "
            f"{available_mb:.0f}MB disponibili, "
            f"~{estimated_mb:.0f}MB stimati per {slide_count} slide. "
            f"Ridurre la durata del corso o riavviare il server."
        )
    logger.info("memory_check_passed",
                available_mb=round(available_mb),
                estimated_mb=round(estimated_mb),
                slides=slide_count)


def check_disk_before_build():
    """Verifica spazio disco prima del build."""
    disk_free_gb = shutil.disk_usage("/app/output").free / (1024**3)
    if disk_free_gb < 1.0:
        raise IOError(
            f"Spazio disco insufficiente: {disk_free_gb:.1f}GB liberi. "
            f"Servono almeno 1GB per il build."
        )


class ProductionBuilder:
    """python-pptx, cairosvg e WeasyPrint sono SINCRONI.
    Ogni chiamata è wrappata in asyncio.to_thread().
    ═══ VINCOLO ARCHITETTURALE: Semaphore(1) ═══
    python-pptx + lxml NON sono thread-safe. Non alzare MAI il semaforo a 2+
    senza passare a un process pool (multiprocessing) o Celery."""

    def __init__(self, brand_config: dict):
        self.brand_config = brand_config
        self.slide_builder = SlideBuilder(brand_config)
        self.pdf_builder = PdfBuilder(brand_config)
        self.validator = PptxValidator()

    async def build(self, slides, course, job_id, ws_callback, image_map):
        """Orchestrazione del build: memory check → PPTX → validate → PDF → cleanup."""

        check_memory_before_build(len(slides))
        check_disk_before_build()

        await ws_callback(job_id, 87, "Generazione PPTX...")
        pptx_path = await asyncio.to_thread(
            self.slide_builder.build, slides, course, image_map
        )

        await ws_callback(job_id, 92, "Validazione PPTX...")
        validation = await asyncio.to_thread(
            self.validator.validate, pptx_path, slides
        )

        await ws_callback(job_id, 95, "Generazione PDF dispensa...")
        pdf_path = await asyncio.to_thread(
            self.pdf_builder.build, slides, course
        )

        await asyncio.to_thread(self._cleanup_tmp)

        report = self._build_report(slides, validation)
        return pptx_path, pdf_path, report

    def _cleanup_tmp(self):
        """Pulizia di TUTTI i file temporanei generati durante il build:
        output/tmp_* (file temporanei generici), output/diagrams/*.png (SVG renderizzati),
        output/images/*.png (immagini scaricate e convertite).
        Rimuove solo file più vecchi di 1 ora per evitare di cancellare
        file in uso da un build in corso."""
        import glob, time
        cutoff = time.time() - 3600
        for pattern in ["output/tmp_*", "output/diagrams/*.png", "output/images/*.png"]:
            for f in glob.glob(pattern):
                try:
                    if os.path.getmtime(f) < cutoff:
                        os.remove(f)
                except OSError:
                    pass

    def _build_report(self, slides, validation) -> dict:
        from models.pipeline import GenerationReport
        return GenerationReport(
            total_slides=len(slides),
            slides_with_images=sum(1 for s in slides if s.image.strategy == "web_search"),
            slides_with_diagrams=sum(1 for s in slides if s.image.strategy == "diagram"),
            quiz_count=sum(1 for s in slides if s.slide_type.value == "QUIZ"),
            modules_completed=len(set(s.module_index for s in slides)),
            modules_failed=0,
            normative_refs_count=sum(1 for s in slides if s.normative_ref),
            warnings=validation.get("warnings", []),
            generation_time_seconds=0  # calcolato dal caller
        ).model_dump()
```

**Nota per lo SlideBuilder:** Ogni immagine va inserita con try/except. Se l'inserimento fallisce, la slide mostra un placeholder testuale, NON crasha il build.

```python
# builders/slide_builder.py — pattern per inserimento immagine resiliente
# image_path = image_map.get(slide.index)
# if image_path and os.path.exists(image_path):
#     try:
#         slide_obj.placeholders[image_ph_idx].insert_picture(image_path)
#     except Exception:
#         logger.warning("pptx_image_insert_failed", slide=slide.index)
#         # Inserisci placeholder testuale "[Immagine non disponibile]"
```

### 7.2 PDF Builder — Con Template Strutturato

```python
# builders/pdf_builder.py
import weasyprint
import structlog
from datetime import datetime

logger = structlog.get_logger()

PDF_TEMPLATE = """
<html>
<head><style>
  @page {{ size: A4; margin: 2cm; @bottom-center {{ content: counter(page); }} }}
  body {{ font-family: 'Open Sans', sans-serif; font-size: 11pt; line-height: 1.6; }}
  h1 {{ font-family: 'Montserrat', sans-serif; color: {primary}; page-break-before: always; }}
  h1:first-of-type {{ page-break-before: avoid; }}
  h2 {{ color: {secondary}; border-bottom: 1px solid {secondary}; }}
  .normative-ref {{ font-size: 9pt; color: #666; font-style: italic; }}
  .quiz {{ background: #f8f9fa; padding: 1em; border-radius: 4px; margin: 1em 0; }}
  .speaker-notes {{ font-size: 10pt; color: #555; margin-top: 0.5em; }}
</style></head>
<body>
  <h1>{course_title}</h1>
  <p>Durata: {duration_hours}h | Target: {target} | Generato: {date}</p>
  {modules_html}
</body>
</html>
"""

class PdfBuilder:
    def __init__(self, brand_config: dict):
        self.palette = brand_config.get("palette", {})

    def build(self, slides, course) -> str:
        """Genera dispensa PDF da slide. SINCRONO — wrappato in asyncio.to_thread()."""
        modules_html = self._slides_to_html(slides)
        html = PDF_TEMPLATE.format(
            primary=self.palette.get("primary", "#1a365d"),
            secondary=self.palette.get("secondary", "#2b6cb0"),
            course_title=course.get("title", "Corso"),
            duration_hours=course.get("duration_hours", ""),
            target=course.get("target", ""),
            date=datetime.now().strftime("%d/%m/%Y"),
            modules_html=modules_html
        )
        pdf_path = f"output/{course['id']}_dispensa.pdf"
        weasyprint.HTML(string=html).write_pdf(pdf_path)
        logger.info("pdf_generated", path=pdf_path)
        return pdf_path

    def _slides_to_html(self, slides) -> str:
        html_parts = []
        current_module = -1
        for s in slides:
            if s.module_index != current_module:
                current_module = s.module_index
                html_parts.append(f"<h1>Modulo {current_module + 1}</h1>")
            html_parts.append(f"<h2>{s.title}</h2>")
            html_parts.append(f"<p>{s.body}</p>")
            if s.normative_ref:
                html_parts.append(f'<p class="normative-ref">Rif.: {s.normative_ref}</p>')
            if s.speaker_notes:
                html_parts.append(f'<p class="speaker-notes">{s.speaker_notes}</p>')
            if s.slide_type.value == "QUIZ" and s.quiz_options:
                html_parts.append('<div class="quiz">')
                for i, opt in enumerate(s.quiz_options):
                    marker = "✓" if i == s.quiz_correct else " "
                    html_parts.append(f"<p>{marker} {opt}</p>")
                html_parts.append('</div>')
        return "\n".join(html_parts)
```

### 7.3 Template PPTX — Con Specifiche Layout

```python
# scripts/create_pptx_template.py
"""Genera il template PPTX master in modo riproducibile.
Esegui UNA volta, poi versiona il .pptx risultante in Git.
ATTENZIONE: le dimensioni dei placeholder andranno aggiustate
visivamente con 2-3 iterazioni con PowerPoint aperto.
Usare inspect_pptx_template.py per verificare le coordinate."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

def create_template():
    prs = Presentation()
    prs.slide_width = Inches(13.333)   # 16:9 widescreen
    prs.slide_height = Inches(7.5)

    master = prs.slide_masters[0]

    # ═══ LAYOUT 0: TITLE ═══
    # Logo centrato, titolo grande, sottotitolo
    # Titolo: x=1.5in, y=2.0in, w=10.33in, h=2.0in  (centrato)
    # Sottotitolo: x=2.5in, y=4.5in, w=8.33in, h=1.0in
    # Logo: x=5.67in, y=0.5in, w=2.0in, h=1.2in

    # ═══ LAYOUT 1: CONTENT_TEXT ═══
    # Titolo in alto, corpo sotto, footer in basso
    # Titolo:  x=0.5in,  y=0.3in,  w=12.33in, h=1.0in
    # Corpo:   x=0.5in,  y=1.5in,  w=12.33in, h=5.0in
    # Footer:  x=0.0in,  y=7.0in,  w=13.33in, h=0.5in (3 aree: ente|titolo|pagina)

    # ═══ LAYOUT 2: CONTENT_IMAGE ═══
    # Titolo in alto, corpo a sinistra, immagine a destra
    # Titolo:  x=0.5in,  y=0.3in,  w=12.33in, h=1.0in
    # Corpo:   x=0.5in,  y=1.5in,  w=6.0in,   h=5.0in
    # Immagine:x=7.0in,  y=1.5in,  w=5.83in,  h=5.0in
    # Footer:  x=0.0in,  y=7.0in,  w=13.33in, h=0.5in

    # ═══ LAYOUT 3: DIAGRAM ═══
    # Titolo:    x=0.5in, y=0.3in, w=12.33in, h=1.0in
    # Diagramma: x=0.5in, y=1.5in, w=12.33in, h=5.0in

    # ═══ LAYOUT 4: QUIZ ═══
    # Titolo:   x=0.5in, y=0.3in, w=12.33in, h=0.8in
    # Domanda:  x=0.5in, y=1.3in, w=12.33in, h=1.5in
    # Opzione A:x=0.5in, y=3.0in, w=5.9in,   h=0.9in
    # Opzione B:x=6.93in,y=3.0in, w=5.9in,   h=0.9in
    # Opzione C:x=0.5in, y=4.1in, w=5.9in,   h=0.9in
    # Opzione D:x=6.93in,y=4.1in, w=5.9in,   h=0.9in

    # ═══ LAYOUT 5: CASE_STUDY ═══
    # ═══ LAYOUT 6: RECAP ═══
    # ═══ LAYOUT 7: CLOSING ═══

    prs.save("assets/templates/nexus_master.pptx")
    print("Template creato. Verificare con inspect_pptx_template.py")
    print("ATTENZIONE: aggiustare visivamente con PowerPoint aperto (2-3 iterazioni)")
    print("Il template finale va committato come binario in Git.")

if __name__ == "__main__":
    create_template()
```

---

## §08 — SECURITY & AUTH PROTOCOL

### 8.1 Autenticazione JWT Custom con Revoca Implicita

```python
# services/auth_service.py
import os
import bcrypt
import pyotp
import jwt
from datetime import datetime, timedelta, timezone

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES = int(os.environ.get("JWT_EXPIRY_MINUTES", "60"))
JWT_REFRESH_EXPIRY_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRY_DAYS", "7"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_EXPIRY_DAYS),
        "type": "refresh"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica e valida un token JWT. Alza jwt.InvalidTokenError se invalido."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# TOTP è predisposto ma non attivo in v1.0
# def verify_totp(secret: str, code: str) -> bool:
#     totp = pyotp.TOTP(secret)
#     return totp.verify(code)
```

### 8.2 Dependency per Autenticazione con Revoca Implicita

```python
# api/dependencies.py
import uuid as uuid_mod
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.auth_service import decode_token
from services.dependencies import get_pool

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency FastAPI: decodifica JWT e verifica che l'utente sia attivo.
    ═══ REVOCA IMPLICITA: un utente disattivato (is_active=false) viene respinto
    anche con token ancora valido. Nessun bisogno di blacklist Redis.
    ═══ TOKEN TYPE CHECK: verifica che sia un access token, non un refresh token.
    ═══ UUID CONVERSION: payload["sub"] è stringa, users.id è UUID — conversione esplicita."""
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(401, "Token non valido o scaduto")

    # ═══ VERIFICA TIPO TOKEN ═══
    if payload.get("type") != "access":
        raise HTTPException(401, "Token type non valido — atteso access token")

    pool = get_pool()
    # ═══ CONVERSIONE UUID ESPLICITA per asyncpg ═══
    user = await pool.fetchrow(
        "SELECT id, email, role, is_active FROM users WHERE id = $1",
        uuid_mod.UUID(payload["sub"])
    )
    if not user or not user["is_active"]:
        raise HTTPException(401, "Utente non autorizzato o disattivato")
    return dict(user)


def require_role(*roles: str):
    """Factory per dependency role-based. Uso: Depends(require_role('admin', 'reviewer'))
    ═══ VINCOLO: la funzione esterna NON è async ═══
    Se fosse async, Depends(require_role('admin')) restituirebbe una coroutine
    invece della funzione checker, rompendo il meccanismo di dependency injection di FastAPI."""
    async def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"Ruolo {user['role']} non autorizzato")
        return user
    return checker
```

### 8.3 Refresh Token con Verifica Attività

```python
# In api/routes/auth.py
@app.post("/api/auth/refresh")
async def refresh(token: str):
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Token non valido")

    pool = get_pool()
    user = await pool.fetchrow(
        "SELECT id, role, is_active FROM users WHERE id = $1",
        uuid_mod.UUID(payload["sub"])
    )
    if not user or not user["is_active"]:
        raise HTTPException(401, "Utente disattivato")

    return {"access_token": create_access_token(str(user["id"]), user["role"])}
```

### 8.4 CORS — Origin Specifico

Configurato in `main.py` (§02.5). L'origine è letta dalla variabile d'ambiente `FRONTEND_URL`. **Mai** usare `allow_origins=["*"]`.

### 8.5 Rate Limiting

| Endpoint | Limite | Motivazione |
|---|---|---|
| `POST /api/courses` | 5/minuto | Previene flood di job |
| `POST /api/regulations/upload` | 3/minuto | Previene upload ripetuti |
| `POST /api/auth/login` | 10/minuto | Previene brute force |
| `GET /api/*` | 60/minuto | Protezione generica |

### 8.6 Ruoli e Permessi

| Ruolo | Permessi |
|---|---|
| admin | Tutto: gestione utenti, upload normative, generazione, download, certificazione, branding, metriche |
| operator | Generazione corsi, visualizzazione/download propri corsi |
| reviewer | Visualizzazione tutti i corsi, approvazione, certificazione (inserimento Livello 2) |

I permessi sono applicati a livello di API (middleware FastAPI con `get_current_user`), non solo di interfaccia.

### 8.7 Audit Log

Ogni azione è registrata nella tabella `audit_log` che è **immutabile a livello SQL** (vedi §03). Eventi registrati:

- Generazione corso: chi l'ha richiesta, con quali parametri, quali normative consultate
- Approvazione/rifiuto: chi ha approvato, quando, con quale status
- Upload normative: chi ha caricato, quanti chunk estratti
- Accesso al sistema: login, logout, tentativi falliti
- **Metriche pipeline** (action='pipeline_metrics'): tempo totale, slide generate, chiamate LLM, retry, immagini

### 8.8 WebSocket Autenticato

```python
# api/websocket.py
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from services.auth_service import decode_token
from services.dependencies import get_pool
import uuid as uuid_mod

async def get_job_progress(job_id: str) -> dict:
    """Recupera lo stato corrente di un job di generazione.
    Usato dal WebSocket per lo streaming progress e dal polling fallback."""
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT status, progress_percent, current_step, error_message "
        "FROM generation_jobs WHERE id = $1", job_id
    )
    return dict(row) if row else {"status": "not_found"}


async def websocket_endpoint(websocket: WebSocket, job_id: str, token: str):
    """WebSocket per progress tracking. Autenticazione via query param JWT.
    ═══ OWNERSHIP CHECK ═══
    Un operator può monitorare SOLO i propri job.
    Admin e reviewer possono monitorare tutti i job."""
    try:
        payload = decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verifica ownership per operator
    pool = get_pool()
    job = await pool.fetchrow(
        "SELECT c.created_by FROM generation_jobs j "
        "JOIN courses c ON j.course_id = c.id WHERE j.id = $1",
        uuid_mod.UUID(job_id)
    )
    if not job:
        await websocket.close(code=4004, reason="Job non trovato")
        return
    if payload.get("role") == "operator" and str(job["created_by"]) != payload["sub"]:
        await websocket.close(code=4003, reason="Accesso negato a job di altro utente")
        return

    await websocket.accept()
    try:
        while True:
            data = await get_job_progress(job_id)
            await websocket.send_json(data)
            if data.get("status") in ("completed", "failed"):
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass  # Client disconnesso — il job continua in background
```

---

## §09 — PIPELINE DI GENERAZIONE, CONCORRENZA & ERROR HANDLING

### 9.1 Generation Service — Con Timeout Globale, Semaforo e Telemetria

```python
# services/generation_service.py
import asyncio
import json
import os
import time
import structlog
from datetime import datetime
from models.pipeline import SlideContent
from services.dependencies import get_pool
from services.image_service import prefetch_images
from builders.production_builder import ProductionBuilder

logger = structlog.get_logger()

# ═══ SEMAFORO DI CONCORRENZA ═══
# VINCOLO ARCHITETTURALE: python-pptx + lxml NON sono thread-safe.
# Non alzare MAI a Semaphore(2+) senza passare a process pool o Celery.
MAX_CONCURRENT_JOBS = 1
_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# ═══ TIMEOUT GLOBALE PIPELINE ═══
PIPELINE_TIMEOUT_SECONDS = int(os.environ.get("PIPELINE_TIMEOUT", "1800"))  # 30 min

# ═══ EVENTO DI SHUTDOWN ═══
# NON creare un asyncio.Event() locale — usare QUELLO CONDIVISO da dependencies.py.
# Vincolo architetturale D-18: un UNICO shutdown event nell'intero progetto.
from services.dependencies import get_shutdown_event


async def send_ws_progress(job_id: str, percent: int, step: str):
    """Aggiorna il progresso del job nel DB. Il WebSocket lo legge via get_job_progress().
    Questo pattern disaccoppia la pipeline dal WebSocket: la pipeline scrive nel DB,
    il WebSocket legge dal DB. Nessuna dipendenza diretta tra i due."""
    db = get_pool()
    await db.execute(
        "UPDATE generation_jobs SET progress_percent=$1, current_step=$2 WHERE id=$3",
        percent, step, job_id
    )


def build_normative_fingerprint(slides: list[dict]) -> dict:
    """Crea un'impronta delle normative usate per il Delta-Update futuro.
    Struttura: {refs: [lista citazioni], chunk_count: N, generated_at: timestamp}"""
    fingerprint = {"refs": [], "chunk_count": 0, "generated_at": datetime.utcnow().isoformat()}
    seen_refs = set()
    all_chunk_ids = set()
    for slide in slides:
        ref = slide.get("normative_ref", "")
        if ref and ref not in seen_refs:
            fingerprint["refs"].append(ref)
            seen_refs.add(ref)
        for cid in slide.get("source_chunk_ids", []):
            all_chunk_ids.add(cid)
    fingerprint["chunk_count"] = len(all_chunk_ids)
    return fingerprint


async def run_pipeline(job_id: str, course_id: str):
    """Wrapper principale: acquisisce il semaforo e wrappa la pipeline in un timeout globale.
    Garantisce che un job bloccato non monopolizzi l'istanza indefinitamente."""
    async with _job_semaphore:
        try:
            await asyncio.wait_for(
                _run_pipeline_inner(job_id, course_id),
                timeout=PIPELINE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error("pipeline_timeout", job_id=job_id, timeout=PIPELINE_TIMEOUT_SECONDS)
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='failed', "
                "error_message='Pipeline timeout dopo 30 minuti' WHERE id=$1",
                job_id
            )
        except asyncio.CancelledError:
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='cancelled' WHERE id=$1", job_id
            )
        except Exception as e:
            logger.error("pipeline_failed", job_id=job_id, error=str(e))
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='failed', error_message=$1 WHERE id=$2",
                str(e)[:500], job_id
            )


async def _run_pipeline_inner(job_id: str, course_id: str):
    """Logica interna della pipeline, separata per gestione timeout."""
    db = get_pool()
    start_time = time.time()

    if get_shutdown_event().is_set():
        raise asyncio.CancelledError("Server in shutdown")

    # ═══ CARICAMENTO DATI DAL DB ═══
    course = dict(await db.fetchrow("SELECT * FROM courses WHERE id = $1", course_id))
    brand = dict(await db.fetchrow(
        "SELECT * FROM brand_presets WHERE id = $1", course["brand_preset_id"]
    ))

    # ═══ COSTRUZIONE INITIAL STATE PER LANGGRAPH ═══
    # Lo schema corrisponde ESATTAMENTE a NexusPipelineState in §05.2.
    # NON aggiungere campi non presenti nel TypedDict.
    initial_state = {
        "course_request": course,
        "brand_config": brand,
        "course_context": None,
        "pacing_plan": None,
        "completed_modules": [],
        "current_module_index": 0,
        "job_id": job_id,
        "errors": [],
    }

    await db.execute(
        "UPDATE generation_jobs SET status='research', started_at=NOW() WHERE id=$1",
        job_id
    )

    # Pipeline LangGraph — usa DATABASE_URL dalla config
    from app.config import DATABASE_URL
    pipeline = await create_pipeline(DATABASE_URL)
    result = await pipeline.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": job_id}}
    )

    all_slides = [s for m in result["completed_modules"] for s in m["slides"]]

    # ═══ SALVATAGGIO PRE-BUILD (crash-safe) ═══
    await db.execute(
        "UPDATE courses SET slide_contents_json = $1 WHERE id = $2",
        json.dumps(all_slides), course_id
    )

    # ═══ FINGERPRINT NORMATIVO per futuro Delta-Update ═══
    fingerprint = build_normative_fingerprint(all_slides)
    chunk_ids = list(set(
        cid for s in all_slides
        for cid in s.get("source_chunk_ids", [])
    ))
    await db.execute(
        "UPDATE courses SET normative_fingerprint=$1, "
        "source_chunk_ids=$2 WHERE id=$3",
        json.dumps(fingerprint), chunk_ids, course_id
    )

    await db.execute(
        "UPDATE generation_jobs SET status='building' WHERE id=$1", job_id
    )

    # ═══ IMAGE PRE-FETCH + DIAGRAM RENDERING ═══
    image_map = await prefetch_images(
        [SlideContent(**s) for s in all_slides], db
    )

    # Build PPTX + PDF (in thread separati, con memory check)
    builder = ProductionBuilder(brand)
    pptx_path, pdf_path, report = await builder.build(
        slides=[SlideContent(**s) for s in all_slides],
        course=course, job_id=job_id,
        ws_callback=send_ws_progress,
        image_map=image_map
    )

    elapsed = time.time() - start_time

    # Completamento
    await db.execute(
        "UPDATE courses SET pptx_path=$1, pdf_path=$2, status='completed' WHERE id=$3",
        str(pptx_path), str(pdf_path), course_id
    )
    await db.execute(
        "UPDATE generation_jobs SET status='completed', completed_at=NOW(), "
        "progress_percent=100 WHERE id=$1", job_id
    )

    # ═══ TELEMETRIA → audit_log ═══
    await db.execute(
        "INSERT INTO audit_log (action, entity_type, entity_id, details) "
        "VALUES ('pipeline_metrics', 'course', $1, $2)",
        course_id,
        json.dumps({
            "elapsed_seconds": round(elapsed, 1),
            "total_slides": len(all_slides),
            "images_resolved": len(image_map),
        })
    )

    logger.info("pipeline_completed",
                 job_id=job_id, slides=len(all_slides),
                 elapsed_seconds=round(elapsed, 1))
```

### 9.2 Recovery al Startup — Semplificata per v1.0

```python
async def recover_interrupted_jobs(pool):
    """v1.0: resetta tutti i job bloccati a 'failed'.
    La recovery intelligente con resume da checkpoint LangGraph è differita a v1.1."""
    result = await pool.execute("""
        UPDATE generation_jobs SET status='failed',
        error_message='Interrotto da restart server'
        WHERE status IN ('research', 'content', 'building')
    """)
    if result != "UPDATE 0":
        logger.warning("jobs_recovered_to_failed", result=result)
```

---

## §10 — API REST — Mappa Endpoint Completa

```
# ═══ AUTH ═══
POST   /api/auth/login                → {access_token, refresh_token}
POST   /api/auth/refresh              → {access_token}
GET    /api/users/me                  → User

# ═══ NORMATIVE ═══
GET    /api/regulations               → Regulation[] (paginato: ?page=1&per_page=20)
POST   /api/regulations/upload        → {regulation_id, chunks_count}
GET    /api/regulations/{id}/chunks   → NormativeChunk[] (paginato: ?page=1&per_page=50)
DELETE /api/regulations/{id}          → soft-delete: sets status='ABROGATA'

# ═══ CORSI ═══
POST   /api/courses                   → {course_id, job_id, queue_position}  (avvia pipeline)
GET    /api/courses                   → Course[] (paginato: ?page=1&per_page=20&status=completed&sort=created_at:desc)
GET    /api/courses/{id}              → Course (con fingerprint normativo)
POST   /api/courses/{id}/certify      → {approved_course_id}
GET    /api/courses/{id}/download/{format}  → file PPTX/PDF/ZIP (ZIP = PPTX + PDF in archivio)
DELETE /api/courses/{id}              → soft-delete: sets status='archived'

# ═══ BRANDING & CATALOGO ═══
GET    /api/brand-presets             → BrandPreset[]
GET    /api/catalog                   → COURSE_CATALOG (tipi corso disponibili)
GET    /api/dashboard/stats           → {courses_count, regulations_count, l2_count}

# ═══ ADMIN (solo ruolo admin) ═══
GET    /api/admin/metrics             → aggregazione metriche pipeline da audit_log

# ═══ HEALTH ═══
GET    /health                        → {status, database, disk_free_gb}

# ═══ WEBSOCKET ═══
WS     /ws/jobs/{job_id}?token=...    → streaming progress
```

### 10.1 Health Check Dettagliato

```python
@app.get("/health")
async def health():
    db_ok = False
    try:
        await app.state.db.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass

    disk_free_gb = shutil.disk_usage("/app/output").free / (1024**3)
    status = "ok" if db_ok and disk_free_gb > 1 else "degraded"
    return {
        "status": status,
        "database": "connected" if db_ok else "unreachable",
        "disk_free_gb": round(disk_free_gb, 1)
    }
```

### 10.2 Pagination Standard e Queue Position

```python
# POST /api/courses — con queue_position
@app.post("/api/courses")
async def create_course(req: CourseRequest, user=Depends(get_current_user)):
    pool = get_pool()

    # Calcola posizione in coda
    queued_count = await pool.fetchval(
        "SELECT COUNT(*) FROM generation_jobs WHERE status IN ('queued', 'research', 'content', 'building')"
    )

    # ... crea corso e job ...

    return CourseResponse(
        course_id=str(course_id),
        job_id=str(job_id),
        estimated_slides=pacing_plan.total_slides,
        estimated_minutes=estimated_time,
        queue_position=queued_count  # 0 = in esecuzione subito, 1+ = in coda
    )
```

### 10.3 Polling Fallback per WebSocket

Se il client perde la connessione WebSocket, il frontend fa polling su:

```
GET /api/courses/{id} → { status: "generating" | "completed" | "failed" }
```

Frontend: WebSocket primario + polling ogni 30 secondi come fallback.

---

## §11 — LOGGING STRUTTURATO

```python
# app/config.py (parziale)
import structlog

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )

logger = structlog.get_logger()
# Esempi:
# logger.info("research_completed", chunks=30, top_k=80, regulation_ids=["DLgs_81_08"])
# logger.error("llm_retry", attempt=2, error="429 rate limited")
# logger.warning("image_download_failed", slide=18, error="timeout")
# logger.warning("low_coverage_chunking", coverage=0.55, regulation_id="uuid-...")
# logger.info("memory_check_passed", available_mb=3200, estimated_mb=450, slides=300)
# logger.error("pipeline_timeout", job_id="...", timeout=1800)
# logger.info("chunk_deduplicated", hash="a1b2c3d4...")
```

---

## §12 — MANUTENZIONE: CLEANUP AUTOMATICO

### 12.1 Pulizia Image Cache (startup task)

```python
async def cleanup_old_images(pool):
    """Pulizia immagini non referenziate da più di 90 giorni con usage basso.
    Eseguire al startup o come cron job giornaliero."""
    old_images = await pool.fetch(
        "SELECT id, local_path FROM image_cache "
        "WHERE created_at < NOW() - INTERVAL '90 days' AND usage_count < 3"
    )
    for img in old_images:
        if img['local_path'] and os.path.exists(img['local_path']):
            os.remove(img['local_path'])
        await pool.execute("DELETE FROM image_cache WHERE id = $1", img['id'])
    if old_images:
        logger.info("image_cache_cleaned", removed=len(old_images))
```

---

## §13 — COURSE CATALOG — CONFIGURAZIONE COMPLETA

```python
# config/catalog_config.py
"""Catalogo dei tipi di corso generabili.
Ogni entry mappa un slug → normative richieste + parametri strutturali.
Gli slug in "regs" devono corrispondere a regulations.slug nel database.
Il Research Agent usa resolve_slugs_to_ids() per validarli prima della query RAG."""

COURSE_CATALOG = {
    "sicurezza_lavoratori_generale": {
        "title": "Formazione Generale Lavoratori",
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2011"],
        "min_hours": 4,
        "max_hours": 4,
        "default_modules": [
            "Concetti di rischio",
            "Prevenzione e protezione",
            "Organizzazione della prevenzione",
            "Diritti e doveri"
        ],
    },
    "sicurezza_lavoratori_specifica_basso": {
        "title": "Formazione Specifica Rischio Basso",
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2011"],
        "min_hours": 4,
        "max_hours": 4,
        "default_modules": [
            "Rischi specifici",
            "DPI",
            "Procedure di emergenza",
            "Segnaletica"
        ],
    },
    "primo_soccorso_gruppo_b_c": {
        "title": "Primo Soccorso Gruppi B e C",
        "regs": ["dlgs_81_08", "dm_388_2003"],
        "min_hours": 12,
        "max_hours": 12,
        "default_modules": [
            "Allertare il sistema di soccorso",
            "Riconoscere emergenza sanitaria",
            "Attuare interventi primo soccorso",
            "Conoscenze generali sui traumi",
            "Conoscenze generali patologie",
            "Acquisire capacità di intervento pratico"
        ],
    },
    "antincendio_livello_1": {
        "title": "Addetto Antincendio Livello 1",
        "regs": ["dlgs_81_08", "dm_02_09_2021"],
        "min_hours": 4,
        "max_hours": 4,
        "default_modules": [
            "Principi dell'incendio",
            "Prevenzione incendi",
            "Protezione antincendio",
            "Procedure operative"
        ],
    },
    "haccp_addetto": {
        "title": "Formazione HACCP Addetti",
        "regs": ["reg_ce_852_2004"],
        "min_hours": 4,
        "max_hours": 8,
        "regional": True,  # attiva filtro regionale nel Research Agent
        "default_modules": [
            "Principi HACCP",
            "Igiene degli alimenti",
            "Rischi biologici e chimici",
            "Autocontrollo e documentazione"
        ],
    },
    "preposti": {
        "title": "Formazione Preposti",
        "regs": ["dlgs_81_08", "accordo_stato_regioni_2011"],
        "min_hours": 8,
        "max_hours": 8,
        "default_modules": [
            "Principali soggetti del sistema di prevenzione",
            "Relazioni tra i vari soggetti",
            "Definizione e individuazione dei fattori di rischio",
            "Incidenti e infortuni mancati",
            "Tecniche di comunicazione e sensibilizzazione",
            "Valutazione dei rischi dell'azienda"
        ],
    },
}
```

---

## §14 — SVILUPPABILITÀ & CLAUDE CODE

### 14.1 Struttura Codebase

```
nexus/
├── app/
│   ├── main.py                    ← Entry point + CORS + rate limit + startup recovery + shutdown + set_pool
│   ├── config.py                  ← Settings, structlog, variabili d'ambiente
│   ├── models/
│   │   ├── core.py                ← Enum (TargetType, SlideDensity, SlideType, ChunkType)
│   │   ├── requests.py            ← CourseRequest, CourseResponse (con queue_position)
│   │   ├── knowledge.py           ← NormativeChunk, StylePattern
│   │   └── pipeline.py            ← SlideContent, ImageStrategy, ModuleSpec, PacingPlan, etc.
│   ├── agents/
│   │   ├── pipeline.py            ← NexusPipelineState (UNICO TypedDict), grafo LangGraph
│   │   ├── research_agent.py      ← Ricerca RAG + slug→UUID + pacing + chunk distribution + gate
│   │   ├── content_agent.py       ← Generazione testo con retry LLM + JSON parsing + circuit breaker
│   │   └── prompts.py             ← System prompts (Discente/Formatore) e user prompt templates
│   ├── services/
│   │   ├── dependencies.py        ← set_pool() / get_pool() — Dependency Injection per il pool asyncpg
│   │   ├── generation_service.py  ← Pipeline wrapper + semaforo + timeout globale + recovery + telemetria
│   │   ├── knowledge_repo.py      ← KnowledgeRepository (slug validation, search_chunks con JOIN regionale)
│   │   ├── ingestion_service.py   ← Parsing + chunking ibrido normalizzato + classificazione + embedding + dedup
│   │   ├── image_service.py       ← prefetch_images + render_diagram SVG→PNG + validazione integrità Pillow
│   │   ├── pacing_engine.py       ← PacingEngine completo con formula e distribuzione
│   │   ├── auth_service.py        ← JWT, bcrypt, password hashing (TOTP predisposto, non attivo)
│   │   └── certification_service.py ← Approvazione + StylePatternExtractor deterministico
│   ├── builders/
│   │   ├── production_builder.py  ← Orchestratore build (memory check + disk check + asyncio.to_thread)
│   │   ├── slide_builder.py       ← Build PPTX (sincrono, riceve image_map con path locali, fallback su immagini corrotte)
│   │   ├── pdf_builder.py         ← Build PDF WeasyPrint (sincrono, con template HTML strutturato)
│   │   └── pptx_validator.py      ← Validazione post-build
│   ├── api/
│   │   ├── dependencies.py        ← get_current_user (JWT + is_active check), require_role
│   │   ├── routes/                ← Endpoint REST (§10) con rate limiting, pagination, queue_position
│   │   └── websocket.py           ← WebSocket autenticato
│   └── db/
│       ├── migrations/001_initial.sql  ← Schema §03 (con indici GIN e UNIQUE content_hash)
│       ├── setup_roles.sql        ← Creazione ruolo nexus_app + blindatura audit_log
│       └── connection.py          ← Pool asyncpg (min 5, max 20) come nexus_app
├── assets/
│   ├── templates/nexus_master.pptx  ← BINARIO committato in Git (non generato da CI)
│   └── fonts/Montserrat/
├── config/catalog_config.py       ← COURSE_CATALOG completo con slug e normative
├── scripts/
│   ├── seed.py                    ← Admin + brand preset al primo avvio (usa DATABASE_ADMIN_URL)
│   ├── create_pptx_template.py
│   └── inspect_pptx_template.py
├── frontend/
├── docker-compose.yml
├── Dockerfile
├── .env.example                   ← Include DATABASE_ADMIN_URL e PIPELINE_TIMEOUT
├── CLAUDE.md
└── pyproject.toml
```

### 14.2 CLAUDE.md

```markdown
# CLAUDE.md — Nexus EduVault Engine v7.0

## Architettura
- Backend: FastAPI (Python 3.12) + LangGraph + PostgreSQL 16 + pgvector
- Frontend: Next.js 15 (App Router) + shadcn/ui + TailwindCSS 4
- AI: Claude Sonnet 4 (Anthropic) + Voyage AI (voyage-3)
- Auth: JWT custom + bcrypt (TOTP predisposto nello schema, non attivo in v1.0)
- Rate Limiting: slowapi
- Memory Check: psutil
- Dependency Injection: services/dependencies.py (set_pool/get_pool)

## Regole fondamentali
- Tutti i contratti tra moduli usano Pydantic BaseModel (v2) — vedi models/
- Un file per concetto. Non creare "utils.py"
- Type hints ovunque. Nessun `Any` tranne interfacce LangGraph
- Async per default. Sync solo per python-pptx, cairosvg, WeasyPrint → wrappati in asyncio.to_thread()
- Retry LLM con tenacity (3 tentativi, exponential backoff)
- structlog per tutto. Mai print() o logging.info()
- Un solo job alla volta (asyncio.Semaphore(1)). Job in eccesso in coda
- Pipeline wrappata in asyncio.wait_for(timeout=1800) — mai job infiniti
- CORS: mai wildcard. Usa FRONTEND_URL da .env
- Audit log: append-only a livello SQL (nexus_app non può DELETE/UPDATE)

## Vincolo python-pptx (ARCHITETTURALE)
python-pptx e lxml NON sono thread-safe. Semaphore(1) è un vincolo architetturale,
non solo di risorse. Non alzare MAI a Semaphore(2+) senza passare a un process pool
(multiprocessing) o Celery.

## Eccezione critica: LangGraph State
`NexusPipelineState` in `agents/pipeline.py` è l'UNICO TypedDict.
Usa `operator.add` come reducer per campi lista (completed_modules, errors).
Tutti gli altri contratti usano Pydantic. Non usare TypedDict altrove.
Validazione Pydantic all'ingresso/uscita di ogni nodo agente.

## Database
- Schema in db/migrations/001_initial.sql
- brand_presets PRIMA di courses (dipendenza FK)
- Trigger update_updated_at() su tutte le tabelle con updated_at
- COURSE_CATALOG usa slug → resolve_slugs_to_ids() PRIMA della query RAG
- Tabelle LangGraph (checkpoints, checkpoint_writes, checkpoint_migrations) — NON TOCCARE
- DOPO il primo avvio LangGraph: eseguire GRANT su tabelle checkpoint per nexus_app (vedi setup_roles.sql)
- DUE RUOLI: nexus_admin (owner) + nexus_app (applicazione, senza DELETE su audit_log)
- content_hash ha UNIQUE INDEX parziale (WHERE is_current = true) per deduplicazione chunk
- source_chunk_ids ha GIN INDEX per future query Delta-Update

## Pipeline di generazione
1. Research Agent: slug→UUID, RAG con top_k dinamico, gate minimo chunk, pacing con titoli dal COURSE_CATALOG, distribuzione chunk per keyword overlap (NON round-robin)
2. Content Agent: prompting modulo×modulo, retry JSON, retry LLM, circuit breaker (>50% fail → abort), body validator con troncamento soft
3. Salvataggio slide_contents_json + normative_fingerprint + source_chunk_ids PRIMA del build
4. Image Pre-Fetch: download async con Semaphore(5), validazione Pillow, SVG→PNG con cairosvg, cache DB
5. Memory check + disk check PRIMA del build
6. Production Builder: PPTX + PDF in asyncio.to_thread()
7. Cleanup: output/tmp_* + output/diagrams/ + output/images/ (file > 1 ora)
8. Telemetria: metriche salvate in audit_log (action='pipeline_metrics')

## StylePatternExtractor (anti-Model-Collapse)
- Estrae SOLO metadati strutturali (numeri, enum, liste brevi)
- MAI frasi intere, MAI testo normativo, MAI blocchi di contenuto
- Vedere models/knowledge.py → StylePattern

## Errori comuni da NON fare
- NON creare client Anthropic globali. Creare dentro la funzione call_llm()
- NON usare `print()` o `logging`. Solo `structlog.get_logger()`
- NON usare `requests`. Solo `httpx` async
- NON mettere logica di business nelle route API. Le route chiamano i service
- NON fare `from app.main import app` nei service (import circolare)
- NON usare TypedDict fuori da `agents/pipeline.py`
- Il pool è accessibile via `from services.dependencies import get_pool`. MAI importarlo da main.py
- NON inserire immagini in PPTX senza try/except. Se fallisce → placeholder testuale

## Pattern di test per ogni sprint
Ogni sprint deve avere almeno 3 test:
1. Test del contratto: il modello Pydantic accetta input valido, rifiuta input invalido
2. Test della funzione core: con input mockato, la funzione restituisce output nel formato atteso
3. Test di integrazione: l'endpoint API restituisce il codice HTTP corretto

## Import path canonici
from app.models.core import TargetType, SlideDensity, SlideType, ChunkType
from app.models.requests import CourseRequest, CourseResponse
from app.models.knowledge import NormativeChunk, StylePattern
from app.models.pipeline import SlideContent, ModuleContent, PacingPlan
from app.services.auth_service import create_access_token, decode_token
from app.services.dependencies import get_pool
from app.services.knowledge_repo import KnowledgeRepository
from app.services.pacing_engine import PacingEngine
from config.catalog_config import COURSE_CATALOG

## Feature differite a v1.1
- TOTP 2FA: schema DB pronto (totp_secret), flusso non implementato
- Delta-Update: fingerprint salvato, logica di diff non implementata
- Recovery intelligente: resetta a failed in v1.0, resume da checkpoint in v1.1

## Ordine di implementazione dei file per Sprint
Sprint 0: config.py → services/dependencies.py → db/connection.py → main.py → scripts/seed.py
Sprint 1: db/migrations/001_initial.sql → db/setup_roles.sql → models/* → services/auth_service.py → api/dependencies.py → api/routes/auth.py
Sprint 2: config/catalog_config.py → services/ingestion_service.py → services/knowledge_repo.py
Sprint 3: services/pacing_engine.py → agents/prompts.py → agents/pipeline.py → agents/research_agent.py → agents/content_agent.py
Sprint 4: services/image_service.py → builders/slide_builder.py → builders/pdf_builder.py → builders/production_builder.py → builders/pptx_validator.py
Sprint 5: services/generation_service.py → api/routes/courses.py → api/websocket.py → frontend/
Sprint 6: services/certification_service.py → api/routes/admin.py → integrazione end-to-end → testing → deploy
```

---

## §15 — CHECKLIST DI VALIDAZIONE PRE-COMMIT

### Sprint 0 — Prima del primo `git commit`

```
[  ] Schema SQL: brand_presets PRIMA di courses
[  ] Schema SQL: trigger update_updated_at() su users, regulations, courses, brand_presets
[  ] Schema SQL: commento su tabelle LangGraph
[  ] Schema SQL: regulations.slug VARCHAR(50) UNIQUE + indice
[  ] Schema SQL: approved_courses.source_course_id UUID REFERENCES courses(id)
[  ] Schema SQL: courses NON ha regulation_snapshot (non implementata in v1.0)
[  ] Schema SQL: image_cache NON ha relevance_score (rimossa in v7.0)
[  ] Schema SQL: courses.status include 'archived' per soft-delete
[  ] Schema SQL: idx_chunks_content_hash UNIQUE parziale (WHERE is_current = true)
[  ] Schema SQL: idx_courses_chunk_ids GIN
[  ] docker-compose NON espone porta 5432
[  ] docker-compose usa nexus_admin come POSTGRES_USER
[  ] Dockerfile include fonts-open-sans + Montserrat (.ttf in assets/fonts/)
[  ] main.py include CORSMiddleware con FRONTEND_URL (non wildcard)
[  ] main.py include slowapi Limiter
[  ] main.py include _shutdown_event + graceful shutdown
[  ] main.py include connection pool + set_pool() + startup recovery
[  ] services/dependencies.py con set_pool() / get_pool()
[  ] db/connection.py con asyncpg pool (min 5, max 20) come nexus_app
[  ] scripts/seed.py usa DATABASE_ADMIN_URL (non DATABASE_URL)
[  ] scripts/create_pptx_template.py e inspect_pptx_template.py presenti
[  ] config/catalog_config.py con COURSE_CATALOG completo
[  ] CLAUDE.md include tutte le regole v7.0
[  ] structlog + tenacity + pdfplumber + Pillow + psutil + slowapi + bcrypt + pyotp in pyproject.toml
[  ] .env.example completo con FRONTEND_URL + DATABASE_ADMIN_URL + PIPELINE_TIMEOUT + due password PostgreSQL
```

### Sprint 1 — Database + Auth + Modelli

```
[  ] db/migrations/001_initial.sql eseguito come nexus_admin
[  ] db/setup_roles.sql eseguito: nexus_app creato, REVOKE su audit_log
[  ] models/core.py: tutti gli Enum
[  ] models/requests.py: CourseRequest, CourseResponse (con queue_position)
[  ] models/knowledge.py: NormativeChunk, StylePattern (con commento anti-avvelenamento)
[  ] models/pipeline.py: SlideContent, ImageStrategy (SVG, non Mermaid), ModuleSpec, PacingPlan, ModuleContent, CourseContext, GenerationReport
[  ] services/auth_service.py: JWT, bcrypt (TOTP commentato per v1.1)
[  ] api/dependencies.py: get_current_user con check is_active
[  ] api/routes/auth.py: login, refresh (con check is_active), me
```

### Sprint 2 — Knowledge Base

```
[  ] config/catalog_config.py con COURSE_CATALOG completo
[  ] ingestion_service.py: parsing (pdfplumber), chunking IBRIDO con coverage normalizzata + overlap fallback + deduplicazione content_hash
[  ] ART_PATTERN corretto con (?:-(?:bis|ter|quater|quinquies|...))
[  ] ALLEGATO_PATTERN presente per catturare allegati
[  ] normalize_for_coverage() presente
[  ] chunk_regulation() con coverage check normalizzato e soglia 70%
[  ] chunk_unstructured_regulation() con overlap di 1 frase
[  ] voyage_embed_with_retry() definita (wrappa embed_batch per singolo testo)
[  ] Deduplicazione via content_hash prima dell'INSERT
[  ] resolve_slugs_to_ids() alza ValueError se slug mancanti
[  ] search_chunks() usa JOIN su regulations.region (non tag)
[  ] get_style_patterns() usa ORDER BY certified_at DESC
[  ] Testato con DM 388/2003 (documento piccolo) prima del D.Lgs 81/08
```

### Sprint 3 — Agenti + PacingEngine

```
[  ] PacingEngine completo con SECONDS_PER_TYPE, DISTRIBUTION, DENSITY_MULTIPLIER
[  ] NexusPipelineState usa Annotated[list[dict], operator.add]
[  ] distribute_chunks_to_modules() definita e testata
[  ] Research Agent: usa get_pool() per il pool (NON variabile globale)
[  ] Research Agent: top_k dinamico = max(30, duration_hours * 10)
[  ] Research Agent: gate RAG → ValueError se < 5 chunk
[  ] Content Agent: prompts.py contiene system prompt Discente + Formatore (con istruzione SVG per diagrammi)
[  ] Content Agent: build_module_prompt differenziato per target Formatore
[  ] Content Agent: call_llm() con tenacity retry (3 tentativi, exponential backoff 5-60s)
[  ] Content Agent: parsing JSON con retry correttivo (max 2 tentativi)
[  ] Content Agent: validazione SlideContent per ogni slide
[  ] Content Agent: circuit breaker — >50% moduli falliti → RuntimeError
[  ] GRANT su tabelle LangGraph (checkpoints, checkpoint_writes, checkpoint_migrations) per nexus_app — eseguire DOPO il primo avvio del backend
```

### Sprint 4 — Production Builder

```
[  ] Template PPTX generato e calibrato con PowerPoint (4-6 ore LAVORO UMANO)
[  ] image_service.py: prefetch_images() con Semaphore(5)
[  ] image_service.py: timeout 10s, validazione integrità Pillow (verify()), conversione PNG, cache DB
[  ] image_service.py: render_diagram() per SVG→PNG con cairosvg
[  ] SlideBuilder riceve image_map con path locali, MAI URL
[  ] SlideBuilder: try/except su inserimento immagine, fallback a placeholder testuale
[  ] pdf_builder.py: template HTML strutturato con WeasyPrint
[  ] ProductionBuilder: check_memory_before_build() con psutil
[  ] ProductionBuilder: check_disk_before_build()
[  ] ProductionBuilder usa asyncio.to_thread() per build, validate, pdf
[  ] _cleanup_tmp() integrata
```

### Sprint 5A — Orchestrazione Backend

```
[  ] generation_service.py: asyncio.wait_for(timeout=PIPELINE_TIMEOUT)
[  ] generation_service.py: semaforo asyncio.Semaphore(1)
[  ] generation_service.py: usa get_shutdown_event() da dependencies.py (NON creare evento locale)
[  ] generation_service.py: build_normative_fingerprint() definita
[  ] generation_service.py: salva normative_fingerprint + source_chunk_ids PRIMA del build
[  ] generation_service.py: telemetria pipeline_metrics in audit_log
[  ] generation_service.py: recovery semplificata (reset a failed)
[  ] api/routes/courses.py: queue_position calcolato
[  ] api/websocket.py: WebSocket autenticato con JWT
```

### Sprint 5B — Frontend

```
[  ] Frontend: wizard 6 step con CourseRequest
[  ] Frontend: dashboard corsi con stato + download
[  ] Frontend: WebSocket progress primario
[  ] Frontend: polling fallback 30s su GET /api/courses/{id}
[  ] Frontend: login + refresh token flow
```

### Pre-Deploy

```
[  ] WebSocket autenticato con JWT
[  ] structlog configurato su tutti i moduli
[  ] Audit log append-only (verificare con: tentare DELETE come nexus_app → deve fallire)
[  ] Rate limiting attivo su tutti gli endpoint critici
[  ] Pagination funzionante su /api/courses e /api/regulations
[  ] Soft-delete funzionante (DELETE → status='archived'/'ABROGATA')
[  ] Health check dettagliato (/health → DB + disco)
[  ] Recovery testata (restart server → job bloccati diventano failed)
[  ] Backup automatico (snapshot VPS + pg_dump + sync asset)
[  ] Endpoint REST conformi a §10
[  ] certification_service.py: StylePatternExtractor deterministico testato
[  ] cleanup_old_images() schedulata
[  ] api/routes/admin.py: GET /api/admin/metrics funzionante
```

---

## §16 — PIANO DI SPRINT (OTTIMIZZATO PER CLAUDE CODE)

| Sprint | Focus | Deliverable | Checklist | Sezioni Blueprint |
|---|---|---|---|---|
| 0 | Infrastruttura | docker-compose up → seed.py → /health verde → login JWT | §15 Sprint 0 | §02, §03 |
| 1 | Database + Auth + Modelli | Schema SQL + ruoli + modelli Pydantic + JWT (no TOTP) | §15 Sprint 1 | §03, §04, §08 |
| 2 | Knowledge Base + Catalog | Ingestion pipeline completa + COURSE_CATALOG + RAG funzionante | §15 Sprint 2 | §06, §13 |
| 3 | Agenti + PacingEngine | LangGraph pipeline + Research/Content Agent + circuit breaker + GRANT tabelle LangGraph | §15 Sprint 3 | §05, §06B |
| 4 | Production Builder | PPTX + PDF + image/diagram + memory check (test con slide mock) | §15 Sprint 4 | §07 |
| 5A | Orchestrazione Backend | generation_service.py + timeout + semaforo + WebSocket server + endpoints courses/ | §15 Sprint 5A | §09, §10 |
| 5B | Frontend | Wizard 6 step + dashboard + WebSocket client + polling fallback 30s | §15 Sprint 5B | §10 |
| 6 | Integrazione + Deploy | End-to-end + certification + audit + metriche + testing | §15 Pre-Deploy | §12, §14 |

**Sequenza Sprint 0 (primo avvio):**

```bash
1. docker-compose up -d
2. docker exec -it nexus-postgres-1 psql -U nexus_admin -d nexus -f /path/to/001_initial.sql
3. docker exec -it nexus-postgres-1 psql -U nexus_admin -d nexus -f /path/to/setup_roles.sql
4. docker exec -it nexus-backend-1 python scripts/seed.py
5. curl http://localhost:8000/health → {"status": "ok", "database": "connected", "disk_free_gb": ...}
6. curl -X POST http://localhost:8000/api/auth/login -d '{"email":"admin@corsi8108.it","password":"CHANGE_ME"}' → JWT
```

**Regole per Claude Code:**

1. **Una sessione per sprint.** Claude Code perde coerenza dopo ~15 file. Uno sprint, un commit, poi nuova sessione. Prompt template per ogni sessione:
   ```
   Leggi il CLAUDE.md. Implementa lo Sprint [N] seguendo la Blueprint §[sezioni].
   File da creare in ordine: [lista da CLAUDE.md].
   Per ogni file: implementa, poi scrivi i test in tests/test_[nome].py.
   Non procedere al file successivo finché i test del precedente non passano.
   ```

2. **CLAUDE.md è il file più importante.** Claude Code lo legge per primo e lo usa come bussola. Committarlo come primo file del progetto.

3. **Testare il chunking con un PDF reale nello Sprint 2.** Il DM 388/2003 (4 pagine) è il test ideale prima del D.Lgs 81/08.

4. **Il template PPTX è lavoro umano.** Non delegare la calibrazione visiva a Claude Code. Creare il template in PowerPoint, versionarlo come binario in Git, poi dare a Claude Code le coordinate esatte via `inspect_pptx_template.py`.

5. **Ogni funzione chiamata nel codice è definita in questo documento.** Se Claude Code non trova una funzione qui, non deve inventarla — deve segnalare il gap.

---

**Fine del documento.**

**NEXUS EDUVAULT — ABSOLUTE MASTER ARCHITECTURAL BLUEPRINT (SUPREME PRODUCTION READY v7.0)**

*Questo documento è l'unica fonte di verità. Contiene organicamente tutti i contratti Pydantic completi (con NexusPipelineState privo di campi vestigiali), la dependency injection via set_pool/get_pool, il timeout globale pipeline con asyncio.wait_for, il circuit breaker nel Content Agent, il COURSE_CATALOG con 6 tipi corso (incluso HACCP con validazione regionale), la query RAG con JOIN regionale NULL-safe, il chunking con coverage normalizzata e overlap, la deduplicazione via content_hash, la distribuzione chunk per keyword overlap con ribilanciamento min+max, il body validator con troncamento soft, la validazione integrità immagini con Pillow, il rendering SVG→PNG con cairosvg, il PDF builder con template strutturato, il build_normative_fingerprint, la costruzione esplicita di initial_state, get_job_progress() definita, il WebSocket con ownership check, il prompt differenziato per target Formatore, la revoca implicita JWT con check is_active, la telemetria pipeline via audit_log, la recovery semplificata, lo shutdown event condiviso via dependencies.py, la pulizia completa dei file temporanei, e il piano di sprint ottimizzato per Claude Code (con Sprint 5 separato in backend/frontend). Non esistono documenti supplementari da consultare.*
