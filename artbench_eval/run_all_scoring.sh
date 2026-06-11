#!/bin/bash
set -u
export WQ_API_KEY="xs28uoh0ptvbvfhry5thw8nrp5y2phtxkqui"
PY=/root/miniconda3/envs/llamafactory/bin/python
cd /share/leixinping/sft_train/8b-vl-sft/artbench_eval
for m in base ckpt100 ckpt200 ckpt300 ckpt306; do
  echo "==================== SCORING $m  $(date '+%H:%M:%S') ===================="
  $PY score.py answers/answers_${m}.jsonl scored/scored_${m}.jsonl shots/${m}
  echo "==================== DONE $m  $(date '+%H:%M:%S') ===================="
done
echo "ALL_SCORING_COMPLETE"
