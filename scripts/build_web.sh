#!/usr/bin/env bash
# Build the web app and stamp it with a build id.
#
# The id goes into two places that must agree: VITE_BUILD_ID baked into the
# bundle, and dist/version.json served by the API. At startup the app compares
# them. If they differ, the browser is running a bundle from an older deploy -
# almost always because a service worker precached that deploy's index.html - and
# the app clears the caches and reloads itself instead of silently issuing API
# calls that cannot work.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/frontend"

BASE_PATH="${VITE_BASE_PATH:-/}"
HEAD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
BUILD_ID="${BUILD_ID:-${HEAD_SHA}}"

# Fail loudly rather than ship a stamp that lies. The build id is what a browser
# compares against the deployed version.json to decide it is running stale code,
# so a stamp from a different commit makes that check meaningless - and it is
# easy to hit by building before committing.
if [ "${REQUIRE_BUILD_MATCH:-0}" = "1" ] && [ -n "$(git status --porcelain -- frontend scripts)" ]; then
  echo "ERROR: frontend/scripts have uncommitted changes but REQUIRE_BUILD_MATCH=1." >&2
  echo "       Commit first so the build id matches the shipped code." >&2
  exit 1
fi

if [ "${BASE_PATH}" = "/" ] && [ "${REQUIRE_BASE:-0}" != "1" ]; then
  echo "    (no VITE_BASE_PATH set: assets will be referenced from / - correct for"
  echo "     root-served deploys, wrong when the app lives under a stage path)"
fi

echo "==> building web app (base=${BASE_PATH}, build=${BUILD_ID})"
# Type-check and bundle separately so a failing type-check cannot be mistaken
# for a bundling problem, and so the bundle always sees BASE_PATH.
echo "==> type-checking"
npx tsc --noEmit

echo "==> bundling"
VITE_BASE_PATH="${BASE_PATH}" BUILD_ID="${BUILD_ID}" npx vite build

mkdir -p dist
printf '{"build":"%s"}\n' "${BUILD_ID}" > dist/version.json
echo "==> wrote dist/version.json (${BUILD_ID})"