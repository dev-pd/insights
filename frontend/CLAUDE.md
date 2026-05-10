# Frontend conventions

How to write TypeScript and React code in this project. Applies to everything under `frontend/`. These are non-negotiable conventions: when generating or editing frontend code, follow them without exception.

## Folder structure

```
frontend/src/
├── app/                         # Next.js 16 App Router
│   ├── layout.tsx               # Server component, root layout
│   ├── page.tsx                 # Home page
│   ├── error.tsx                # Route-level error boundary ('use client')
│   ├── not-found.tsx            # 404 page
│   └── globals.css              # @import "tailwindcss" + @theme inline
├── components/
│   ├── ui/                      # shadcn primitives (uses forwardRef internally for React 18 compat)
│   ├── shared/                  # Cross-feature: HealthCheck
│   ├── feedback/                # PasteForm, FeedbackList, FeedbackCard
│   └── stats/                   # KpiCard, ThemeFrequencyChart, SentimentTrendChart, StatsDashboard
├── hooks/                       # Phase 4: useFeedbackStream, useToasts
├── lib/
│   ├── api/                     # client.ts, routes.ts, types.ts
│   └── utils.ts                 # cn() helper from shadcn
└── locales/
    └── en/                      # Typed string modules (direct imports — NO barrel file)
        ├── common.ts            # app, errors, status, actions, loading
        ├── feedback.ts          # pasteForm, list, card, sentiment
        └── stats.ts             # kpis, charts
```

## Tooling and versions

- Next.js 16 with App Router (not Pages Router); Turbopack is the default dev/build engine
- TypeScript 5.9 with `strict: true` in `tsconfig.json`
- React 19 — `forwardRef` is no longer required for refs (ref is a regular prop). Existing shadcn components may still use the older pattern; both work.
- Tailwind v4 (CSS-first config via `@import "tailwindcss"` + `@theme inline`; no `tailwind.config.ts` theme block needed)
- shadcn/ui components on `@base-ui/react` (shadcn v4 default), installed via `npx shadcn@latest add`
- SWR for data fetching and cache mutation
- date-fns for relative timestamps
- Prettier for TypeScript formatting via the Next.js default config

Package management via `npm`. Run dev server with `npm run dev`.

Frontend deploys via `next start` as a Node server, not static export. `next.config.js` does not set `output: 'export'`. This preserves the full Next.js feature surface (middleware, server components, server actions, API routes) for future additions like authentication.

## Modern patterns (2026)

This codebase follows current 2026 best practices. Phase 2-4 code MUST follow these rules.

### React 19 idioms

**Use ref as a normal prop, NOT `React.forwardRef`.**

```tsx
// Good
interface Props {
  ref?: React.Ref<HTMLDivElement>
  children?: React.ReactNode
}
function FeedbackCard({ ref, children }: Props) {
  return <div ref={ref}>{children}</div>
}

// Bad
const FeedbackCard = React.forwardRef<HTMLDivElement, Props>((props, ref) => (
  <div ref={ref}>...</div>
))
```

**Exception:** shadcn primitives in `components/ui/` use `forwardRef` for backward compat with React-18 consumers. Don't refactor library code.

**Use the `use()` hook for promises in Server Components when applicable.** We use SWR for client-side data fetching, which has its own promise handling. The `use()` hook is documented here for completeness; current code does not need it.

**Server Components by default.** Add `'use client'` only when needed: state (`useState`/`useReducer`), effects (`useEffect`), event handlers (`onClick`), browser APIs, or third-party client-only libraries.

### Server Actions: deliberately not used

We have a separate FastAPI backend. Mutations go through the REST API, not Server Actions. This is a deliberate architectural choice (separation of concerns, language-appropriate tooling for LLM work) — not lack of awareness.

### Async cookies / headers (Next.js 15+)

If we add auth or session handling later, `cookies()` and `headers()` must be awaited:

```ts
const cookieStore = await cookies()
const session = cookieStore.get("session")
```

Currently no auth, so unused. Documented for graduation work.

### No barrel files in our own code

