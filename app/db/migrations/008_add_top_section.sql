-- 008_add_top_section.sql
--
-- D-166 chiusura strutturale (analista sign-off 2026-05-30, strada A):
-- aggiunta colonna `top_section` su `regulation_chunks` per supportare B3
-- (cross-Titolo decay) come clausola SQL pura, senza heuristic runtime.
--
-- Architettura:
--   - Per regulations multi-Titolo (D.Lgs 81/08): `top_section` contiene il
--     nome del Titolo (Titolo I..XIII, Titolo X-bis) derivato dal numero
--     dell'articolo. Per gli Allegati del D.Lgs 81/08, `top_section`
--     contiene il Titolo di appartenenza ufficiale (Allegato XV -> Titolo IV,
--     Allegato XLI -> Titolo IX, ecc).
--     Mapping deterministica in `app/services/regulation_metadata.py`,
--     verificata su Normattiva (D-170 lezione: fonte istituzionale primaria).
--   - Per regulations a singolo top_section (DM antincendio, Reg CE,
--     Accordi SR, D.Lgs 193/2007, DM 388): `top_section` = il regulation_slug
--     stesso. B3 su queste e' trivial single-section (no-op atteso).
--   - Per chunks parsing-noise (article = NULL, numero fuori range, allegato
--     non normalizzabile): `top_section` = "Sconosciuto".
--
-- TOC 13 Titoli D.Lgs 81/08 confermato (analista 2026-05-30 + verifica
-- Normattiva): NON esiste Titolo I-bis separato. Quello che chiamavamo
-- informalmente "Titolo I-bis Prevenzione e protezione" e' Capo III di
-- Titolo I (Art. 15-54). Limite riconosciuto: B3 al livello Titolo NON
-- discrimina chunks intra-Titolo I (Art. 35/47/18 organizzazione SPP vs
-- Art. 40/46 prevenzione incendi -> tutti top_section = "Titolo I").
-- Target H8 (scheletro doppio livello) + B4 (D9 vincolante).
--
-- B3 logica (post-backfill):
--   - Pool top-30 cosine_voyage selezionato da B2.
--   - Per ogni regulation_id nel pool, conta majority top_section.
--   - Chunks il cui top_section != Titolo dominante della propria regulation
--     -> decay del peso (* B3_DECAY_FACTOR, default 0.4).
--   - Soglia di scarto: peso post-decay < (max_pool * B3_THRESHOLD_RATIO),
--     default 0.30 (soglia relativa, auto-adattiva cross-regime).
--
-- Idempotente (analista sign-off 2026-05-30 disciplinare 3):
--   - ADD COLUMN IF NOT EXISTS sulla migration stessa.
--   - Backfill via script Python (`scripts/backfill_top_section.py`) che usa
--     `regulation_metadata.top_section_of()` come oracolo deterministico.
--     Lo script applica UPDATE solo dove `top_section IS DISTINCT FROM
--     oracolo(regulation_slug, article)`, mai DELETE+INSERT.
--   - Forma SQL ri-eseguibile: corregge mapping (es. Allegato XXI mapping
--     update tra 3 mesi) senza side effect, scrive solo chunks affetti.

ALTER TABLE regulation_chunks
    ADD COLUMN IF NOT EXISTS top_section VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_chunks_top_section
    ON regulation_chunks(regulation_id, top_section)
    WHERE is_current = true;

-- Verifica post-backfill (manuale via psql/proxy):
--
--   SELECT r.slug, c.top_section, COUNT(*) AS n
--   FROM regulation_chunks c
--   JOIN regulations r ON c.regulation_id = r.id
--   WHERE c.is_current = true
--   GROUP BY r.slug, c.top_section
--   ORDER BY r.slug, n DESC;
--
-- Distribuzione attesa per `dlgs_81_08` (post-backfill):
--   Titolo I dominante (Art. 1-61 + Allegati I, I-bis, II, III, 3A, 3B)
--   Titolo IV ricco (Art. 88-160 cantieri + Allegati X-XXIII)
--   Titolo VIII (Art. 180-220 agenti fisici + Allegati XXXV-XXXIX)
--   Titolo IX (Art. 221-265 sostanze + Allegati XL-XLI)
--   Titolo X (Art. 266-286 biologici + Allegati XLII-XLVIII + XLIII-bis/ter)
--   Titolo II, III, V, VI, VII, X-bis, XI, XII, XIII minoritari.
--   "Sconosciuto" minimal (parsing noise residuo, target <1% chunks).
--
-- Distribuzione attesa per regulations single-section (DM 02/09/2021 ecc):
--   top_section = slug stesso per tutti i chunks (1 valore per regulation).
