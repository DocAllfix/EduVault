-- 009_regulations_effective_until.sql
--
-- D-161 (analista sign-off 2026-05-30 post sample-read M0 PPTX ANT L1 post-B4):
-- tracciamento vigenza regulations universale + override pedagogico per-corso.
--
-- Patologia osservata (PPTX `ANT_L1_0dfe39ad.pptx` sample-read):
--   `accordo_stato_regioni_2011` marcato status='VIGENTE' ma titolo dichiara
--   "(storico)". Effettivamente abrogato dall'Accordo Stato-Regioni del
--   17/04/2025 (GU n. 119 del 24/05/2025) — regime transitorio 12 mesi fino al
--   2026-05-24, scaduto da 6 giorni alla data di questa migration.
--
-- Schema (analista raffinato vs is_abrogated BOOL):
--   - `effective_until DATE NULL`: data fino a cui il regulation e' applicabile
--     come fonte normativa. NULL = vigente indefinito. Valorizzato = vigente
--     fino a data (utile anche per direttive UE con cessazione programmata
--     futura). Filtro retrieval default: r.effective_until IS NULL OR > now().
--   - `abrogated_by_id UUID FK REFERENCES regulations(id)`: catena di
--     succession. ON DELETE: no cascade (preserva storico se la regulation
--     successore venisse rimossa per qualunque motivo).
--   - `courses.include_abrogated_for_pedagogy BOOL NOT NULL DEFAULT false`:
--     override per-corso (es. "corso evoluzione normativa 2011-2025"). Default
--     false = principio di sicurezza ("mai mostrare abrogata se non esplicitato").
--
-- Filtro retrieval (post-migration, in codice):
--   - `knowledge_repo.resolve_slugs_to_ids` + `search_chunks` ricevono
--     `include_abrogated: bool = False`, clause SQL:
--     `($N::bool OR r.effective_until IS NULL OR r.effective_until > now())`.
--   - `retrieval_v2.recall_hybrid` propaga a search_chunks E al BM25 corpus
--     load (lezione D-168: BM25 compensa silenziosamente se filtro manca).
--
-- Backfill (separato, in `scripts/backfill_accordo_2011.py` gitignored):
--   UPDATE accordo_stato_regioni_2011 SET effective_until='2026-05-24',
--          abrogated_by_id=(SELECT id FROM regulations WHERE
--                           slug='accordo_stato_regioni_2025')
--   Data 2026-05-24 = fine regime transitorio 12 mesi (24/05/2025 + 12m),
--   verificata via doppia fonte istituzionale (GU n. 119 + Artser).
--
-- Idempotente:
--   - ADD COLUMN IF NOT EXISTS sulle 3 colonne.
--   - CREATE INDEX IF NOT EXISTS sull'indice parziale.
--   - Backfill UPDATE su slug specifico (no DELETE/INSERT, ri-eseguibile).

ALTER TABLE regulations
    ADD COLUMN IF NOT EXISTS effective_until DATE NULL,
    ADD COLUMN IF NOT EXISTS abrogated_by_id UUID NULL REFERENCES regulations(id);

CREATE INDEX IF NOT EXISTS idx_regulations_effective_until
    ON regulations(effective_until)
    WHERE effective_until IS NOT NULL;

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS include_abrogated_for_pedagogy BOOLEAN NOT NULL DEFAULT false;

-- Verifica post-applicazione (manuale via psql/proxy):
--
--   -- Schema check
--   SELECT column_name, data_type, is_nullable
--   FROM information_schema.columns
--   WHERE table_name = 'regulations'
--     AND column_name IN ('effective_until', 'abrogated_by_id');
--   -- atteso: 2 righe
--
--   SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns
--   WHERE table_name = 'courses'
--     AND column_name = 'include_abrogated_for_pedagogy';
--   -- atteso: 1 riga, default = false
--
--   -- Backfill check (post backfill_accordo_2011.py)
--   SELECT slug, status, effective_until, abrogated_by_id
--   FROM regulations
--   WHERE slug IN ('accordo_stato_regioni_2011', 'accordo_stato_regioni_2025');
--   -- atteso accordo_2011: status='VIGENTE', effective_until='2026-05-24',
--   --   abrogated_by_id=<UUID accordo_2025>
--   -- atteso accordo_2025: effective_until=NULL, abrogated_by_id=NULL
