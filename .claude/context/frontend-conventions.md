# Frontend conventions

How to write TypeScript and React code in this project. Applies to everything under `frontend/`. These are non-negotiable conventions: when generating or editing frontend code, follow them without exception.

## Tooling and versions

- Next.js 14 with App Router (not Pages Router)
- TypeScript 5+ with `strict: true` in `tsconfig.json`
- React 18+
- Tailwind CSS via PostCSS
- shadcn/ui components installed via `npx shadcn@latest add`
- recharts for charts
- SWR for data fetching and cache mutation
- date-fns for relative timestamps
- Prettier for TypeScript formatting via the Next.js default config

Package management via `npm`. Run dev server with `npm run dev`.

Frontend deploys via `next start` as a Node server, not static export. `next.config.js` does not set `output: 'export'`. This preserves the full Next.js feature surface (middleware, server components, server actions, API routes) for future additions like authentication.

## Environment variables

The frontend container has no env file in deployment. `apiClient.ts` uses relative paths (e.g., `/v1/feedback`) which nginx routes to the backend on the internal docker network. `NEXT_PUBLIC_API_BASE_URL` is unset and `apiClient` falls back to an empty-string base.

Server-only env vars (e.g., `AUTH_SECRET` when auth is added later) would live in `frontend/.env.local` without the `NEXT_PUBLIC_` prefix — they stay server-side and never bundle into the browser. Running as a Node server (not static export) is what makes server-only env vars work; static export would not have this distinction.

## Server vs client components

Next.js App Router defaults to server components. Any file using `useState`, `useEffect`, hooks, browser APIs, or event handlers must start with `'use client'` at the very top. Default to server components when possible (layout shells, static content). Use `'use client'` only when interactivity is actually needed.

For this app, every component in `components/` and every hook in `hooks/` uses `'use client'`; only `app/layout.tsx` and `app/page.tsx` (where applicable) can stay as server components.

## Naming

| Element | Convention | Example |
|---|---|---|
| Component file | PascalCase, `.tsx` | `FeedbackCard.tsx`, `PasteForm.tsx` |
| Hook file | camelCase with `use` prefix, `.ts` | `useFeedbackStream.ts` |
| Utility file | camelCase, `.ts` | `apiClient.ts`, `dateUtils.ts` |
| Type-only file | lowercase with `.types.ts` suffix when standalone | `feedback.types.ts` |
| Constants file | camelCase, `.ts` | `constants.ts` |
| Component (in code) | PascalCase | `FeedbackCard`, `KpiCard` |
| Hook (in code) | camelCase with `use` prefix | `useFeedbackStream`, `useDebouncedValue` |
| Function | camelCase | `formatTimestamp`, `submitFeedback` |
| Constant | UPPER_SNAKE_CASE for primitives | `POLL_INTERVAL_MS = 2000` |
| Constant object | UPPER_SNAKE_CASE with `as const` | `API_ROUTES`, `SENTIMENT_STYLES` |
| Type | PascalCase | `FeedbackOut`, `Sentiment` |
| Props type | PascalCase ending in `Props` | `FeedbackCardProps` |

## Exports

**Named exports only.** No default exports anywhere except where Next.js requires them (page components in `app/`).

```tsx
// Good
export function FeedbackCard({ item }: FeedbackCardProps) { ... }

// Bad - default export
export default function FeedbackCard({ item }: FeedbackCardProps) { ... }
```

The Next.js exception: `app/page.tsx`, `app/layout.tsx`, `app/loading.tsx`, etc. require default exports. Everything else is named.

One primary thing per file: one component, one hook, one util module. Co-locate small helpers used only by that primary thing in the same file.

## Components

### Functional components with hooks only

No class components. No exceptions.

```tsx
// Good
export function FeedbackCard({ item }: FeedbackCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  return <div>...</div>
}

// Bad - class component
export class FeedbackCard extends React.Component<FeedbackCardProps> { ... }
```

### Explicit prop types adjacent to component

Define `Props` type immediately above the component. Don't inline.

