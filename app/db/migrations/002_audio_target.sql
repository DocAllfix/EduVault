-- FASE 6 vast-hopping-sketch — audio off_target flag
-- Aggiunge la colonna off_target a audio_tracks: True se la durata MP3 della
-- slide è fuori dal range target 25-35s (regola 30s/slide). La Course Studio
-- (FASE 10) mostra un badge "⚠ off-target" e permette regen manuale.

ALTER TABLE audio_tracks
    ADD COLUMN IF NOT EXISTS off_target BOOLEAN NOT NULL DEFAULT false;

-- Index parziale per query rapida "slide con audio off-target di un corso"
CREATE INDEX IF NOT EXISTS idx_audio_tracks_off_target
    ON audio_tracks (course_id)
    WHERE off_target = true;
