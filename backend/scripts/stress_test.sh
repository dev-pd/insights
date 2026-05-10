#!/usr/bin/env bash
# Usage: stress_test.sh <N>
#   N items per /batch call. If N > 50 (batch endpoint cap), splits into
#   chunks of 50 dispatched back-to-back so the worker pool sees the full
#   load at once.
set -euo pipefail

N=${1:-20}
BATCH_CAP=50
TIMEOUT_S=$((N * 4 + 30))    # generous: ~4s per item plus headroom
POLL_INTERVAL_S=2

echo "==================== stress test: N=$N ===================="

# Generate N varied feedback texts. Cycle through a 25-template pool so the
# texts vary in length, sentiment, and themes — exercises validation + LLM
# extraction realistically.
texts_json=$(/usr/bin/python3 <<PY
import json, random
random.seed(0xC0FFEE + $N)
TEMPLATES = [
    "Product quality is excellent and the shipping was super fast this week.",
    "Customer support response time has been disappointing lately. Two days for a reply.",
    "Mobile app crashes on the login screen on Android 14. Restarting does not help.",
    "Pricing tiers are confusing. The pro plan benefits are not clearly explained.",
    "Loving the new dashboard! Charts are clear and load quickly.",
    "Bulk export feature is missing critical fields like sentiment and timestamp.",
    "Onboarding flow had too many steps. Lost interest before finishing setup.",
    "Performance is solid even with 10k records. Filters and search feel instant.",
    "Documentation could use more examples for the API integration endpoints.",
    "Trial expiration warnings were unclear. Account locked without obvious notice.",
    "Theme support is great but I wish dark mode synced with my OS preference.",
    "Search returns irrelevant results when querying short strings. Needs tuning.",
    "Loading spinners feel slow even on small operations. Could use optimistic UI.",
    "Webhook reliability is excellent. Have not seen a missed delivery in months.",
    "Billing UI is buried three levels deep in settings. Hard to find when needed.",
    "Push notifications are landing twice for the same event. Possible duplicate dispatch.",
    "Two-factor auth setup was painless. QR code scanned and worked first try.",
    "CSV import fails silently when a row has trailing commas. No error shown.",
    "Realtime collaboration is buttery smooth. Cursors and selections sync instantly.",
    "Mobile responsive layout breaks on landscape orientation. Side nav overlaps content.",
    "Latency improved dramatically since last week. API calls feel snappier overall.",
    "Email digest is helpful but the unsubscribe link in dark mode is invisible.",
    "Keyboard shortcuts cheat sheet would help power users move faster through the UI.",
    "Date picker defaults to today but the user often wants the same range as last week.",
    "Audio transcription accuracy is impressive even with background noise present.",
]
items = []
for i in range(${N}):
    base = random.choice(TEMPLATES)
    items.append(f"[stress N=${N} item {i+1:03d}] {base}")
print(json.dumps({"texts": items}))
PY
)

# Baseline counts
baseline_pending=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["pending_count"])')
baseline_extracted=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["total_extracted"])')
baseline_failed=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["total_failed"])')
baseline_usage=$(docker compose exec -T postgres psql -U postgres -d feedback -At -c "SELECT COUNT(*) FROM llm_usage WHERE call_type='extraction';")
echo "baseline: pending=$baseline_pending extracted=$baseline_extracted failed=$baseline_failed llm_usage_extraction=$baseline_usage"

