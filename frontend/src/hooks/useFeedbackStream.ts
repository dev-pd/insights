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
  onSummaryInvalidate?: () => void
  onConnected?: () => void
  onError?: (error: Event) => void
}

/**
 * Subscribes to /api/v1/events. `enabled` gates connection — callers
 * should pass `pending_count > 0` so idle dashboards don't pin a Redis
 * pubsub slot. Handlers via ref so callers can pass inline closures every
 * render without re-creating the EventSource.
 */
export function useFeedbackStream(
  handlers: FeedbackStreamHandlers,
  enabled: boolean,
): void {
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  useEffect(() => {
    if (!enabled) return

    const eventSource = new EventSource(API_ROUTES.events)

    const onConnected = () => {
      handlersRef.current.onConnected?.()
    }

    const onFeedbackUpdate = (messageEvent: MessageEvent) => {
      try {
        const data = JSON.parse(messageEvent.data) as FeedbackUpdateEvent
        handlersRef.current.onFeedbackUpdate?.(data)
      } catch {
        // Malformed payload — drop the event, don't break the stream.
      }
    }

    const onStatsInvalidate = () => {
      handlersRef.current.onStatsInvalidate?.()
    }

    const onSummaryInvalidate = () => {
      handlersRef.current.onSummaryInvalidate?.()
    }

    const onError = (errorEvent: Event) => {
      handlersRef.current.onError?.(errorEvent)
    }

    eventSource.addEventListener("connected", onConnected)
    eventSource.addEventListener("feedback_update", onFeedbackUpdate)
    eventSource.addEventListener("stats_invalidate", onStatsInvalidate)
    eventSource.addEventListener("summary_invalidate", onSummaryInvalidate)
    eventSource.addEventListener("error", onError)

    return () => {
      eventSource.removeEventListener("connected", onConnected)
      eventSource.removeEventListener("feedback_update", onFeedbackUpdate)
      eventSource.removeEventListener("stats_invalidate", onStatsInvalidate)
      eventSource.removeEventListener("summary_invalidate", onSummaryInvalidate)
      eventSource.removeEventListener("error", onError)
      eventSource.close()
    }
  }, [enabled])
}
