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
-- audio_manifest_path: GAP-3 v3.0 — path manifest delle tracce audio (FAD).
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
    audio_manifest_path VARCHAR(500),
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
-- TRACCE AUDIO (narrazione FAD per ogni slide)
-- GAP-3 v3.0 — generate via edge-tts (OPT-1), durata calcolata con mutagen.
-- duration_seconds in DECIMAL(6,2): fino a 9999.99 secondi (~166 minuti) per slide.
-- ────────────────────────────────────────────
CREATE TABLE audio_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    slide_index INT NOT NULL,
    narration_text TEXT NOT NULL,
    audio_path VARCHAR(500),
    duration_seconds DECIMAL(6,2),
    voice VARCHAR(50) DEFAULT 'it-IT-DiegoNeural',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audio_course ON audio_tracks(course_id);

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
