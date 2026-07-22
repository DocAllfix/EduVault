-- Migration 016 — parametri di pacing per-corso (FASE 2 pacing dinamico, 2026-07-21)
--
-- Contesto: la durata-slide diventa una scelta dell'utente (CourseRequest.
-- seconds_per_slide, range 40-240s, default 45). Va persistita sulla riga
-- ``courses`` per due motivi:
--   1. il rebuild audio deve usare la stessa finestra di durata della prima
--      generazione (altrimenti tracce marcate off_target a torto);
--   2. la generazione contenuti legge la durata-slide dal corso per calibrare
--      i vincoli di lunghezza note (build_layout_constraints).
--
-- Aggiungiamo anche ``slide_density``, che finora NON era persistito (il create
-- endpoint lo scartava — courses.py pre-FASE-2): serve per un rebuild coerente.
--
-- Additiva e idempotente. Il DEFAULT 45/'standard' garantisce che i corsi
-- esistenti (9 in produzione) restino identici: la loro durata-slide effettiva
-- era 45 e la densita` standard, quindi il backfill non cambia nulla.

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS seconds_per_slide NUMERIC(5,1) NOT NULL DEFAULT 45.0;

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS slide_density VARCHAR(20) NOT NULL DEFAULT 'standard'
        CHECK (slide_density IN ('leggera', 'standard', 'intensiva'));
