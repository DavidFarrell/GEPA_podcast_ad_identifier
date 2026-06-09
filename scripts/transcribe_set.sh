#!/usr/bin/env bash
# Download + transcribe every episode in a manifest, then delete the audio.
# Resumable: skips episodes whose transcript JSON already exists.
# Usage: scripts/transcribe_set.sh manifests/pilot.json
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="${1:-$REPO/manifests/pilot.json}"
TOOL_DIR="$HOME/git/ai-sandbox/projects/fast_mac_transcribe_diarise_local_models_only"
AUDIO_DIR="$REPO/data/audio"
TX_DIR="$REPO/data/transcripts"
LOG="$REPO/data/transcribe.log"
mkdir -p "$AUDIO_DIR" "$TX_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

count=$(jq '.episodes | length' "$MANIFEST")
log "=== transcribe_set: $count episodes from $(basename "$MANIFEST") ==="

for i in $(seq 0 $((count-1))); do
  id=$(jq -r ".episodes[$i].id" "$MANIFEST")
  url=$(jq -r ".episodes[$i].url" "$MANIFEST")
  show=$(jq -r ".episodes[$i].show" "$MANIFEST")
  json="$TX_DIR/$id.json"

  if [ -s "$json" ]; then log "SKIP  $id (transcript exists)"; continue; fi
  log "FETCH $id  ($show)"

  audio="$AUDIO_DIR/$id.mp3"
  if ! curl -fsSL --max-time 600 -A "Mozilla/5.0" -o "$audio" "$url"; then
    log "ERROR download failed: $id"; rm -f "$audio"; continue
  fi
  sz=$(du -h "$audio" | cut -f1); log "  downloaded $sz, transcribing..."

  if (cd "$TOOL_DIR" && uv run diarise-transcribe \
        --in "$audio" --out "$TX_DIR/$id.txt" --out-json "$json" 2>>"$LOG"); then
    log "  OK transcript -> $id.json"
  else
    log "ERROR transcription failed: $id"
  fi
  rm -f "$audio"   # throwaway: do not retain copyrighted audio
done

log "=== done. transcripts in $TX_DIR ==="
