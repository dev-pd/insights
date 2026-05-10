-- One-shot cleanup: 471 PROCESSING rows from a 500-item Opus stress test
-- that was aborted mid-flight when the operator realized the Anthropic
-- account didn't have $13 of credit to cover it.
--
-- Aborted via:
--   docker compose stop worker         (no more Opus calls)
--   redis-cli -n 1 DEL celery          (purge queued tasks)
--   this SQL                           (flip stuck rows so the dashboard
--                                       reflects reality)
--
-- Final cost: 29 Opus calls completed (~$1.05) before the abort.
-- 468 queued tasks discarded before they reached the worker. ~$12 saved.
--
-- Not a bug — operator-driven abort. Captured here for audit trail per
-- the established pattern (every cleanup leaves a committed SQL artifact).
--
-- Idempotent: WHERE status='processing' guard makes re-running a no-op.

UPDATE feedback
SET status = 'failed',
    updated_at = NOW(),
    llm_metadata = jsonb_build_object(
        'error_type', 'TestAbortedNoBudget',
        'error', 'Stress test of 500 Opus items aborted mid-flight when user noted insufficient Anthropic credit. Worker stopped, broker purged, queued tasks discarded.',
        'context', 'budget_abort',
        'note', 'No Anthropic call was made for these rows; they were queued but never picked up by the worker.'
    )
WHERE status = 'processing';