Per Vercel and Next.js 2026 recommendations (https://vercel.com/blog/how-we-optimized-package-imports-in-next-js), barrel files in YOUR OWN code harm build performance, tree-shaking, and bundle size.

Direct imports from leaf files only:

```ts
// Good
import { feedback } from "@/locales/en/feedback"
import { PasteForm } from "@/components/feedback/PasteForm"

// Bad
import { feedback, common } from "@/locales"        // no barrel
import { PasteForm, FeedbackList } from "@/components/feedback"   // no barrel
```

Each module is imported directly from its source file. **Do not create `index.ts` files in `components/`, `locales/`, `hooks/`, or `lib/`.**

**Exception:** third-party libraries (lucide-react, shadcn/ui) — their barrels are optimized via `experimental.optimizePackageImports` in `next.config.js`.

### Tailwind v4 conventions

- `@import "tailwindcss"` in `globals.css` (NOT three `@tailwind` directives)
- `@theme inline` directive in CSS for theme customization (NOT JS config object)
- `@tailwindcss/postcss` plugin (NOT `tailwindcss` + `autoprefixer`)
- `@utility` for custom utilities (NOT `@layer`)
- Built-in color palette uses `oklch()` colors (modern color space, wider gamut)

### State management

- **SWR** for server state. Use `mutate()` with optimistic updates for instant UI feedback.
- **`useState`/`useReducer`** for local component state.
- **React 19 Context** for cross-component state (no Redux/Zustand at this scale).

### Toasts and side effects

- Use `flushSync` from `react-dom` for synchronous DOM updates when ordering matters (toast queues, focus management). Setting a toast state inside `flushSync` ensures the toast renders before the next paint.
- `crypto.randomUUID()` for client-side IDs. **Never install a `uuid` library.**

### Performance

- `next.config.js` has `experimental.optimizePackageImports: ['lucide-react']` so only the icons used ship.
- `next/image` for any images (we have none currently).
- Server Components where possible (no `'use client'` unless necessary).
- Bundle analysis: `npx @next/bundle-analyzer` can be added in graduation work.

### TypeScript

- `strict: true` (enforced).
- No `any` types. Use `unknown` for genuinely unknown data.
- Type-only imports: `import type { Foo } from "..."` when only types are needed.
- `as const` for literal type narrowing in constants modules (`locales/en/*.ts` uses this).

### Internationalization (i18n)

User-facing strings live in `src/locales/en/` organized by feature (`common`, `feedback`, `stats`). Components import directly from leaf files:

```tsx
import { feedback } from "@/locales/en/feedback"
return <h1>{feedback.pasteForm.title}</h1>
```

Currently English-only. Adding a locale (e.g., Greek):

1. Create `src/locales/el/` mirroring `src/locales/en/`.
2. Translate strings (preserve key shape exactly).
3. Add a thin `src/lib/i18n.ts` that conditionally re-exports based on env / cookie / middleware.
4. Components migrate from `@/locales/en/*` to `@/lib/i18n`.
5. Or use Next.js i18n routing for full locale-as-URL-prefix support.

Deliberately did NOT install i18next or react-intl. Runtime locale switching machinery is graduation-tier infrastructure. Constants modules with type-safe access via direct imports are sufficient for English-only with a documented migration path.

### Testing strategy (deliberate)

- **Frontend:** no tests written for the take-home. Visual evaluation by grader is sufficient signal.
- **Backend Tier 1 only (Phase 5):** `test_validate.py`, `test_extract.py` (mocked Anthropic), `test_feedback_service.py` (fake repo).
- Repository pattern enables testing services without mocking SQLAlchemy session calls.
- See `NOTES.md` for full testing rationale.

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

**Non-negotiable for Phase 2-5 code.** No inline numbers or repeated strings in components. Every tunable goes to one of three homes.

### Where each kind of value lives

| Type of value | Where it lives | Import path |
|---|---|---|
| **API route paths** | `lib/api/routes.ts` as `API_ROUTES` (`as const`). All versioned paths include `/v1/` prefix; operational endpoints (`/health`, `/ready`) stay unprefixed. | `import { API_ROUTES } from "@/lib/api/routes"` |
| **UI timings** (polling intervals, debounces, animation, request timeouts) | `lib/constants.ts` as `UI_TIMINGS` (`as const`) | `import { UI_TIMINGS } from "@/lib/constants"` |
| **UI dimensions** (textarea rows, default limits, layout sizes) | `lib/constants.ts` as `UI_DIMENSIONS` (`as const`) | `import { UI_DIMENSIONS } from "@/lib/constants"` |
| **User-facing strings** (labels, placeholders, error messages, button text) | `locales/en/{common,feedback,stats}.ts` (`as const`, no barrel file) | `import { feedback } from "@/locales/en/feedback"` (direct, leaf-file imports only) |
| **Sentiment / status visual maps** (planned) | `lib/sentiment.ts` as `SENTIMENT_STYLES`, `SENTIMENT_LABELS` (Phase 3 — not created yet) | `import { SENTIMENT_STYLES } from "@/lib/sentiment"` |
| **API base URL** | `process.env.NEXT_PUBLIC_API_BASE_URL` (empty-string fallback) — read once in `lib/api/client.ts` | n/a — only in `client.ts` |
| **Backend-controlled values** (page sizes, validation thresholds, max body length) | NOT in frontend code. Backend Settings owns these; frontend reads them implicitly via API behavior. | n/a |

```tsx
// Good
import { API_ROUTES } from "@/lib/api/routes"
import { UI_TIMINGS, UI_DIMENSIONS } from "@/lib/constants"
import { feedback } from "@/locales/en/feedback"

const { data } = useSWR(API_ROUTES.feedback, fetcher, {
  refreshInterval: UI_TIMINGS.feedbackListRefreshMs,
})
return (
  <Textarea
    rows={UI_DIMENSIONS.pasteFormRows}
    placeholder={feedback.pasteForm.placeholder}
  />
)

// Bad
const { data } = useSWR("/api/v1/feedback", fetcher, { refreshInterval: 0 })
<Textarea rows={6} placeholder="Paste customer feedback here..." />
```

### Currently defined `lib/constants.ts` (May 2026)

For reference when wiring new code — pick the existing key rather than redefining:

```ts
UI_TIMINGS = {
  apiRequestTimeoutMs: 30_000,        // apiClient AbortController
  healthCheckRefreshMs: 30_000,       // HealthCheck SWR
  feedbackListRefreshMs: 0,           // FeedbackList SWR (no polling in Phase 2)
}

UI_DIMENSIONS = {
  pasteFormRows: 6,                   // Textarea visible rows
}
```

### Workflow when you need a new tunable or string

**For a number / dimension / timing:**
1. Add the key to `UI_TIMINGS` or `UI_DIMENSIONS` in `lib/constants.ts` with `as const` preserved.
2. Add a one-line trailing comment explaining what consumes it.
3. Import via `import { UI_TIMINGS } from "@/lib/constants"` and reference by name.

**For a user-facing string:**
1. Add the key to the right `locales/en/<feature>.ts` (`common` for app-wide, `feedback`/`stats` for feature-scoped).
2. Preserve the `as const` so the type stays narrow and i18n migration stays mechanical.
3. Direct-import the leaf file (`@/locales/en/feedback`) — no barrel file.

**Never:**
- ❌ Inline numeric literals in component JSX (`refreshInterval: 30_000`, `rows={6}`).
- ❌ Inline user-facing strings in components (`<Button>Submit</Button>`).
- ❌ Create a barrel file (`locales/index.ts`, `components/feedback/index.ts`) — see "Modern patterns / No barrel files" above.
- ❌ Hardcode backend-controlled limits in the frontend. Backend Settings is the source of truth; frontend should accept whatever the API returns.

### Rule of thumb

- Number or non-trivial string appears **once but might be tuned** → constant.
- Appears in **two or more files** → constant, no exceptions.
- Is **user-facing copy** → locale file, even if it appears once.
- Is **a Tailwind utility class** (`gap-4`, `p-6`, `h-32`) → leave inline. Those are design tokens, not magic numbers.

Phase 2-5 code MUST NOT introduce new inline timing/dimension literals or hardcoded user-facing strings. Audit your own diff before commit: `grep -nE 'refreshInterval:|rows=\{|setTimeout\([^,]+,\s*[0-9]'` over your changes should return only existing `UI_TIMINGS.*` / `UI_DIMENSIONS.*` references.

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

## Gotchas

Frontend-specific things we've hit. Cross-cutting gotchas (nginx restart, `.env` sync) live in the root `CLAUDE.md`.

- **shadcn v4 + Tailwind v4: theme variables are full `oklch(...)` values, not raw HSL components.** Templates and StackOverflow snippets that say `hsl(var(--primary))` produce `hsl(oklch(...))` → invalid CSS, color renders as black. Use `var(--primary)` directly. Same applies to `--muted-foreground`, `--popover`, `--border`, etc.

- **shadcn auto-init rewrites `layout.tsx`.** `npx shadcn@latest init -d` adds a `Geist` font import + `cn(font.variable)` body className. If you re-init shadcn after Phase 1, expect `layout.tsx` to lose your customizations (locale strings, body utility classes). Diff and reconcile.

- **`Geist` from `next/font/google` only works on Next 15+.** On Next 14, that import fails because Geist isn't in the Google Fonts catalog. Either upgrade to Next 16 (where it's built in) or `npm install geist` and `import { GeistSans } from "geist/font/sans"`. We're on Next 16 so the built-in path works.

