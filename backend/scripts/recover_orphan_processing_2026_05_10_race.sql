-- Second one-shot recovery: 18 orphan PROCESSING rows from the stress test
-- that surfaced the dispatch-before-commit race.
--
-- Root cause: FeedbackService.create_feedback flushed the row but didn't
-- commit before calling extract_feedback_task.delay(). The Celery worker
-- picks up tasks from the broker faster than the request commits (~1ms vs
-- ~20ms), so on a 20-item batch the first 15-18 tasks landed at the worker
-- BEFORE the request's session.commit() ran. The worker queried by id,
-- saw not_found, returned a clean success — and the row stayed in
-- PROCESSING forever.
--
-- Worker logs at the time of failure:
--   ERROR/ForkPoolWorker-1 feedback_not_found_for_extraction
--   …succeeded in 0.014s: {'feedback_id': 88, 'status': 'not_found'}
--
-- Fix: FeedbackService now awaits session.commit() BEFORE dispatching the
-- task. Committed alongside this cleanup.
--
-- Idempotent: WHERE status='processing' guards re-run.

UPDATE feedback
SET status = 'failed',
    updated_at = NOW(),
    llm_metadata = jsonb_build_object(
        'error_type', 'DispatchBeforeCommitRace',
        'error', 'Worker queried DB before request committed the INSERT; task returned not_found and row was orphaned.',
        'context', 'race_condition_orphan',
        'note', 'From stress test pre-fix. Fix landed alongside this cleanup.'
    )
WHERE id BETWEEN 88 AND 105 AND status = 'processing';
