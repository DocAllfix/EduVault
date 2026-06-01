-- 014_audio_tracks_module_index.sql
-- F-AUDIO-FIX 2026-06-01: audio_tracks NON identifica univocamente la slide.
-- Bug strutturale: slide.index e' module-relative (0..N per modulo), ma audio_tracks
-- aveva solo (course_id, slide_index). Con 4+ moduli → 4 righe con stesso slide_index
-- → fetchrow restituisce 1 riga casuale. Inoltre filename MP3 era slide_{index:04d}.mp3
-- → moduli successivi sovrascrivono i precedenti su disco.
--
-- Fix: aggiungere module_index obbligatorio per nuove righe + UNIQUE per dedup
-- corretta. Vecchie righe (legacy) rimangono module_index NULL, ma vengono pulite
-- tramite DELETE prima del retrofit (rebuild_service.py linea 102 fa gia' DELETE
-- prima di generate_narrations).

ALTER TABLE audio_tracks
    ADD COLUMN IF NOT EXISTS module_index INT;

-- UNIQUE constraint partial: applicato solo a righe con module_index valorizzato.
-- Permette coesistenza temporanea legacy (NULL) + new (NOT NULL).
CREATE UNIQUE INDEX IF NOT EXISTS uniq_audio_tracks_course_mod_slide
    ON audio_tracks (course_id, module_index, slide_index)
    WHERE module_index IS NOT NULL;

-- Index per query frequente: lookup per (course_id, module_index, slide_index)
-- → coperto gia` dal UNIQUE index sopra.
