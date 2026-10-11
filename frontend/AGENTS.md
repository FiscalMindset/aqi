# frontend/AGENTS.md

Web app: React 18 + TypeScript strict + Vite + Tailwind + MapLibre PWA.

## Commands

```bash
npm ci
npm run dev            # vite dev server on :5173 (proxies /v1 to :8000)
npm run build
npm run test:unit      # vitest + RTL with coverage thresholds
npx playwright test    # chromium/firefox/webkit/mobile + axe + responsive
npm run lint
npm run typecheck
```

## Rules (short form)

1. Mobile-first at 360px; exclusive rendering of the bottom sheet (mobile) vs side panel (desktop) — never both in the DOM.
2. Colour never alone: CPCB categories always pair colour + icon + text.
3. Demo data banner is permanent and visible whenever the API marks the response (`X-Dhuan-Demo`).
4. New user-facing strings go into **both** `src/i18n/en.json` and `src/i18n/hi.json`.
5. Same-origin `/v1` API base; problem+json errors become typed `ApiError`s.
6. No `any` in `src/`; `noUncheckedIndexedAccess` is on.
7. Map and chart bundles are code-split; MapLibre loads on an idle callback.
8. Accessibility to WCAG 2.2 AA: axe must stay at zero serious/critical on every route.

See `../docs/RULES.md`, `../docs/FRONTEND.md` and the `.opencode/skill/frontend` skill.
