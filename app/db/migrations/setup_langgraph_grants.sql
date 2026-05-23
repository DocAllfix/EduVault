-- app/db/migrations/setup_langgraph_grants.sql
--
-- GRANT per le tabelle LangGraph create automaticamente da
-- AsyncPostgresSaver.setup() (BLUEPRINT §03.2).
--
-- ═══ QUANDO ESEGUIRE ═══
-- Una sola volta DOPO il primo startup del backend (FASE 5 quando
-- generation_service.recover_interrupted_jobs() o equivalente fa partire
-- la pipeline per la prima volta e AsyncPostgresSaver.setup() crea le 3
-- tabelle checkpoint).
--
-- Se nexus_app è l'unico utente che si connette (è il caso v1.0: app
-- runtime usa DATABASE_URL=nexus_app), allora nexus_app è l'OWNER delle
-- tabelle checkpoint e questi GRANT sono ridondanti. Eseguire comunque
-- è idempotente e safe.
--
-- Se in futuro un secondo utente (es. tool di backup, dashboard analytics)
-- deve leggere/scrivere i checkpoint, questi GRANT diventano necessari.
--
-- ═══ COME ESEGUIRE ═══
-- Eseguire come nexus_admin (NON come nexus_app):
--   docker exec -i eduvault-postgres-1 psql -U nexus_admin -d nexus \
--     < app/db/migrations/setup_langgraph_grants.sql
--
-- Se le tabelle non esistono ancora (backend mai avviato con pipeline reale),
-- PostgreSQL restituirà "relation does not exist" — in quel caso avviare prima
-- il backend e rieseguire.

GRANT SELECT, INSERT, UPDATE, DELETE ON checkpoints TO nexus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON checkpoint_writes TO nexus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON checkpoint_migrations TO nexus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON checkpoint_blobs TO nexus_app;

-- Le tabelle checkpoint non hanno SEQUENCE in langgraph-checkpoint-postgres 3.x
-- (UUID generati lato applicazione). Se in versioni future LangGraph
-- aggiunge sequence, decommentare:
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app;
