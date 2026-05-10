"use client"

import { useToast, type ToastVariant } from "@/hooks/useToast"
import { cn } from "@/lib/utils"

const variantStyles: Record<ToastVariant, string> = {
  success:
    "bg-emerald-50 text-emerald-900 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-100 dark:border-emerald-900/60",
  error:
    "bg-rose-50 text-rose-900 border-rose-200 dark:bg-rose-950/40 dark:text-rose-100 dark:border-rose-900/60",
  info: "bg-slate-50 text-slate-900 border-slate-200 dark:bg-slate-950/40 dark:text-slate-100 dark:border-slate-800",
}

export function ToastStack() {
  const { toasts, dismissToast } = useToast()

  if (toasts.length === 0) return null

  return (
    <div
      role="region"
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-[min(420px,calc(100vw-2rem))]"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className={cn(
            "rounded-md border px-4 py-3 shadow-md text-sm flex items-start justify-between gap-3",
            variantStyles[toast.variant],
          )}
        >
          <span className="flex-1 leading-relaxed">{toast.message}</span>
          <button
            type="button"
            onClick={() => dismissToast(toast.id)}
            aria-label="Dismiss notification"
            className="text-current/60 hover:text-current text-lg leading-none px-1 -my-1"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
