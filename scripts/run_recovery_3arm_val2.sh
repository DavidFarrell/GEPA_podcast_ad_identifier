#!/bin/zsh
# Round 5: 3-arm recovery experiment on val2. Pause: touch /tmp/gepa_pause
set -x
cd /Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier
# Arm 1: champion baseline (checklist alone)
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/r5_arm1_champion_val2.json
# Arm 2: champion + model-only terminal-anchor recovery
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt \
  --recover model --recover-prompt prompts/recover_scan_v1.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/r5_arm2_model_val2.json
# Arm 3: champion + regex pre-scan + model back-expansion
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt \
  --recover regex --recover-prompt prompts/recover_micro_v1.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/r5_arm3_regex_val2.json
echo "ALL DONE"
