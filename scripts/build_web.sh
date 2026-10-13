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
BUILD_ID="${BUILD_ID:-$(git rev-parse --short HEAD 2>/dev/null || echo "local-$(date +%s)")}"

echo "==> building web app (base=${BASE_PATH}, build=${BUILD_ID})"
VITE_BASE_PATH="${BASE_PATH}" BUILD_ID="${BUILD_ID}" npm run build

mkdir -p dist
printf '{"build":"%s"}\n' "${BUILD_ID}" > dist/version.json
echo "==> wrote dist/version.json (${BUILD_ID})"