#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p logs

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
LOG_FILE="$ROOT_DIR/logs/analyze_profile_${TIMESTAMP}.log"
PID_FILE="$ROOT_DIR/logs/analyze_profile.pid"
LATEST_LINK="$ROOT_DIR/logs/analyze_profile_latest.log"

CMD=(
  uv run python -m src.user_profile_analyzer.analyze_profile
  --log-file "$LOG_FILE"
  --no-progress
)

if [[ $# -gt 0 ]]; then
  CMD+=("$@")
fi

nohup "${CMD[@]}" >/dev/null 2>&1 &
PID=$!

echo "$PID" > "$PID_FILE"
ln -sfn "$LOG_FILE" "$LATEST_LINK"

echo "Started analyze_profile in background"
echo "PID: $PID"
echo "Log: $LOG_FILE"
echo "Latest log symlink: $LATEST_LINK"
echo "Watch: tail -f $LATEST_LINK"
