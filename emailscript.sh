#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
email_dir="$script_dir/emails"
upload_url="${AIRGUARD_UPLOAD_URL:-http://127.0.0.1:8000/api/v1/measurements/govee/}"
: "${AIRGUARD_INGEST_TOKEN:?Set AIRGUARD_INGEST_TOKEN before uploading measurements}"

mkdir -p "$email_dir/read"
shopt -s nullglob
for file in "$email_dir"/*.csv; do
  curl --fail --show-error --silent --retry 3 -H "Authorization: Bearer $AIRGUARD_INGEST_TOKEN" -F "file=@$file" "$upload_url"
  mv "$file" "$email_dir/read/"
done