```tsx
// Good
type FeedbackCardProps = {
  item: FeedbackOut
  onExpand?: (id: string) => void
}

export function FeedbackCard({ item, onExpand }: FeedbackCardProps) { ... }

// Bad - inline
export function FeedbackCard({ item, onExpand }: { item: FeedbackOut; onExpand?: (id: string) => void }) { ... }
```

### Destructure props in the function signature

```tsx
// Good
export function KpiCard({ label, value, trend }: KpiCardProps) {
  return <div>{label}: {value}</div>
}

// Bad - access via props.x
export function KpiCard(props: KpiCardProps) {
  return <div>{props.label}: {props.value}</div>
}
```

### Handle all four async states

Every component that renders async data MUST handle all four states explicitly: loading, error, empty, and data. Skipping any of these creates broken UX.

```tsx
// Good - all four states
export function FeedbackList() {
  const { data, error, isLoading } = useSWR<FeedbackListResponse>(API_ROUTES.feedback.list, fetcher)
  
  if (isLoading) return <FeedbackListSkeleton />
  if (error) return <ErrorMessage>Failed to load feedback. {error.message}</ErrorMessage>
  if (!data || data.items.length === 0) return <EmptyState message="No feedback yet" />
  
  return (
    <div className="space-y-3">
      {data.items.map((item) => <FeedbackCard key={item.id} item={item} />)}
    </div>
  )
}

// Bad - happy path only
export function FeedbackList() {
  const { data } = useSWR<FeedbackListResponse>(API_ROUTES.feedback.list, fetcher)
  return <div>{data?.items.map((item) => <FeedbackCard key={item.id} item={item} />)}</div>
}
```

## Type safety

### Strict mode required

`tsconfig.json` must have `"strict": true`. Don't relax it. Every type error is a real bug.

### No `any`

Never use `any`. If a type is genuinely unknown, use `unknown` and narrow with type guards.

```tsx
// Good
function parseEvent(raw: unknown): FeedbackOut | null {
  if (typeof raw !== "object" || raw === null) return null
  if (!("id" in raw) || typeof (raw as Record<string, unknown>).id !== "string") return null
  return raw as FeedbackOut  // narrowed enough to assert
}

// Bad
function parseEvent(raw: any): FeedbackOut {
  return raw
}
```

### API types mirror backend schemas

Define API response types in `lib/api/types.ts`. They must match what the backend returns. When the backend changes, update these types in the same PR.

```tsx
// lib/api/types.ts
export type Sentiment = "positive" | "neutral" | "negative"

export type FeedbackStatus = "processing" | "completed" | "failed" | "skipped"

export type FeedbackOut = {
  id: string
  text: string
  status: FeedbackStatus
  sentiment: Sentiment | null
  themes: string[]
  action_items: string[]
  language: string | null
  skip_reason: string | null
  created_at: string
  updated_at: string
}

export type FeedbackListResponse = {
  items: FeedbackOut[]
}

export type StatsOut = {
  themes: { name: string; count: number }[]
  sentiment_dist: Record<Sentiment, number>
  trend: { date: string; positive: number; neutral: number; negative: number }[]
  processing_count: number
}
```

### `as const` for readonly objects and arrays

Use `as const` so TypeScript infers the narrowest possible type and the value is immutable.

```tsx
// Good
export const SENTIMENT_LABELS = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
} as const

// Bad - widens to Record<string, string>, loses key narrowing
export const SENTIMENT_LABELS = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
}
```

## No magic values

If a value could vary, repeat, or change with environment, it does NOT live inline in components.

| Type of value | Where it lives |
|---|---|
| API route paths | `lib/api/routes.ts` as `API_ROUTES` constant. All versioned paths include the `/v1/` prefix (e.g. `feedback: { list: "/v1/feedback" }`); operational endpoints like `/health` stay unprefixed. |
| Sentiment colors / labels / chart fills | `lib/sentiment.ts` as `SENTIMENT_STYLES`, `SENTIMENT_COLORS`, `SENTIMENT_LABELS` |
| UI timings (debounce, polling, animation) | `lib/constants.ts` as `UI_TIMINGS` |
| API base URL | `process.env.NEXT_PUBLIC_API_BASE_URL` (with sensible default) |
| Repeated string literals | Module-level constants with descriptive names |

