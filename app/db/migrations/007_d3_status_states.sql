-- 007_d3_status_states.sql
--
-- D3 (vast-hopping-sketch, post-review-17): add the skeleton-review states
-- to the `courses.status` and `generation_jobs.status` CHECK constraints.
--
-- Why: the D3 narrative-skeleton flow introduces two new course states:
--   - 'skeleton_pending': research finished, the LLM-proposed skeleton has
--     been persisted to courses.module_skeletons_json, the pipeline is paused
--     waiting for the human 1-click approve gate.
--   - 'content': the operator approved the skeleton; the content phase is
--     running (per-sub-topic retrieval + content_agent + build).
-- Both states were missing from the pre-existing CHECK constraints — the E2E
-- smoke caught it as soon as _run_research_and_skeleton tried to UPDATE the
-- row with status='skeleton_pending' (asyncpg CheckViolationError).
--
-- The generation_jobs constraint already includes 'research' and 'content';
-- only 'skeleton_pending' is added there (the inner phase uses 'research' for
-- the kick-off and the orchestrator stamps 'skeleton_pending' on the job when
-- the gate fires).
--
-- Idempotent: drops the old CHECK by name only if present, recreates with the
-- extended whitelist. No data migration needed (the new states do not exist
-- for any pre-D3 row).

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'courses_status_check' AND conrelid = 'courses'::regclass
    ) THEN
        ALTER TABLE courses DROP CONSTRAINT courses_status_check;
    END IF;
END
$$;

ALTER TABLE courses
    ADD CONSTRAINT courses_status_check
    CHECK (status IN (
        'generating',
        'skeleton_pending',  -- D3 gate: research done, awaiting human approve
        'content',           -- D3: approve fired, content phase running
        'completed',
        'reviewed',
        'certified',
        'failed',
        'archived'
    ));

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'generation_jobs_status_check'
          AND conrelid = 'generation_jobs'::regclass
    ) THEN
        ALTER TABLE generation_jobs DROP CONSTRAINT generation_jobs_status_check;
    END IF;
END
$$;

ALTER TABLE generation_jobs
    ADD CONSTRAINT generation_jobs_status_check
    CHECK (status IN (
        'queued',
        'research',
        'skeleton_pending',  -- D3 gate
        'content',
        'building',
        'completed',
        'failed',
        'cancelled'
    ));

-- Verifica post-apply (a mano via psql/proxy):
--   SELECT pg_get_constraintdef(oid)
--   FROM pg_constraint
--   WHERE conname IN ('courses_status_check','generation_jobs_status_check');
--   → entrambe devono contenere 'skeleton_pending'.
