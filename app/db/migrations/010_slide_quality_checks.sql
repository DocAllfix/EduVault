-- 010_slide_quality_checks.sql
--
-- F4 D9 Slide Quality Checks (analista sign-off 2026-05-31 post-H8b rollback):
-- tabella per persistere issue rilevati su slide generate, esposti via API
-- a frontend Course Studio per badge slide problematiche (decisione D9 VAA-c:
-- "Visibilità sì, coercizione no" — NON blocca download PPTX/PDF, solo segnala).
--
-- Trigger di ricomputo: ogni rebuild PPTX o edit slide via studio_service ->
-- service slide_quality_service compute_slide_issues() ricalcola da
-- slide_contents_json del corso, sovrascrive righe per (course_id, slide_index).
--
-- Schema:
--   - course_id UUID FK courses(id) ON DELETE CASCADE: invalidazione automatica
--     quando il corso viene cancellato
--   - slide_index INT NOT NULL: 0-based index nella lista slide del corso
--   - issue_type VARCHAR(64) NOT NULL: uno dei 11 tipi (lista chiusa, vedi
--     slide_quality_service.ISSUE_TYPES)
--   - severity VARCHAR(16) NOT NULL: 'info' | 'warning' | 'error'
--   - context JSONB: dati extra per tooltip frontend (counts, slugs, etc.)
--   - computed_at TIMESTAMPTZ DEFAULT now(): traceability ricomputo
--
-- Indice composto (course_id, slide_index): query frontend filtra per corso +
-- legge tutte le issue per slide. (course_id, issue_type) per dashboard
-- summary "quanti corsi hanno N hallucination warnings".
--
-- Idempotente: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS slide_quality_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    slide_index INT NOT NULL,
    module_index INT,
    issue_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    context JSONB,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabella poteva esistere preesistente da migration 005 senza module_index.
-- ALTER TABLE ADD COLUMN IF NOT EXISTS rende la migration vera idempotente:
-- esegue solo se la colonna manca.
ALTER TABLE slide_quality_checks
    ADD COLUMN IF NOT EXISTS module_index INT;

CREATE INDEX IF NOT EXISTS idx_slide_quality_course_slide
    ON slide_quality_checks(course_id, slide_index);

CREATE INDEX IF NOT EXISTS idx_slide_quality_course_type
    ON slide_quality_checks(course_id, issue_type);

CREATE INDEX IF NOT EXISTS idx_slide_quality_severity
    ON slide_quality_checks(course_id, severity)
    WHERE severity = 'error';

-- Verifica post-applicazione (manuale via psql/proxy):
--
--   SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'slide_quality_checks'
--   ORDER BY ordinal_position;
--   -- atteso: 7 colonne
--
--   SELECT indexname FROM pg_indexes WHERE tablename = 'slide_quality_checks';
--   -- atteso: 3 indici + pkey
