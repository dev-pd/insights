# Frontend conventions

Project-specific rules for `frontend/`. Generic React/TypeScript (named exports, no `any`, hooks rules, accessibility basics) is assumed.

Stack: Next.js 16 (App Router, Turbopack), React 19, TypeScript 5.9 strict, Tailwind v4 (CSS-first), shadcn/ui on `@base-ui/react`, SWR, date-fns. npm for packages. Deploys as a Node server via `next start` (not static export) so middleware / server components / future auth surface stays available.

## Layout rules

- **`components/ui/` is shadcn primitives — DO NOT refactor.** Library code; uses `forwardRef` for backward compat. Everything else uses React 19 `ref`-as-prop.
- **`locales/en/` — direct leaf imports, NO barrel files.** `import { feedback } from "@/locales/en/feedback"`, never from `@/locales`. Same rule for `components/`, `hooks/`, `lib/` — `find src -name "index.ts" -not -path "*/node_modules/*"` should return zero matches. Exception: third-party libs whose barrels are optimized via `experimental.optimizePackageImports`.
- **All three routes (`/`, `/add`, `/feedback`)** put their `<h1>` directly in `app/<route>/page.tsx`, not inside child components.
- **Server Components by default.** Add `'use client'` only when a component needs state, effects, event handlers, or browser APIs.
- **Server Actions deliberately not used** — separate FastAPI backend, mutations go through REST.

## Dashboard composition

`/` is the executive view (no forms). Top → bottom: 6 KPI cards (`grid-cols-2 sm:grid-cols-3 lg:grid-cols-6`) → AI summary widget → two charts side-by-side. Three non-obvious choices:
- **KPI sentiment tiles use counts (not percentages)** so they sum to `total_extracted` and the user can sanity-check by addition. Today's day-over-day arrow only renders when `|delta_pct| > 5pp` (small fluctuations look noisy).
- **Summary widget**: `GET /api/v1/summary` once per page; server owns freshness via Redis TTL. The `summary/v1.2` prompt targets a tight char range so the card doesn't reflow.
- **Theme cap is in `app/llm/schema.py`** (`max_length=3`), not the prompt — frontend assumes ≤3 themes per feedback.

## Tailwind v4 setup gotchas

- `@import "tailwindcss"` in `globals.css`, NOT the three `@tailwind` directives.
- `@theme inline` in CSS for customization, NOT a JS config block.
- `@tailwindcss/postcss` plugin, NOT `tailwindcss` + `autoprefixer`.
- Palette uses `oklch()` (wider-gamut). See the shadcn-v4 gotcha below for the trap.

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

`useToast` + `ToastStack` (mounted once in `app/layout.tsx`). Module-level singleton with subscribe/notify so any component triggers; avoids Context boilerplate for an intrinsically global UI. Variants: `"success"`/`"error"`/`"info"`. Default duration 4s. Cap of 5 visible. Use `flushSync` when ordering matters (queues, focus). `crypto.randomUUID()` for client IDs — **never install a `uuid` library**.

## API types mirror backend

`lib/api/types.ts` must match what the backend returns; update together in the same PR. Use `as const` for readonly maps so TypeScript narrows keys (e.g. `SENTIMENT_LABELS["positive"]` → `"Positive"`, not `string`).

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

## Sentiment styling

Always go through `lib/sentiment.ts` (`SENTIMENT_STYLES`, `SENTIMENT_LABELS`). Never inline sentiment colors — keeps cards/badges/charts consistent.

## Testing

Frontend has no tests for the take-home — visual evaluation is sufficient signal for a single-user demo. Backend Tier 1: only `test_validate.py` for the `NOISE` rule; the eval harness covers LLM behavior.

## Environment

Frontend container has no env file in deployment. `apiClient.ts` uses relative paths (`/v1/feedback`); nginx routes them to the backend on the internal docker network. `NEXT_PUBLIC_API_BASE_URL` is unset → empty-string base. Server-only env vars (e.g. future `AUTH_SECRET`) would live in `frontend/.env.local` without `NEXT_PUBLIC_` — stays server-side, never bundled. Running as a Node server (not static export) is what makes this distinction work.