```tsx
// Good
import { API_ROUTES } from "@/lib/api/routes"
import { SENTIMENT_STYLES } from "@/lib/sentiment"
import { UI_TIMINGS } from "@/lib/constants"

const { data } = useSWR(API_ROUTES.feedback.list, fetcher)
{item.sentiment && (
  <Badge className={SENTIMENT_STYLES[item.sentiment]}>
    {SENTIMENT_LABELS[item.sentiment]}
  </Badge>
)}
useDebouncedValue(query, UI_TIMINGS.searchDebounceMs)

// Bad
const { data } = useSWR("/api/feedback", fetcher)
<Badge className="bg-emerald-100 text-emerald-700">{item.sentiment}</Badge>
useDebouncedValue(query, 300)
```

Rule of thumb: if a string or number appears in two or more files, extract it to a constant.

## Data fetching

### All HTTP through the typed client

`lib/api/client.ts` is the single entry point for HTTP. Components NEVER call `fetch()` directly.

```tsx
// Good
import { apiClient } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"

const data = await apiClient.get<FeedbackListResponse>(API_ROUTES.feedback.list)

// Bad - inline fetch
const response = await fetch("http://localhost:8000/feedback")
const data = await response.json()
```

The client handles base URL resolution, error mapping, and request ID propagation in one place.

`apiClient` uses relative paths via empty-string base URL: `fetch("/v1/feedback")` becomes a same-origin request which nginx proxies to the backend. No `NEXT_PUBLIC_API_BASE_URL` needed in deployment.

The `apiClient.ts` implementation includes a 30-second timeout via `AbortController`. Without this, a hung backend leaves the UI waiting forever — every fetch call must have an upper bound.

### All UI data through SWR

Components subscribe to data via SWR. Never `useState` + `useEffect` + `fetch` for data fetching.

The SWR `fetcher` wraps `apiClient.get` so all HTTP goes through one place. Define it in `lib/api/client.ts` as `fetcher = (url) => apiClient.get(url)`.

```tsx
// Good
const { data, error, isLoading, mutate } = useSWR(API_ROUTES.feedback.list, fetcher)

// Bad - manual state management
const [data, setData] = useState(null)
const [error, setError] = useState(null)
useEffect(() => {
  fetch("/api/feedback").then((r) => r.json()).then(setData).catch(setError)
}, [])
```

### Mutate after writes

After a write operation, use SWR's `mutate(key)` to invalidate affected caches and trigger revalidation.

```tsx
// Good
async function handleSubmit(text: string) {
  await apiClient.post(API_ROUTES.feedback.create, { texts: [text] })
  await mutate(API_ROUTES.feedback.list)
  await mutate(API_ROUTES.stats.summary)
}

// Bad - manual refetch
async function handleSubmit(text: string) {
  await fetch("/api/feedback", { method: "POST", body: ... })
  setRefreshKey((k) => k + 1)
}
```

## Loading states

Every async render path has a skeleton loader, not a spinner. Skeletons:

- Communicate the shape of incoming content.
- Don't shift layout when real content loads.
- Use shadcn/ui's `Skeleton` component for consistency.

## Optimistic updates

For the feedback submission flow:

- Show the new row immediately with status `processing`.
- The backend confirms via SSE.
- If submission fails, show an error and remove the row.

This makes the UI feel instant. The pattern lives in the submission hook, not scattered across components.

## Styling

### Tailwind utilities only

No custom CSS files except `globals.css` for Tailwind imports and minimal global resets. No CSS-in-JS. No CSS modules.

```tsx
// Good
<div className="flex items-center justify-between gap-4 p-4 rounded-lg border">
  <span className="text-sm font-medium text-slate-900">{label}</span>
  <span className="text-2xl font-bold">{value}</span>
</div>

// Bad - inline style
<div style={{ display: "flex", padding: 16 }}>...</div>
```

### shadcn/ui components used as-is

Don't override shadcn theme. Don't customize colors via CSS variables. Use the components as installed.

```tsx
// Good
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

<Card>
  <Badge>{label}</Badge>
</Card>

// Bad - custom theme override
<Card style={{ backgroundColor: "#ff00ff" }}>...</Card>
```

### Sentiment colors via the central map

Never inline sentiment colors. Always go through `SENTIMENT_STYLES` so the convention stays consistent.

