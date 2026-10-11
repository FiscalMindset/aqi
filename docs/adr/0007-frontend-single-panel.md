# ADR 0007: Exclusive rendering of mobile sheet vs desktop panel

## Status
Accepted

## Context
Rendering both the mobile bottom sheet and the desktop side panel (with `md:` CSS classes) duplicated DOM nodes, including `id` attributes like `estimate-heading` — an accessibility failure found by axe.

## Decision
A `useMediaQuery("(min-width: 768px)")` hook renders exactly one of the two. Tests then find a single estimate panel, and ids are unique.

## Consequences
- One estimate query per viewport (also cheaper).
- Playwright's mobile projects exercise the sheet; desktop projects the panel.
