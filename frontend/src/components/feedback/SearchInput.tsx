"use client"

import { Input } from "@/components/ui/input"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
}

export function SearchInput({ value, onChange }: SearchInputProps) {
  return (
    <div className="relative w-full max-w-md">
      <Input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={feedbackCopy.search.placeholder}
        aria-label={feedbackCopy.search.ariaLabel}
        className="pr-9"
      />
      {value.length > 0 && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label={feedbackCopy.search.clearButton}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground rounded p-0.5 leading-none"
        >
          <span aria-hidden="true">×</span>
        </button>
      )}
    </div>
  )
}
