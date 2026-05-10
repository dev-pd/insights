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
 * via a ref so the effect only mounts once — callers can pass fresh
 * inline closures every render without re-creating the EventSource.
 *
 * Use one hook instance per page that needs real-time updates. Multiple
 * concurrent instances are fine; the backend serves each connection
 * independently.
 */
export function useFeedbackStream(handlers: FeedbackStreamHandlers): void {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
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
  }, [])
}
