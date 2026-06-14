#!/bin/zsh
# Round 5b: tightened regex recovery (recover_micro_v2) on val2. Pause: touch /tmp/gepa_pause
set -x
cd /Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt \
  --recover regex --recover-prompt prompts/recover_micro_v2.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/r5_arm3b_regex_v2_val2.json
echo "ALL DONE"
