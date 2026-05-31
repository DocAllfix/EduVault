-- F5 — image_library: indice supplementare per UI admin filter.
-- vast-hopping-sketch §F5.1. La table esisteva gia' (migration 005:88-118)
-- con file_path UNIQUE inline + idx_image_library_tags GIN +
-- idx_image_library_embedding HNSW + idx_image_library_source.
-- Questa migration aggiunge SOLO l'indice composito (source, created_at DESC)
-- usato dall'UI admin "ultime image seeded per provenance ISO7010 vs
-- Wikimedia" in fase review F5.2 admin endpoint.

CREATE INDEX IF NOT EXISTS idx_image_library_source_created
    ON image_library(source, created_at DESC);
