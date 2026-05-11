# Frontend conventions

Project-specific rules for `frontend/`. Generic React/TypeScript (named exports, no `any`, hooks rules, accessibility basics) is assumed — this file documents what's load-bearing for *this* codebase.

## Folder structure

```
frontend/src/
├── app/                         Next.js 16 App Router
│   ├── layout.tsx               Server component, root layout
│   ├── page.tsx                 Dashboard (KPIs + summary + charts)
│   ├── add/page.tsx, feedback/page.tsx
│   ├── error.tsx                Route-level error boundary ('use client')
│   ├── not-found.tsx            404 page
│   └── globals.css              @import "tailwindcss" + @theme inline
├── components/
│   ├── ui/                      shadcn primitives (forwardRef inside, do not refactor)
│   ├── shared/                  Cross-feature: HealthCheck, ProcessingPill, ToastStack
│   ├── feedback/                PasteForm, FeedbackList, FeedbackCard, FeedbackTable
│   └── stats/                   KpiCard, StatsDashboard, ThemeFrequencyChart, SentimentTrendChart
├── hooks/                       useFeedbackStream, useToast, useDashboardStats, useDebouncedValue
├── lib/
│   ├── api/                     client.ts, routes.ts, types.ts
│   ├── constants.ts             UI_TIMINGS, UI_DIMENSIONS
│   ├── sentiment.ts             SENTIMENT_STYLES, SENTIMENT_LABELS
│   └── utils.ts                 cn() helper from shadcn
└── locales/en/                  Typed string modules — direct imports, NO barrel file
    ├── common.ts, feedback.ts, stats.ts
```

## Dashboard composition

The home page `/` is the executive view — no input forms. Top → bottom:

- **5 KPI cards** in `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`. Order: **Total feedback, Positive, Neutral, Negative, Today** (with day-over-day trend arrow). The three sentiment tiles cover the PDF's "sentiment distribution" requirement at a glance — counts not percentages so all three numbers add to `total_extracted` and the user can sanity-check by addition. `KpiCard.trend` prop (`"up"|"down"|"flat"|null`) renders a colored Unicode arrow; the arrow appears only when `|delta_pct| > 5pp` and `delta_pct === null` hides it entirely. `KPI_COUNT = 5` so skeleton state matches loaded without a layout jump. **Earlier iterations included Avg latency and Total tokens tiles** — both got cut once Neutral became a first-class number, because LLM cost/latency is operator-facing telemetry that doesn't belong on a single-user dashboard alongside the four product KPIs.
- **AI summary widget** sandwiched between KPIs and charts. Sources `GET /api/v1/summary` once per page; server owns freshness via Redis TTL. Manual refresh hits `POST /api/v1/summary/refresh` and writes back via `mutate(fresh, { revalidate: false })`. Refresh failures surface as toasts — never `console.log` in committed code. Footer shows `Updated Xm ago` + `· from cache` when payload came from cache. The widget renders raw text from `summary.text` in a fixed-footprint card; the active prompt (`summary/v1.2`) targets 380-500 chars so the card doesn't reflow when output length varies.
- **Two charts side-by-side** below (`md:grid-cols-2`). Top themes (horizontal bar, last 7 days, top 10, reads `data.top_themes`). Sentiment trend (stacked bar, last 14 days, reads `data.sentiment_trend`). The Top-themes chart aggregates per-feedback theme labels across the corpus — each feedback contributes up to 3 themes (capped by `extraction/v1.3`), and the chart shows the 10 most-mentioned distinct theme names. Horizontal scroll wrapper is defensive for when `stats_top_themes_limit` gets raised above what fits in the viewport.

All three routes (`/`, `/add`, `/feedback`) put their `<h1>` directly in `app/<route>/page.tsx`, not inside child components.

## Tooling

Next.js 16 (App Router, Turbopack default), TypeScript 5.9 strict, React 19, Tailwind v4 (CSS-first config), shadcn/ui on `@base-ui/react`, SWR for data fetching, date-fns for relative timestamps. npm for package management. Deploys via `next start` as a Node server (not static export) — preserves the full Next.js feature surface for future auth additions.

## React 19 specifics

