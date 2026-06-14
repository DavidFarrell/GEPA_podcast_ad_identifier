#!/bin/zsh
# FINAL EXAM: checklist+verify v3 on the two held-out sets. Pause: touch /tmp/gepa_pause
set -x
cd /Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt --verify-prompt prompts/verify_v3.txt \
  --split test_fresh5 --metric weighted --workers 3 \
  --out out/final_checklist_verify3_fresh5.json
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt --verify-prompt prompts/verify_v3.txt \
  --split test --metric weighted --workers 3 \
  --out out/final_checklist_verify3_test8.json
echo "ALL DONE"
