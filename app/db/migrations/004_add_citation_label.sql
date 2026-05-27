-- Migration 004 — FIX #30.5a (2026-05-26): citation_label denormalizzato.
--
-- Aggiunge una colonna citation_label a regulation_chunks. Il valore viene
-- popolato a ingest-time da una regola deterministica:
--   - se article valorizzato: "D.Lgs. {year}/{number}, art. {article}{comma}"
--   - se article NULL ma hierarchy_path contiene "Allegato": hierarchy_path
--   - else: hierarchy_path troncato a 200 char
--
-- Il content_agent dopo questa migration NON scrive più normative_ref via LLM:
-- lo ricostruisce con lookup deterministico dai source_chunk_ids della slide.
-- Questo elimina alla radice le allucinazioni "Pag. 31-136" e i format
-- incoerenti tipo "Allegato IV" singolo.
--
-- Script backfill: scripts/backfill_citations.py (popola gli esistenti).

ALTER TABLE regulation_chunks ADD COLUMN IF NOT EXISTS citation_label VARCHAR(200);
CREATE INDEX IF NOT EXISTS idx_chunks_citation ON regulation_chunks(citation_label);

-- Verifica:
-- SELECT COUNT(*) FROM regulation_chunks WHERE citation_label IS NOT NULL;
