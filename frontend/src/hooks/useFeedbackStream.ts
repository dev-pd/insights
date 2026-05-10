"use client"

import { useEffect, useRef } from "react"

import { API_ROUTES } from "@/lib/api/routes"

export interface FeedbackUpdateEvent {
  feedback_id: number
  status: string
  payload: {
    sentiment?: string
    themes?: string[]
    action_items?: string[]
    language?: string
    error?: string
  }
  ts: string
}

export interface FeedbackStreamHandlers {
  onFeedbackUpdate?: (event: FeedbackUpdateEvent) => void
  onStatsInvalidate?: () => void
  onConnected?: () => void
  onError?: (error: Event) => void
}

/**
 * Subscribe to the SSE event stream from /api/v1/events.
 *
 * EventSource auto-reconnects on transient drops (browser owns the retry
 * loop). Cleanup closes the connection on unmount. Handlers are accessed
 * via a ref so the effect only mounts once per (enabled) cycle — callers
 * can pass fresh inline closures every render without re-creating the
 * EventSource.
 *
 * The `enabled` param drives conditional subscription. When false, no
 * connection is opened (or the existing one is closed). Callers should
 * gate this on `pending_count > 0` from the SWR-polled /v1/stats so the
 * connection only lives while there's actually work in flight. Idle
 * dashboards don't pin a Redis pubsub slot just to receive heartbeats.
 *
 * Re-enable latency: SWR polls stats every 5s, so there's at most a 5s
 * gap between a submission landing in PROCESSING and the SSE pipe opening.
 * Acceptable — the user just clicked submit, they're not expecting
 * realtime updates within the first second.
 *
 * Use one hook instance per page. Multiple concurrent instances on
 * different pages are fine; the backend serves each connection
 * independently.
 */
export function useFeedbackStream(
  handlers: FeedbackStreamHandlers,
  enabled: boolean,
): void {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    if (!enabled) {
      // No subscription when disabled. Effect re-runs (and opens a new
      // EventSource) when enabled flips back to true.
      return
    }

    const eventSource = new EventSource(API_ROUTES.events)

    const onConnected = () => {
      handlersRef.current.onConnected?.()
    }

    const onFeedbackUpdate = (messageEvent: MessageEvent) => {
      try {
        const data = JSON.parse(messageEvent.data) as FeedbackUpdateEvent
        handlersRef.current.onFeedbackUpdate?.(data)
      } catch {
        // Malformed payload — ignore the event rather than breaking the
        // stream. There's nothing user-actionable to surface here.
      }
    }

    const onStatsInvalidate = () => {
      handlersRef.current.onStatsInvalidate?.()
    }

    const onError = (errorEvent: Event) => {
      handlersRef.current.onError?.(errorEvent)
      // EventSource handles reconnection — no manual retry logic needed.
    }

    eventSource.addEventListener("connected", onConnected)
    eventSource.addEventListener("feedback_update", onFeedbackUpdate)
    eventSource.addEventListener("stats_invalidate", onStatsInvalidate)
    eventSource.addEventListener("error", onError)

    return () => {
      eventSource.removeEventListener("connected", onConnected)
      eventSource.removeEventListener("feedback_update", onFeedbackUpdate)
      eventSource.removeEventListener("stats_invalidate", onStatsInvalidate)
      eventSource.removeEventListener("error", onError)
      eventSource.close()
    }
  }, [enabled])
}
