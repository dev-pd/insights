"use client"

import { useEffect, useState } from "react"

/**
 * Returns a debounced copy of `value` that only updates after `delayMs` of
 * stillness. Each new `value` resets the timer.
 *
 * Used by the /feedback search input so we don't fire a request on every
 * keystroke. Cleanup runs on unmount and on every value change, so an
 * abandoned typing burst never lands a stale update on the consumer.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delayMs)
    return () => {
      clearTimeout(timer)
    }
  }, [value, delayMs])

  return debouncedValue
}
