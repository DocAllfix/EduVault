-- FASE 7 + 11 vast-hopping-sketch — Course Studio support
-- dirty: True quando l'utente modifica slide via Studio ma non ha ancora
--   rigenerato PPTX/PDF/audio (RebuildBanner FASE 11).
-- last_rebuilt_at: timestamp ultima rebuild.
-- slide_contents_json_snapshot: snapshot dell'ultimo build per diff incrementale
--   audio re-gen (FASE 11 rebuild_service).

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS dirty BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS last_rebuilt_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS slide_contents_json_snapshot JSONB;