```tsx
// Good
import { SENTIMENT_STYLES, SENTIMENT_LABELS } from "@/lib/sentiment"
{sentiment && (
  <Badge className={SENTIMENT_STYLES[sentiment]}>
    {SENTIMENT_LABELS[sentiment]}
  </Badge>
)}

// Bad
<Badge className={sentiment === "positive" ? "bg-green-100" : "bg-red-100"}>{sentiment}</Badge>
```

### Spacing consistency

Use Tailwind's default spacing scale. Default to `gap-4`, `p-4`, `space-y-4` everywhere unless there's a specific reason to differ. Consistent spacing reads as designed even when no design effort went in.

## Hooks

### Custom hooks for repeatable logic

If two components need the same pattern (debounced search, SSE connection, polling), extract to a hook in `hooks/`.

```tsx
// hooks/useDebouncedValue.ts
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
```

### Hooks rules

- Call hooks only at the top level of a component or another hook.
- Don't call hooks inside loops, conditions, or nested functions.
- Hook names must start with `use`.

These are React rules, not project conventions, but worth restating.

### Cleanup in useEffect

Always return a cleanup function from `useEffect` for subscriptions, intervals, timers, or external resources.

```tsx
// Good
useEffect(() => {
  const eventSource = new EventSource(url)
  eventSource.addEventListener("message", handleMessage)
  
  return () => {
    eventSource.close()
  }
}, [url])

// Bad - leaks the connection
useEffect(() => {
  const eventSource = new EventSource(url)
  eventSource.addEventListener("message", handleMessage)
}, [url])
```

## Imports

Order: React/Next.js → third-party libraries → `@/` aliases → relative imports.

```tsx
// Good
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import useSWR, { mutate } from "swr"
import { formatDistanceToNow } from "date-fns"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { apiClient } from "@/lib/api/client"
import { API_ROUTES } from "@/lib/api/routes"
import { SENTIMENT_STYLES } from "@/lib/sentiment"
import type { FeedbackOut } from "@/lib/api/types"

import { FeedbackCardSkeleton } from "./FeedbackCardSkeleton"
```

Type-only imports use `import type` to make tree-shaking unambiguous.

## Error handling

### Error boundaries for component trees

Wrap major sections in error boundaries so one component crashing does not blank the whole page. Next.js App Router provides `app/error.tsx` (route-level error boundary) and `app/not-found.tsx` (404 page) for this. **Both must exist** — without `error.tsx`, an uncaught error renders the framework default; without `not-found.tsx`, navigating to an unknown path shows a generic page.

### User-friendly error messages

When an error reaches the user, show something actionable. Not stack traces. Not raw error objects.

```tsx
// Good
if (error) return <ErrorMessage>Could not load feedback. Try refreshing.</ErrorMessage>

// Bad
if (error) return <div>{JSON.stringify(error)}</div>
```

### Log unexpected errors

For errors that shouldn't happen, log them so you can investigate. Use a logger module, not `console.log` in committed code.

## Comments

Code should be self-documenting through good naming. Comments only when WHY isn't obvious.

```tsx
// Good - explains a non-obvious choice
// We close the SSE connection when no rows are processing
// to avoid holding open connections for users who never submit feedback.
useFeedbackStream({ enabled: hasProcessingItems })

// Bad - restates the code
// Set isLoading to true
setIsLoading(true)
```

No `console.log` in committed code. No commented-out code in commits.

## Accessibility basics

- Every interactive element is keyboard-accessible (use `<button>`, not `<div onClick={...}>`)
- Form inputs have associated labels
- Images have `alt` text (or empty `alt=""` if purely decorative)
- Focus indicators are visible (don't override Tailwind's focus rings without a replacement)
- Color is never the only signal (sentiment cards use the label text, not just the color)

These are non-negotiable. The dashboard should be navigable with keyboard alone.

## Testing

Frontend tests are minimal for this PoC. We test:

- Pure utility functions (sentiment color mapping, date formatters)
- Critical hooks in isolation (e.g. `useFeedbackStream` lifecycle)
- One smoke test that the page renders without crashing

Visual regression and full integration tests are out of scope for the PoC.