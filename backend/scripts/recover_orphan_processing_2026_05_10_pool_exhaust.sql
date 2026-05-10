-- Third one-shot recovery: 8 orphan PROCESSING rows from the 100-item
-- stress test that surfaced the Redis-pool-exhaust bug.
--
-- Root cause: backend's async Redis client was sized at max_connections=10.
-- During the stress test, multiple dashboard tabs each holding 1-2 SSE
-- pubsub connections + concurrent /v1/stats polls + /v1/summary cache
-- reads exhausted the pool, and the SSE subscribe path started failing
-- with `redis.exceptions.MaxConnectionsError: Too many connections`.
-- This impacted any code path the worker used that touched Redis from
-- the backend's pool — pub/sub publishes from workers use their OWN
-- sync redis client per task so workers themselves were fine, but the
-- in-flight tasks that COMPLETED and published events may have had the
-- event drop on the floor (workers ignore publish failures by design).
-- The 8 stuck rows specifically are tasks that completed silently or
-- exhausted the bumped retry budget on rate-limit (95 confirmed
-- LLMRateLimitError failures in the same window).
--
-- Fixes shipped together:
--   - ff2d09a — bumped Redis pool to 50 + 5s connect timeout
--   - (this) — flip the 8 zombies to FAILED with diagnostic metadata
--
-- Idempotent: WHERE status='processing' guard.

UPDATE feedback
SET status = 'failed',
    updated_at = NOW(),
    llm_metadata = jsonb_build_object(
        'error_type', 'WorkerCleanupAfterPoolExhaust',
        'error', 'Worker likely succeeded on extraction but failed to publish events due to Redis MaxConnectionsError, or hit retry budget on rate-limit. Cleanup ran post-stress-test.',
        'context', 'stress_test_orphan',
        'note', 'Cleaned up alongside ff2d09a Redis pool fix.'
    )
WHERE status = 'processing';
