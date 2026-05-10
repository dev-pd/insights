-- One-shot recovery for orphan PROCESSING rows from Phase 4 (C5/C6) debug
-- iterations. Two upstream bugs caused worker tasks to crash BEFORE our
-- LLMError handler ran, leaving 4 rows in PROCESSING forever:
--
--   ids 66/67/71 → RuntimeError "Future attached to a different loop"
--                  (engine-rebinding bug, fixed in commit 2cbd074)
--   id  73       → AttributeError "'APIConnectionError' object has no
--                  attribute 'status_code'" (fixed in commit 80247ae)
--
-- Both root causes are fixed in HEAD. The design gap that LET the rows
-- orphan (only `except LLMError` flipped status) is fixed in commit
-- a5e48db (broad-catch in _do_extraction).
--
-- Diagnostic source: redis-cli -n 2 KEYS 'celery-task-meta-*' →
-- 4 FAILURE records whose tracebacks matched these exceptions.
--
-- Idempotent: the WHERE status='processing' guards ensure re-running on
-- already-recovered data is a no-op.
--
-- Run inside the postgres container:
--   docker compose exec -T postgres psql -U postgres -d feedback \
--     < backend/scripts/recover_orphan_processing_2026_05_10.sql

UPDATE feedback
SET status = 'failed',
    updated_at = NOW(),
    llm_metadata = jsonb_build_object(
        'error_type', 'RuntimeError',
        'error', 'Future attached to a different loop',
        'context', 'celery_task_uncaught',
        'note', 'Orphan from C5 engine-rebinding bug; fix landed in 2cbd074. Cleaned up post-hoc.'
    )
WHERE id IN (66, 67, 71) AND status = 'processing';

UPDATE feedback
SET status = 'failed',
    updated_at = NOW(),
    llm_metadata = jsonb_build_object(
        'error_type', 'AttributeError',
        'error', '''APIConnectionError'' object has no attribute ''status_code''',
        'context', 'celery_task_uncaught',
        'note', 'Orphan from C6 client.py bug; fix landed in 80247ae. Cleaned up post-hoc.'
    )
WHERE id = 73 AND status = 'processing';
