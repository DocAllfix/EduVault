-- 013_courses_outputs.sql (2026-06-01)
--
-- Fix bug strutturale: `outputs TEXT[]` mancava nella tabella courses.
--
-- Il payload CourseRequest contiene `outputs: list[str]` (es. ['pptx','pdf','audio','quiz'])
-- ma INSERT INTO courses NON salvava il campo → tutti i corsi avevano outputs=[].
-- Conseguenza: generation_service._bg_audio() check `"audio" in course["outputs"]`
-- ritornava SEMPRE False → audio Azure mai generato per nessun corso, anche
-- quando l'utente sceglieva audio=true nel wizard step 5.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS + check default '{}'.
-- Retro-compat: corsi pre-esistenti hanno outputs='{}' (no audio retrofit
-- automatico — utente userà endpoint /audio/rebuild quando vuole).

ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS outputs TEXT[] NOT NULL DEFAULT '{}';

-- Backfill: corsi che hanno gia' audio_manifest_path popolato avevano audio,
-- segnaliamo nei loro outputs (utile per /audio/rebuild stesso campo source).
UPDATE courses
   SET outputs = ARRAY['pptx','pdf','audio']::TEXT[]
 WHERE outputs = '{}'::TEXT[]
   AND audio_manifest_path IS NOT NULL;

-- Tutti gli altri completed (senza audio) hanno almeno pptx+pdf
UPDATE courses
   SET outputs = ARRAY['pptx','pdf']::TEXT[]
 WHERE outputs = '{}'::TEXT[]
   AND status IN ('completed','partial','content','building','failed','archived');
