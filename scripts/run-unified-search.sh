#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${ROOT}/tools/unified-search/unified.sqlite"
DATA_DIR="${DATA_DIR:-${ROOT}/datasets}"
python3 "${ROOT}/tools/unified-search/indexer.py" "$DATA_DIR" --db "$DB"
exec python3 "${ROOT}/tools/unified-search/app.py" "$DB"
