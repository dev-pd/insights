"use client"

import { useCallback, useEffect, useState } from "react"

export type ToastVariant = "success" | "error" | "info"

export interface Toast {
  id: string
  message: string
  variant: ToastVariant
}

interface ShowToastOptions {
  variant?: ToastVariant
  durationMs?: number
}

const DEFAULT_DURATION_MS = 4000
const MAX_VISIBLE_TOASTS = 5

// Module-level singleton state. Subscribe/notify lets any component anywhere
// trigger a toast that the single ToastStack (mounted in app/layout) renders.
// Avoids React Context boilerplate for what's intrinsically global UI.
const subscribers = new Set<(toasts: Toast[]) => void>()
let currentToasts: Toast[] = []

function notifySubscribers() {
  for (const subscriber of subscribers) {
    subscriber([...currentToasts])
  }
}

function pushToast(message: string, options: ShowToastOptions = {}) {
  const id = crypto.randomUUID()
  const toast: Toast = {
    id,
    message,
    variant: options.variant ?? "info",
  }
  currentToasts = [toast, ...currentToasts].slice(0, MAX_VISIBLE_TOASTS)
  notifySubscribers()

  const duration = options.durationMs ?? DEFAULT_DURATION_MS
  setTimeout(() => {
    currentToasts = currentToasts.filter((toast) => toast.id !== id)
    notifySubscribers()
  }, duration)
}

function dismissToastById(id: string) {
  currentToasts = currentToasts.filter((toast) => toast.id !== id)
  notifySubscribers()
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>(currentToasts)

  useEffect(() => {
    subscribers.add(setToasts)
    return () => {
      subscribers.delete(setToasts)
    }
  }, [])

  const showToast = useCallback(
    (message: string, options?: ShowToastOptions) => {
      pushToast(message, options)
    },
    [],
  )

  const dismissToast = useCallback((id: string) => {
    dismissToastById(id)
  }, [])

  return { toasts, showToast, dismissToast }
}