## SSE wiring

`useFeedbackStream({ enabled })` exposes `onFeedbackUpdate`, `onStatsInvalidate`, `onConnected`, `onError` slots. EventSource owns the reconnect loop; cleanup closes on unmount. **Gated on `pending_count > 0`** so we don't hold open connections for idle users. `/feedback` page does predicate-based SWR cache patches on `feedback_update`; `/` dashboard only listens to `stats_invalidate` (the adaptive SWR poll keeps things accurate even without SSE — SSE just shortens latency).

## Gotchas

Frontend-specific things we've hit. Cross-cutting gotchas (nginx restart, `.env` sync) live in the root `CLAUDE.md`.

- **shadcn v4 + Tailwind v4 theme variables are full `oklch(...)` values, not raw HSL components.** Templates that say `hsl(var(--primary))` produce `hsl(oklch(...))` → invalid CSS, color renders as black. Use `var(--primary)` directly. Same for `--muted-foreground`, `--popover`, `--border`.

- **shadcn auto-init rewrites `layout.tsx`.** Re-running `npx shadcn@latest init -d` adds a `Geist` font + body className override and clobbers your customizations (locale strings, body utility classes). Diff and reconcile.

- **`Geist` from `next/font/google` only works on Next 15+.** On older versions, `npm install geist` + `import { GeistSans } from "geist/font/sans"`. We're on Next 16 so the built-in path works.

- **`'use client'` required for SWR or `useState`.** Server components can't run hooks. `app/page.tsx` is `'use client'` because it uses `mutate()` in callbacks.

- **EventSource doesn't reconnect on HTTP errors.** Silent retries on transient drops, but on 4xx/5xx it stops entirely. Smoke-test SSE after deploys with `curl -N /api/v1/events`.

- **`useFeedbackStream` deps array is `[]` on purpose.** Hook reads handlers via a ref so callers can pass inline closures. Adding `[handlers]` to deps tears down + recreates the EventSource on every parent re-render — symptom: flurry of `connected` events.

- **Predicate-based `mutate()` for paginated caches.** `mutate(specificUrl, ...)` only patches one query-param permutation. Use `mutate((key) => typeof key === "string" && key.startsWith(API_ROUTES.feedbackPaginated), patcher, { revalidate: false })` so every cached page gets the patch.

- **Optimistic SWR mutate uses different revalidate rules per cache.** Feedback list gets the new row prepended *without* revalidate (we already have it); stats gets a plain `mutate(key)` to force re-fetch (we'd compute it wrong locally). Don't blanket-disable revalidation across both.

- **recharts traps** (all hit during chart work):
  - **Colors must be CSS strings, not Tailwind classes.** `fill="bg-primary"` does nothing. Use `fill="var(--primary)"` for theme-aware, or literal hex for fixed (sentiment colors stay green/red on dark mode).
  - **Tooltip formatter has strict types** — `(value: ValueType | undefined, name: NameType, ...) => ReactNode`. Writing `(value: number) => ...` fails. Same for `Cell` `fill` and Legend `payload`.
  - **No native "frozen axis"** — the two-chart sidecar trick fails (zero plot area can't position tick labels). Pattern in `ThemeFrequencyChart.tsx`: HTML-positioned `<span class="absolute">` ticks in a sidecar, scrollable chart next to it sharing `domain`/`ticks`.
  - **Pin axis domains for visual stability.** Use explicit `domain={[0, MAX]}` + `ticks={[...]}` from `UI_DIMENSIONS`; counts above ceiling clip rather than rescale.
  - **High-cardinality**: set per-item `slotMinPx` and `overflow-x-auto`, don't cap data.
  - **Long rotated XAxis labels need explicit `height`.** Reserve via `UI_DIMENSIONS.<chart>LabelHeightPx`; diagonal drop = `width × sin(angle)`.