# Dispatch — chunk if N > BATCH_CAP
start_epoch=$(/usr/bin/python3 -c 'import time; print(time.time())')
chunks=$(/usr/bin/python3 -c "
import json
texts = json.loads('''$texts_json''')['texts']
cap = $BATCH_CAP
out = [texts[i:i+cap] for i in range(0, len(texts), cap)]
print(len(out))
")
echo "dispatching $N items in $chunks chunk(s) of max $BATCH_CAP …"

/usr/bin/python3 <<PY
import json, time, urllib.request
texts = json.loads('''$texts_json''')['texts']
cap = $BATCH_CAP
chunks = [texts[i:i+cap] for i in range(0, len(texts), cap)]
total_processing = 0
for chunk_idx, chunk in enumerate(chunks, 1):
    t0 = time.time()
    req = urllib.request.Request(
        "http://localhost:8081/api/v1/feedback/batch",
        data=json.dumps({"texts": chunk}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - t0
    total_processing += data["processing"]
    print(f"  chunk {chunk_idx}/{len(chunks)}: dispatched {len(chunk)} in {elapsed*1000:.0f}ms  → processing={data['processing']} skipped={data['skipped']}")
print(f"total dispatched: processing={total_processing}")
PY
dispatch_end_epoch=$(/usr/bin/python3 -c 'import time; print(time.time())')

# Poll until pending drains
echo
echo "polling pending_count every ${POLL_INTERVAL_S}s …"
poll_start=$(/usr/bin/python3 -c 'import time; print(time.time())')
deadline=$(/usr/bin/python3 -c "import time; print(time.time() + $TIMEOUT_S)")
last_pending=-1
while true; do
    now=$(/usr/bin/python3 -c 'import time; print(time.time())')
    if (( $(/usr/bin/python3 -c "print(1 if $now > $deadline else 0)") )); then
        echo "TIMEOUT after ${TIMEOUT_S}s — bailing"
        break
    fi
    pending=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["pending_count"])')
    extracted=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["total_extracted"])')
    if [ "$pending" != "$last_pending" ]; then
        elapsed=$(/usr/bin/python3 -c "print(f'{$now - $poll_start:5.1f}')")
        completed=$((extracted - baseline_extracted))
        echo "  t+${elapsed}s  pending=$pending  newly_extracted=$completed"
        last_pending=$pending
    fi
    if [ "$pending" -le "$baseline_pending" ]; then
        break
    fi
    sleep $POLL_INTERVAL_S
done
drain_end_epoch=$(/usr/bin/python3 -c 'import time; print(time.time())')

# Final stats
total_elapsed=$(/usr/bin/python3 -c "print(f'{$drain_end_epoch - $start_epoch:.1f}')")
dispatch_elapsed=$(/usr/bin/python3 -c "print(f'{$dispatch_end_epoch - $start_epoch:.2f}')")
drain_elapsed=$(/usr/bin/python3 -c "print(f'{$drain_end_epoch - $dispatch_end_epoch:.1f}')")

final_extracted=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["total_extracted"])')
final_failed=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["total_failed"])')
final_usage=$(docker compose exec -T postgres psql -U postgres -d feedback -At -c "SELECT COUNT(*) FROM llm_usage WHERE call_type='extraction';")
final_pending=$(/usr/bin/curl -s http://localhost:8081/api/v1/stats | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin)["pending_count"])')

newly_extracted=$((final_extracted - baseline_extracted))
newly_failed=$((final_failed - baseline_failed))
newly_usage=$((final_usage - baseline_usage))
throughput=$(/usr/bin/python3 -c "print(f'{$newly_extracted / max(0.1, $drain_end_epoch - $dispatch_end_epoch):.2f}')")

echo
echo "=== summary ==="
echo "  dispatch:        ${dispatch_elapsed}s  ($N items)"
echo "  drain:           ${drain_elapsed}s    (worker concurrency=4)"
echo "  total elapsed:   ${total_elapsed}s"
echo "  newly extracted: $newly_extracted"
echo "  newly failed:    $newly_failed"
echo "  llm_usage rows added: $newly_usage  (should equal extracted)"
echo "  end pending_count: $final_pending"
echo "  throughput:      ${throughput} items/s"
echo

# Worker p50/p95 from the most recent N llm_usage rows
docker compose exec -T postgres psql -U postgres -d feedback -c "
WITH recent AS (
    SELECT latency_ms FROM llm_usage
    WHERE call_type='extraction'
    ORDER BY id DESC
    LIMIT $N
)
SELECT
    MIN(latency_ms) AS min_ms,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
    MAX(latency_ms) AS max_ms,
    AVG(latency_ms)::int AS avg_ms,
    COUNT(*) AS n
FROM recent;
"

# Show any failures
if [ "$newly_failed" -gt 0 ]; then
    echo "FAILURES detected — error types:"
    docker compose exec -T postgres psql -U postgres -d feedback -c "
    SELECT llm_metadata->>'error_type' AS error_type,
           COUNT(*) AS n
    FROM feedback
    WHERE status='failed'
      AND created_at > NOW() - INTERVAL '5 minutes'
    GROUP BY 1 ORDER BY n DESC;
    "
fi
