#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BUILD_ID="${GITHUB_SHA:-$(git rev-parse HEAD)}"
node scripts/build-offline-data-manifest.mjs "$BUILD_ID"
GITHUB_PAGES=true VITE_BUILD_ID="$BUILD_ID" pnpm exec vite build

rm -rf docs assets __manus__
rm -f index.html .nojekyll
rm -f service-worker.js service-worker-*.js pwa-version.json
cp -a dist/public/. .
rm -rf __manus__
# Vite does not copy the large seek sidecars into the repository root in this
# layout; the browser fetches them from BASE_URL/index-seek at runtime.
rm -rf index-seek
mkdir -p index-seek
cp -a client/public/index-seek/. index-seek/
touch .nojekyll
node scripts/build-pwa-assets.mjs "$ROOT" "$BUILD_ID" "/maagarim_all/"

echo "GitHub Pages site built at the repository root: $ROOT"
echo "The static UI uses public Git LFS Range requests and compact sidecar indexes for ID, phone, text, Facebook ID, and family search; source rows remain unchanged."
