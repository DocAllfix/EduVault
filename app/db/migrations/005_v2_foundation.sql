-- ═══════════════════════════════════════════════
-- Migration 005 — v2 foundation (D1..D10 plan, FASE 0)
-- Crea 7 tabelle nuove richieste dal refactor v2 (RAG+Graph universale,
-- catalogo cliente in DB, image library curata, chat Studio, badge UI).
--
-- VINCOLI:
--   - Idempotente (IF NOT EXISTS ovunque). Riapplicarla è no-op.
--   - NO DROP di tabelle v1: convivono con v1 dietro feature-flag finché
--     la promozione A/B per famiglia di corsi (D10) non le rimuove.
--   - Ogni componente "fail-silenzioso-pericoloso" ha colonna `source` che
--     traccia provenienza (VAA-b). Edge LLM-verified e quality checks con
--     enum esplicito.
--   - GRANT a nexus_app al fondo, identico pattern 001_initial.
-- ═══════════════════════════════════════════════

-- ────────────────────────────────────────────
-- D8 — CATALOGO CORSI CLIENTE (sostituisce config/catalog_config.py dietro flag)
-- Sistema propone (scraping), esperto valida (approved_at). Senza approved_at
-- l'entry NON è disponibile per la generazione (gate VAA-c).
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS course_type_catalog (
    slug VARCHAR(80) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    hours NUMERIC(4,1) NOT NULL,
    target VARCHAR(40) NOT NULL
        CHECK (target IN ('lavoratori', 'preposti', 'dirigenti', 'rspp', 'aspp',
                          'rls', 'datore_lavoro', 'formatore', 'primo_soccorso',
                          'antincendio', 'haccp', 'coordinatore_cantieri',
                          'pes_pav', 'generale')),
    regulation_slugs TEXT[] NOT NULL DEFAULT '{}',
    regional BOOLEAN DEFAULT false,
    source VARCHAR(20) NOT NULL DEFAULT 'scraped'
        CHECK (source IN ('scraped', 'manual', 'imported_v1')),
    source_url VARCHAR(500),
    scraped_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_catalog_approved ON course_type_catalog(approved_at)
    WHERE approved_at IS NOT NULL;
DROP TRIGGER IF EXISTS trg_catalog_updated ON course_type_catalog;
CREATE TRIGGER trg_catalog_updated BEFORE UPDATE ON course_type_catalog
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE IF NOT EXISTS course_type_modules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_type_slug VARCHAR(80) NOT NULL
        REFERENCES course_type_catalog(slug) ON DELETE CASCADE,
    ordinal INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    normative_refs TEXT[] DEFAULT '{}',
    source VARCHAR(20) NOT NULL DEFAULT 'scraped'
        CHECK (source IN ('scraped', 'manual', 'imported_v1')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (course_type_slug, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_modules_course_type ON course_type_modules(course_type_slug);

-- ────────────────────────────────────────────
-- D1 — KNOWLEDGE GRAPH: edge-table chunk → chunk con provenienza tracciata.
-- Edge `deterministic` da regex/struttura (peso 1.0, sempre attendibili).
-- Edge `llm_verified` da LLM SOLO se gate verifica programmatica passata
-- (sovrapposizione lessicale Jaccard ≥ 0.15 o ref normativo condiviso).
-- Filtrabile per source: nei test A/B si può escludere llm_verified.
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regulation_chunk_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    src_chunk_id UUID NOT NULL REFERENCES regulation_chunks(id) ON DELETE CASCADE,
    dst_chunk_id UUID NOT NULL REFERENCES regulation_chunks(id) ON DELETE CASCADE,
    kind VARCHAR(30) NOT NULL
        CHECK (kind IN ('cita', 'modifica', 'attua', 'e_definito_da',
                        'gerarchico_parent', 'gerarchico_sibling')),
    weight NUMERIC(3,2) NOT NULL DEFAULT 1.0
        CHECK (weight > 0 AND weight <= 1.0),
    source VARCHAR(20) NOT NULL
        CHECK (source IN ('deterministic', 'llm_verified')),
    extraction_context JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (src_chunk_id, dst_chunk_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_edges_src_kind ON regulation_chunk_edges(src_chunk_id, kind);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON regulation_chunk_edges(dst_chunk_id);
CREATE INDEX IF NOT EXISTS idx_edges_source ON regulation_chunk_edges(source);

-- ────────────────────────────────────────────
-- D4 — IMAGE LIBRARY LOCALE (sostituisce image_cache opportunistica).
-- Seeded da Wikimedia/Openverse (CC-0 / CC-BY), Pexels solo web-runtime fallback.
-- Embedding multimodale Voyage 1024-dim per ricerca semantica.
-- Attribution obbligatoria per CC-BY (slide credits finale del corso).
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS image_library (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path VARCHAR(500) NOT NULL UNIQUE,
    tags TEXT[] NOT NULL DEFAULT '{}',
    embedding VECTOR(1024),
    source VARCHAR(30) NOT NULL
        CHECK (source IN ('wikimedia', 'openverse', 'iso7010', 'demo_seed',
                          'manual_upload', 'web_promoted')),
    license VARCHAR(50),
    attribution VARCHAR(500),
    source_url VARCHAR(500),
    width INT,
    height INT,
    bytes INT,
    usage_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_image_library_tags ON image_library USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_image_library_embedding ON image_library
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_image_library_source ON image_library(source);
DROP TRIGGER IF EXISTS trg_image_library_updated ON image_library;
CREATE TRIGGER trg_image_library_updated BEFORE UPDATE ON image_library
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ────────────────────────────────────────────
-- D7 — CHAT IN COURSE STUDIO (conversazioni + messaggi persistiti in DB).
-- Una conversation per corso (storia continua cross-sessione, non scope client).
-- Messages con role enum esteso che include 'tool' per il futuro F2 (tool-use).
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_course ON conversations(course_id);
DROP TRIGGER IF EXISTS trg_conversations_updated ON conversations;
CREATE TRIGGER trg_conversations_updated BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL
        CHECK (role IN ('user', 'assistant', 'tool', 'system')),
    content TEXT NOT NULL,
    slide_index INT,
    tool_calls JSONB,
    tool_call_id VARCHAR(100),
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);

-- ────────────────────────────────────────────
-- D9 — BADGE UI "SLIDE PROBLEMATICHE" (issues persistite, ricomputate su edit).
-- Issue_type lista chiusa, severity classifica visibilità (warning/error nel badge).
-- Ricomputata da slide_quality_service.compute_slide_issues su edit / rebuild.
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS slide_quality_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    slide_index INT NOT NULL,
    issue_type VARCHAR(50) NOT NULL
        CHECK (issue_type IN (
            'image_placeholder',
            'quiz_no_options',
            'notes_too_short',
            'diagram_branded_fallback',
            'module_underpopulated',
            'module_corpus_thin',
            'image_overused_in_module',
            'title_near_duplicate_in_module'
        )),
    severity VARCHAR(10) NOT NULL
        CHECK (severity IN ('info', 'warning', 'error')),
    context JSONB,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quality_course ON slide_quality_checks(course_id, slide_index);
CREATE INDEX IF NOT EXISTS idx_quality_issue ON slide_quality_checks(issue_type);

-- ────────────────────────────────────────────
-- D3 — SCHELETRO NARRATIVO (sotto-temi validati 1-click PRIMA della materializzazione).
-- Persistito come JSONB su courses (mai cancellato: traceability dopo approval).
-- Status="skeleton_pending" è una nuova transizione di stato; sotto, ci aggiungiamo
-- solo la colonna (nessun touch alle FK).
-- ────────────────────────────────────────────
ALTER TABLE courses ADD COLUMN IF NOT EXISTS module_skeletons_json JSONB;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS skeleton_approved_at TIMESTAMPTZ;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS skeleton_approved_by UUID REFERENCES users(id);

-- ────────────────────────────────────────────
-- GRANT a nexus_app (pattern identico a 001_initial.sql) — CONDIZIONALE.
-- In produzione Railway l'app gira come nexus_admin (owner) e il ruolo
-- nexus_app NON esiste (deployment single-role). Lo statement GRANT
-- esplicito su un ruolo inesistente farebbe fallire l'INTERA migrazione
-- (rollback atomico). Lo rendiamo idempotente: esegui i GRANT solo se il
-- ruolo esiste davvero, così la 005 funziona sia in dev (2 ruoli) sia in
-- prod (solo nexus_admin). VAA: non assumere lo stato, verificalo.
-- ────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON
            course_type_catalog,
            course_type_modules,
            regulation_chunk_edges,
            image_library,
            conversations,
            messages,
            slide_quality_checks
        TO nexus_app;
    END IF;
END
$$;

-- Verifica post-apply (a mano via psql/proxy):
--   SELECT table_name FROM information_schema.tables
--     WHERE table_schema='public' AND table_name IN
--       ('course_type_catalog','course_type_modules','regulation_chunk_edges',
--        'image_library','conversations','messages','slide_quality_checks');
--   → 7 righe.
--   SELECT column_name FROM information_schema.columns
--     WHERE table_name='courses' AND column_name LIKE 'skeleton%' OR column_name='module_skeletons_json';
--   → 3 righe.
