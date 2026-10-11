---
name: frontend
description: Frontend skill for Dhuan Detective. Use when adding or changing React screens, components, hooks, i18n strings, or the API client in frontend/src. Enforces the mobile-first responsiveness, WCAG 2.2 AA accessibility, colour-with-icon pairing, PWA behaviour, demo-banner rule, and the vitest/Playwright/axe/Lighthouse gates.
---

# Frontend engineering skill

## When to use

Any change under `frontend/src/` — routes, components, features, hooks, lib, i18n.

## Responsiveness rules (brief §5.3)

- Design at **360 px first**; verify 360, 390, 768, 1024, 1440 and landscape.
- Mobile: map full screen + draggable bottom sheet (peek/half/full, 44px handle, touch drag).
- Desktop ≥768px: exclusive side panel (never render both — duplicate ids break a11y).
- No horizontal scroll at any width; `dvh` units; `env(safe-area-inset-*)`.
- Touch targets ≥ 44px (test asserts it).

## Accessibility checklist (WCAG 2.2 AA)

- [ ] Keyboard reachable; visible focus ring
- [ ] Skip link targets `#main`
- [ ] `aria-live` for result regions
- [ ] Colour never alone: category chip = colour + icon + text
- [ ] Loading → skeleton with `aria-busy`; failure → `role="alert"` with retry
- [ ] New strings added to **both** `i18n/en.json` and `i18n/hi.json`

## Rule 1 in practice

If a response carries `X-Dhuan-Demo: 1`, the document is marked `data-demo="1"` and `DemoBanner` renders permanently. Never suppress it.

## Performance budget

- Map and chart bundles are code-split; MapLibre loads on idle (`useIdleCallback`).
- Lighthouse CI asserts performance ≥ 85, a11y ≥ 95, best-practices ≥ 95, SEO ≥ 90 (mobile).
- Don't add a dependency without considering the bundle split.

## API client contract (`src/lib/api.ts`)

- Same-origin `/v1`; problem+json → `ApiError`; expose header handling for the demo banner; 15s abort timeout.

## Commands (run before every commit)

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run test:unit        # 45 tests, thresholds enforced
npx playwright test      # 80 tests: 4 projects + axe + responsive
```