- **Use `ref` as a normal prop, not `forwardRef`.** Exception: shadcn primitives in `components/ui/` still use `forwardRef` for backward compat — don't refactor library code.
- **Server Components by default.** Add `'use client'` only when needed: state, effects, event handlers, browser APIs.
- **Server Actions deliberately not used.** Separate FastAPI backend; mutations go through REST. Architectural choice, not unawareness.

## Tailwind v4 specifics

- `@import "tailwindcss"` in `globals.css`, NOT the three `@tailwind` directives
- `@theme inline` in CSS for theme customization, NOT a JS config block
- `@tailwindcss/postcss` plugin, NOT `tailwindcss` + `autoprefixer`
- Built-in palette uses `oklch()` (modern wider-gamut color space)

## No barrel files (in our own code)

Per Vercel + Next.js 2026: barrel files in your own code harm tree-shaking and bundle size. Direct leaf-file imports only:

```ts
import { feedback } from "@/locales/en/feedback"        // ✓
import { PasteForm } from "@/components/feedback/PasteForm"  // ✓
import { feedback } from "@/locales"                    // ✗ barrel
```

**Do not create `index.ts` files in `components/`, `locales/`, `hooks/`, or `lib/`.** Lint check: `find src -name "index.ts" -not -path "*/node_modules/*"` should return zero matches.

Exception: third-party libraries (lucide-react, shadcn/ui) — their barrels are optimized via `experimental.optimizePackageImports` in `next.config.js`.

## No magic values

Every tunable lives in one of three homes — never inline.

| Type | Where it lives |
|---|---|
| API route paths | `lib/api/routes.ts` as `API_ROUTES` (`as const`) — versioned paths include `/v1/`, ops endpoints don't |
| UI timings (polling intervals, debounces, animations, request timeouts) | `lib/constants.ts` as `UI_TIMINGS` (`as const`) |
| UI dimensions (textarea rows, chart slot widths, label heights) | `lib/constants.ts` as `UI_DIMENSIONS` (`as const`) |
| User-facing strings | `locales/en/{common,feedback,stats}.ts` (`as const`, direct leaf imports) |
| Sentiment / status visual maps | `lib/sentiment.ts` (`SENTIMENT_STYLES`, `SENTIMENT_LABELS`) |
| API base URL | `process.env.NEXT_PUBLIC_API_BASE_URL` (empty-string fallback) — read once in `lib/api/client.ts` |
| Backend-controlled values (page sizes, validation thresholds) | NOT in frontend code. Backend Settings is the source of truth; frontend reads via API |
| Tailwind utility classes (`gap-4`, `p-6`) | Leave inline — design tokens, not magic numbers |

Workflow for a new tunable: add key to the right `as const` object → add trailing comment explaining what consumes it → direct-import the leaf.

## Toast notifications

Transient feedback via `useToast` hook + `ToastStack` (mounted once in `app/layout.tsx`). Backs onto module-level singleton state with subscribe/notify, so any component can trigger a toast that the single global stack renders — avoids React Context boilerplate for intrinsically global UI.

```tsx
const { showToast } = useToast()
showToast("Feedback added", { variant: "success" })
showToast("Could not connect", { variant: "error", durationMs: 6000 })
```

Variants: `"success"` (emerald), `"error"` (rose), `"info"` (slate, default). Default duration 4s. Cap of 5 visible — oldest dropped when 6th arrives. Use `flushSync` from `react-dom` for synchronous DOM updates when ordering matters (toast queues, focus). `crypto.randomUUID()` for client-side IDs — **never install a `uuid` library**.

## Multi-paste in PasteForm

Radio toggle between single (whole textarea = 1 feedback) and multiple (split by `splitFeedbackTexts(text)`). Splitter logic:
1. Tries blank-line separation first (`\n\s*\n+`) — paragraph-style copy from emails/Slack
2. Falls back to single-newline split (`\n+`) — spreadsheet column copy
3. Treats no-newline input as one feedback

Live count below textarea; turns destructive when `count > MAX_BATCH_SIZE` (50). Submit button disables in that state — backend rejects > 50 with 422 anyway, but stopping at the form is friendlier than a round-trip error.

## API types mirror backend

Types in `lib/api/types.ts` must match what the backend returns. Update together in the same PR. The shape:

