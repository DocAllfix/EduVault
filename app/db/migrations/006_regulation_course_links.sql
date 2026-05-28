-- =========================================================================
-- Migration 006 - v2 regulation <-> course_type_catalog link table
--
-- Materializza la relazione N:M tra normative e tipi di corso del catalogo,
-- visibile in UI (sia dalla normativa "quali corsi la usano" sia dal corso
-- "quali normative servono"). Sostituisce la lista hardcoded `regs` di
-- config/catalog_config.py (sotto flag v2_catalog_from_db).
--
-- Provenienza tracciata (VAA-b): ogni link ha `source` che dice se l'ha
-- popolato (a) lo script di seed dal catalog draft, (b) l'admin a mano da UI,
-- (c) l'automatismo di rimappatura 2016->2025 / 1998->2021 con conferma.
--
-- Idempotente: IF NOT EXISTS, GRANT condizionale (nexus_app assente in prod).
-- =========================================================================

CREATE TABLE IF NOT EXISTS regulation_course_type_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    regulation_slug VARCHAR(50) NOT NULL,
    course_type_slug VARCHAR(80) NOT NULL
        REFERENCES course_type_catalog(slug) ON DELETE CASCADE,
    -- Provenienza dell'associazione (VAA-b): da dove arriva questo link?
    -- Valori:
    --   'scrape'    = dedotto automaticamente dallo scraping del sito cliente
    --                 (i riferimenti normativi citati nella pagina corso)
    --   'remap'     = rimappato automaticamente (es. 7/7/2016 -> 2025) con
    --                 conferma admin in UI
    --   'manual'    = aggiunto manualmente dall'admin nella UI
    --   'imported_v1' = ereditato dalla lista hardcoded di catalog_config.py
    source VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (source IN ('scrape', 'remap', 'manual', 'imported_v1')),
    -- Note libere dell'admin per spiegare scelte non ovvie (es. "L'Accordo
    -- 2016 sul sito e' obsoleto, il cliente ha adottato il 2025 dal 22/05/2026").
    notes TEXT,
    -- Audit: chi e quando ha creato/approvato il link.
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES users(id),
    -- Vincolo: una sola associazione (regulation_slug, course_type_slug).
    UNIQUE (regulation_slug, course_type_slug)
);

CREATE INDEX IF NOT EXISTS idx_reg_course_links_reg
    ON regulation_course_type_links(regulation_slug);
CREATE INDEX IF NOT EXISTS idx_reg_course_links_course
    ON regulation_course_type_links(course_type_slug);
CREATE INDEX IF NOT EXISTS idx_reg_course_links_source
    ON regulation_course_type_links(source);

-- GRANT condizionale (nexus_app non esiste in prod Railway, idem migrazione 005).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON regulation_course_type_links TO nexus_app;
    END IF;
END
$$;

-- Verifica post-apply (da psql/proxy):
--   SELECT count(*) FROM regulation_course_type_links;  -- 0 inizialmente
--   \d regulation_course_type_links                      -- struttura visibile
