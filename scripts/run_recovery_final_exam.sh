#!/bin/zsh
# Round 5 FINAL EXAM: champion + recovery v2 on held-out fresh5 + test8. Pause: touch /tmp/gepa_pause
set -x
cd /Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt \
  --recover regex --recover-prompt prompts/recover_micro_v2.txt \
  --split test_fresh5 --metric weighted --workers 3 \
  --out out/r5_final_recovery_fresh5.json
taskpolicy -b uv run python src/run_eval.py \
  --prompt prompts/seed_checklist_v1.txt \
  --recover regex --recover-prompt prompts/recover_micro_v2.txt \
  --split test --metric weighted --workers 3 \
  --out out/r5_final_recovery_test8.json
echo "ALL DONE"