```ts
type Sentiment = "positive" | "neutral" | "negative"
type FeedbackStatus = "processing" | "completed" | "failed" | "skipped"

type FeedbackOut = {
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
```

Use `as const` for readonly maps so TypeScript narrows keys (`SENTIMENT_LABELS["positive"]` → `"Positive"`, not `string`).

## Data fetching

- **All HTTP through `lib/api/client.ts`.** Components NEVER call `fetch()` directly. The client handles base URL resolution (empty-string base → same-origin → nginx proxies to backend), error mapping, and a 30-second `AbortController` timeout.
- **All UI data through SWR.** Never `useState` + `useEffect` + `fetch` for data. SWR `fetcher = (url) => apiClient.get(url)` lives in `lib/api/client.ts`.
- **Adaptive polling** via function-shaped `refreshInterval`: 5s when `pending_count > 0`, 30s when idle. Pattern lives in `useDashboardStats`.
- **Mutate after writes.** After POST/PATCH/DELETE, call `mutate(key)` to invalidate caches. For paginated caches use the predicate form — see the gotcha below.

## Optimistic updates

For feedback submission: show the new row immediately as `processing` → backend confirms via SSE → if submission fails, show error toast and remove the row. Makes the UI feel instant. Pattern lives in the submission hook, not scattered across components.

## Loading states

Every async render path uses a **skeleton loader, not a spinner**. Skeletons communicate the shape of incoming content and don't shift layout when real content loads. Use shadcn/ui's `Skeleton` for consistency.

Every component that renders async data MUST handle all four states explicitly: loading, error, empty, data. Skipping any creates broken UX.

## Sentiment colors via the central map

```tsx
<Badge className={SENTIMENT_STYLES[sentiment]}>{SENTIMENT_LABELS[sentiment]}</Badge>
```

Never inline sentiment colors. Always go through `lib/sentiment.ts` so the convention stays consistent across cards, badges, charts.

## Testing strategy (deliberate)

Frontend has no tests for the take-home. Visual evaluation by grader is sufficient signal for a single-user demo. Backend Tier 1 only: `test_validate.py`, `test_extract.py` (mocked Anthropic), `test_feedback_service.py` (fake repo).

## Environment

The frontend container has no env file in deployment. `apiClient.ts` uses relative paths (`/v1/feedback`) which nginx routes to the backend on the internal docker network. `NEXT_PUBLIC_API_BASE_URL` is unset; falls back to empty-string base.

Server-only env vars (e.g. `AUTH_SECRET` later) would live in `frontend/.env.local` without the `NEXT_PUBLIC_` prefix — stays server-side, never bundles into the browser. Running as a Node server (not static export) is what makes this distinction work.

## SSE wiring

`useFeedbackStream({ enabled })` exposes four handler slots: `onFeedbackUpdate`, `onStatsInvalidate`, `onConnected`, `onError`. EventSource owns the reconnect loop; cleanup closes the source on unmount. **Gated on `pending_count > 0`** so we don't hold open connections for users who never submit.

Used on:
- `/feedback` page — predicate-based SWR cache patch on `feedback_update`, `mutate(API_ROUTES.stats)` on `stats_invalidate`. Rows visibly transition from spinning "Processing" badge to colored sentiment as workers complete.
- `/` (dashboard) — only listens to `stats_invalidate` to refetch pending-count + KPIs. The adaptive SWR poll keeps things accurate even without SSE; SSE just shortens latency.

`ProcessingPill` shows in the page header next to "Dashboard" when `stats.pending_count > 0`. Self-hiding (`if count <= 0 return null`) so the page can render it unconditionally.

## Gotchas

Frontend-specific things we've hit. Cross-cutting gotchas (nginx restart, `.env` sync) live in the root `CLAUDE.md`.

- **shadcn v4 + Tailwind v4 theme variables are full `oklch(...)` values, not raw HSL components.** Templates that say `hsl(var(--primary))` produce `hsl(oklch(...))` → invalid CSS, color renders as black. Use `var(--primary)` directly. Same for `--muted-foreground`, `--popover`, `--border`.

- **shadcn auto-init rewrites `layout.tsx`.** Re-running `npx shadcn@latest init -d` adds a `Geist` font + body className override and clobbers your customizations (locale strings, body utility classes). Diff and reconcile.

