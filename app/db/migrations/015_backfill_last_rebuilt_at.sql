-- Migration 015 — D-221 backfill (F-NEXT Fase 3, 2026-06-02)
--
-- Problema: la pipeline `content` (generation_service.py) chiude la prima
-- generazione SENZA popolare `last_rebuilt_at`. Solo `rebuild_service`
-- (chiamato esplicitamente da "Rigenera") setta quel campo. Conseguenza:
-- tutti i corsi appena generati hanno `last_rebuilt_at = NULL`.
--
-- Effetto sulla UI: il PptxCanvasRenderer client-side (F-STUDIO-UX Step 4)
-- usa `last_rebuilt_at` come cache-key. NULL fa scattare il fallback al
-- preview PNG backend (PDF dispensa Jinja2 testo-only), bypassando del
-- tutto il rendering fedele del PPTX.
--
-- Fix codice: generation_service.py:660 ora include `last_rebuilt_at=NOW()`
-- nell'UPDATE finale (commit successivo a questa migration).
--
-- Backfill: per i corsi storici già `completed` con `pptx_path` scritto,
-- usa `updated_at` come proxy del tempo di build (l'UPDATE finale di
-- generation_service touch-a quel timestamp). Per corsi MAI completati
-- (failed, generating, skeleton_pending) lascia NULL.

UPDATE courses
SET last_rebuilt_at = COALESCE(updated_at, NOW())
WHERE last_rebuilt_at IS NULL
  AND status IN ('completed', 'partial')
  AND pptx_path IS NOT NULL;
