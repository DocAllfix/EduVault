-- F7.3 — audio_tracks: provider column per tracking origine TTS.
-- vast-hopping-sketch §F7. Default 'edge' = retro-compat su righe esistenti.
-- Quando provider='azure' frontend mostra badge "Azure" accanto al play
-- (signal premium quality per cliente). Idempotente.

ALTER TABLE audio_tracks
    ADD COLUMN IF NOT EXISTS provider VARCHAR(20) DEFAULT 'edge'
        CHECK (provider IN ('edge', 'azure'));

-- Indice utile per audit query "quanti track Azure vs edge" (telemetry F7.5).
CREATE INDEX IF NOT EXISTS idx_audio_tracks_provider
    ON audio_tracks(provider)
    WHERE provider IS NOT NULL;