- **recharts v3 `Tooltip` formatter has strict types.** The runtime signature gives you `(value: ValueType | undefined, name: NameType, …) => ReactNode`. Writing `(value: number) => …` fails TypeScript. Either let TS infer (`(value) => …`) and cast inside, or match the full signature with the recharts `ValueType`/`NameType` re-exports. Same trap for the `Bar` chart's `Cell` `fill` prop and Legend's `payload` shapes.

- **recharts colors must be CSS color strings, not Tailwind utility classes.** `fill="bg-primary"` does nothing. Use `fill="var(--primary)"` for theme-aware fills, or literal hex (`fill="#1D9E75"`) when you want a fixed color regardless of theme. Sentiment colors in `SentimentTrendChart` are deliberately literal hex so positive=green/negative=red doesn't shift on dark mode.

- **`'use client'` is required for any component using SWR or `useState`.** Server components can't run hooks. Putting `useSWR` in a server component yields a build-time error. The `app/page.tsx` page itself is `'use client'` because it uses `mutate()` in a callback; otherwise default to server components.

- **Optimistic SWR mutate uses `revalidate: false` for one cache, `mutate(key)` for another.** In `app/page.tsx`'s `handleCreated`: feedback list gets the new row prepended *without* revalidate (we already have it), but stats gets a plain `mutate(key)` to force a re-fetch (we'd compute it wrong locally). Don't blanket-disable revalidation across both.

- **No barrel files in `locales/`, `components/`, `hooks/`, or `lib/`.** Direct leaf-file imports only. `import { feedback } from "@/locales/en/feedback"`. The Modern Patterns section above explains why; the lint check is `find src -name "index.ts" -not -path "*/node_modules/*"` should return zero matches.