#!/bin/zsh
# Verify v3 experiments on val2: union(checklist,editor)+v3, then editor+v3. Pause: touch /tmp/gepa_pause
set -x
cd /Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt --prompt2 prompts/seed_editor_v1.txt \
  --verify-prompt prompts/verify_v3.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/twopass_union_verify3_val2.json
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_editor_v1.txt --verify-prompt prompts/verify_v3.txt \
  --split val2 --metric weighted --workers 3 \
  --out out/twopass_editor_verify3_val2.json
echo "ALL DONE"
