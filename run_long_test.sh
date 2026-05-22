#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/smter-mac/personalAPPS/whisper"
VENV_PY="$PROJECT_DIR/venv/bin/python"
MAIN_PY="$PROJECT_DIR/stream_transcribe.py"

RUN_ID=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$PROJECT_DIR/test_runs/$RUN_ID"
mkdir -p "$LOG_DIR"

STDOUT_LOG="$LOG_DIR/run_stdout.log"
STDERR_LOG="$LOG_DIR/run_stderr.log"
MONITOR_LOG="$LOG_DIR/system_monitor.log"
META_LOG="$LOG_DIR/meta.log"

echo "RUN_ID=$RUN_ID" | tee -a "$META_LOG"
echo "LOG_DIR=$LOG_DIR" | tee -a "$META_LOG"
echo "START_TIME=$(date '+%F %T')" | tee -a "$META_LOG"

cd "$PROJECT_DIR"

"$VENV_PY" "$MAIN_PY" >"$STDOUT_LOG" 2>"$STDERR_LOG" &
APP_PID=$!

echo "APP_PID=$APP_PID" | tee -a "$META_LOG"

cleanup() {
  echo "STOP_TIME=$(date '+%F %T')" | tee -a "$META_LOG"
  if ps -p "$APP_PID" >/dev/null 2>&1; then
    kill -INT "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

while ps -p "$APP_PID" >/dev/null 2>&1; do
  TS=$(date +"%F %T")

  PS_LINE=$(ps -p "$APP_PID" -o pid=,etime=,%cpu=,rss=,vsz=,state= | awk '{$1=$1; print}')

  VM_PAGE_SIZE=$(vm_stat | head -1 | awk -F'page size of ' '{print $2}' | awk '{print $1}')
  PAGES_FREE=$(vm_stat | awk '/Pages free/ {gsub("\\.","",$3); print $3}')
  PAGES_ACTIVE=$(vm_stat | awk '/Pages active/ {gsub("\\.","",$3); print $3}')
  PAGES_INACTIVE=$(vm_stat | awk '/Pages inactive/ {gsub("\\.","",$3); print $3}')
  PAGES_SPECULATIVE=$(vm_stat | awk '/Pages speculative/ {gsub("\\.","",$3); print $3}')
  PAGES_WIRED=$(vm_stat | awk '/Pages wired down/ {gsub("\\.","",$4); print $4}')
  PAGES_COMPRESSED=$(vm_stat | awk '/Pages occupied by compressor/ {gsub("\\.","",$5); print $5}')

  FREE_MB=$((PAGES_FREE * VM_PAGE_SIZE / 1024 / 1024))
  ACTIVE_MB=$((PAGES_ACTIVE * VM_PAGE_SIZE / 1024 / 1024))
  INACTIVE_MB=$((PAGES_INACTIVE * VM_PAGE_SIZE / 1024 / 1024))
  SPEC_MB=$((PAGES_SPECULATIVE * VM_PAGE_SIZE / 1024 / 1024))
  WIRED_MB=$((PAGES_WIRED * VM_PAGE_SIZE / 1024 / 1024))
  COMP_MB=$((PAGES_COMPRESSED * VM_PAGE_SIZE / 1024 / 1024))

  MEM_PRESSURE=$(memory_pressure 2>/dev/null | awk -F': ' '
    /System-wide memory free percentage/ {free=$2}
    /System-wide memory pressure/ {pressure=$2}
    END {printf "mem_free_pct=%s mem_pressure=%s", free, pressure}
  ')

  echo "$TS | $PS_LINE | free_mb=$FREE_MB active_mb=$ACTIVE_MB inactive_mb=$INACTIVE_MB speculative_mb=$SPEC_MB wired_mb=$WIRED_MB compressed_mb=$COMP_MB | $MEM_PRESSURE" >> "$MONITOR_LOG"

  sleep 5
done

wait "$APP_PID"
