#!/bin/zsh
# Two-pass detect->verify experiments on val2. Pause: touch /tmp/gepa_pause
set -x
cd /Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_editor_v1.txt --verify-prompt prompts/verify_v1.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/twopass_editor_verify1_val2.json
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt --verify-prompt prompts/verify_v1.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/twopass_checklist_verify1_val2.json
echo "ALL DONE"