- **`Geist` from `next/font/google` only works on Next 15+.** On older versions, `npm install geist` + `import { GeistSans } from "geist/font/sans"`. We're on Next 16 so the built-in path works.

- **recharts v3 `Tooltip` formatter has strict types.** Runtime signature gives you `(value: ValueType | undefined, name: NameType, ...) => ReactNode`. Writing `(value: number) => ...` fails. Either let TS infer and cast inside, or match the full signature with recharts' `ValueType`/`NameType` exports. Same trap for `Bar` chart's `Cell` `fill` prop and Legend's `payload` shapes.

- **recharts colors must be CSS color strings, not Tailwind classes.** `fill="bg-primary"` does nothing. Use `fill="var(--primary)"` for theme-aware fills, or literal hex for fixed colors. Sentiment colors are deliberately literal hex so positive=green/negative=red doesn't shift on dark mode.

- **`'use client'` required for any component using SWR or `useState`.** Server components can't run hooks. `app/page.tsx` is `'use client'` because it uses `mutate()` in callbacks; otherwise default to server components.

- **Optimistic SWR mutate uses different revalidate rules per cache.** In `app/page.tsx`'s `handleCreated`: feedback list gets the new row prepended *without* revalidate (we already have it); stats gets a plain `mutate(key)` to force re-fetch (we'd compute it wrong locally). Don't blanket-disable revalidation across both.

- **EventSource doesn't reconnect on HTTP errors.** Silently retries on transient drops, but on 4xx/5xx it stops entirely. Every page that subscribes goes silent and never recovers without a hard refresh. Smoke-test SSE after deploys with `curl -N /api/v1/events`.

- **`useFeedbackStream` deps array is `[]` on purpose.** The hook reads handlers via a ref so callers pass inline closures without re-creating the EventSource. If you put `[handlers]` in deps, every parent re-render tears down + recreates the connection — symptom: flurry of `connected` events in the log.

- **Predicate-based `mutate()` for paginated caches.** On a `feedback_update` event, `mutate(specificUrl, ...)` only patches one query-param permutation. Use the predicate form: `mutate((key) => typeof key === "string" && key.startsWith(API_ROUTES.feedbackPaginated), patcher, { revalidate: false })` so every cached page gets the patch.

- **recharts has no native "frozen axis" support, and the obvious "two-chart sidecar" approach silently breaks.** Rendering a fixed-width left chart with `<YAxis />` only and a scrollable right chart with `<YAxis hide />` doesn't work — recharts has zero plot area to position tick labels against, and labels just don't render. The working pattern is **HTML-positioned axis labels** computed from shared geometry constants. See `ThemeFrequencyChart.tsx`:
  ```
  plotTopPx = TOP_MARGIN_PX
  plotBottomPx = chartHeight - BOTTOM_MARGIN_PX - labelHeight
  topPx for tick T = plotBottomPx - (T / max) * (plotBottomPx - plotTopPx) - lineHalfHeight
  ```
  Render `<span class="absolute" style={{top: topPx}}>{T}</span>` in a `position: relative` sidecar, with the scrollable chart next to it (`overflow-x-auto`, `<YAxis hide width={0} />`, same `domain`/`ticks` so bars scale correctly).

- **Pin chart axis domains for visual stability.** Auto-scaled axes look great on a single screenshot but make day-over-day comparison impossible — a bar that meant "10 mentions" yesterday and today renders at different heights when the dataset grows. Use explicit `domain={[0, MAX]}` + `ticks={[...]}` from `UI_DIMENSIONS` constants. Counts above the ceiling clip rather than rescale.

- **High-cardinality charts need a slot-min-width strategy, not a cap on data.** For charts that can plausibly receive 50+ items, set a min px slot per item via `UI_DIMENSIONS.<chart>SlotMinPx`, compute inner width as `items.length × slotMinPx`, wrap in `overflow-x-auto`. The API returns all data; the UI decides display.

- **Long rotated XAxis labels need explicit `height`.** A 24-char label at fontSize 11 (~144px wide) rotated -35° drops ~83px vertically. Default XAxis height ~30px → labels clip into the next element. Reserve via `UI_DIMENSIONS.<chart>LabelHeightPx`; compute diagonal drop with `width × sin(angle)`.
