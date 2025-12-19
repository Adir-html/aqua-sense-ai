#!/usr/bin/env bash
# Wait for API readiness
# Usage: ./scripts/wait-for-api.sh [url] [timeout]

URL=${1:-http://localhost:8000/health}
TIMEOUT=${2:-60}
START=$(date +%s)

echo "Waiting for $URL"
while true; do
  if command -v curl >/dev/null 2>&1; then
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL" || echo "000")
    if [ "$STATUS" -eq 200 ]; then echo "OK"; exit 0; fi
  else
    python - <<PY
import sys,urllib.request
try:
    r=urllib.request.urlopen("${URL}", timeout=5)
    sys.exit(0 if r.getcode()==200 else 1)
except:
    sys.exit(1)
PY
    if [ $? -eq 0 ]; then echo "OK"; exit 0; fi
  fi

  NOW=$(date +%s)
  ELAPSED=$((NOW-START))
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then echo "Timeout after $TIMEOUT seconds"; exit 1; fi
  sleep 2
done
