-- scripts/setup_roles.sql
-- Eseguire UNA VOLTA dopo il primo docker-compose up, connessi come nexus_admin.
--
-- IMPORTANTE: sostituire 'CHANGE_ME_APP_64_CHARS' con il valore di
-- POSTGRES_APP_PASSWORD dal file .env PRIMA di eseguire questo script.
-- Esempio di esecuzione:
--   docker exec -i eduvault-postgres-1 psql -U nexus_admin -d nexus \
--     < app/db/migrations/setup_roles.sql

CREATE ROLE nexus_app LOGIN PASSWORD 'CHANGE_ME_APP_64_CHARS';
GRANT CONNECT ON DATABASE nexus TO nexus_app;
GRANT USAGE ON SCHEMA public TO nexus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nexus_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nexus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO nexus_app;

-- ═══ BLINDATURA AUDIT LOG ═══
REVOKE DELETE, UPDATE, TRUNCATE ON audit_log FROM nexus_app;

-- ═══ GRANT PER TABELLE LANGGRAPH ═══
-- LangGraph crea le proprie tabelle al primo avvio del backend.
-- Eseguire QUESTA sezione DOPO il primo avvio del backend (Sprint 3).
-- Se eseguita prima che le tabelle esistano, PostgreSQL darà errore —
-- in quel caso, rieseguire dopo il primo avvio.
-- GRANT SELECT, INSERT, UPDATE, DELETE ON checkpoints, checkpoint_writes, checkpoint_migrations TO nexus_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app;
