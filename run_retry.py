#!/usr/bin/env python3
"""
Multi-round retry orchestrator with Best-of-N selection.

Usage:
    python3 run_retry.py --threshold 70 --max-rounds 5

Flow per round:
  1. Run step5 to identify items below threshold
  2. Write failed ids to temp file
  3. Re-run step1 with --round N --retry-ids-file
  4. Re-run step2 (checklist, if needed)
  5. Re-run step3/step4 for new attempts
  6. Re-run step5 (picks best across all rounds)
  7. Repeat until all pass or max rounds reached
"""

import os
import sys
import json
import argparse
import subprocess
import time

from config import (
    INPUT_JSONL, STEP1_LOG, STEP1_RESPONSES, STEP2_OUTPUT,
    STEP3_OUTPUT, STEP4_OUTPUT, STEP5_OUTPUT,
    MODEL, SCORE_THRESHOLD,
)
from utils import load_jsonl


def run_cmd(cmd, desc=""):
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"  {' '.join(cmd)}")
    print(f"{'='*60}")
    ret = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    if ret.returncode != 0:
        print(f"[WARN] {desc} exited with code {ret.returncode}")
    return ret.returncode


def get_failed_ids(threshold, strategy, input_jsonl, step2, step3, step4, output):
    cmd = [
        sys.executable, 'step5_filter.py',
        '--input', input_jsonl,
        '--step2', step2,
        '--step3', step3,
        '--step4', step4,
        '--output', output,
        '--threshold', str(threshold),
        '--strategy', strategy,
    ]
    run_cmd(cmd, f"Step5: filter (threshold={threshold})")

    scored_ids = set()
    step3_data = load_jsonl(step3)
    step4_data = load_jsonl(step4)
    for item in step3_data:
        if item.get('scores'):
            scored_ids.add(item['id'])
    for item in step4_data:
        if item.get('scores'):
            scored_ids.add(item['id'])

    passed_ids = set()
    if os.path.exists(output):
        for line in open(output, 'r', encoding='utf-8'):
            try:
                obj = json.loads(line.strip())
                passed_ids.add(obj['id'])
            except (json.JSONDecodeError, KeyError):
                continue

    failed = [id_ for id_ in scored_ids if id_ not in passed_ids]
    return failed


def main():
    parser = argparse.ArgumentParser(description='Multi-round retry orchestrator')
    parser.add_argument('--threshold', type=float, default=SCORE_THRESHOLD)
    parser.add_argument('--max-rounds', type=int, default=5)
    parser.add_argument('--strategy', choices=['average', 'code-only', 'visual-only'], default='average')
    parser.add_argument('--gen-model', default=MODEL, help='Model for generation (step1)')
    parser.add_argument('--eval-model', default='Gemini-3.1-Pro', help='Model for evaluation (step2/3/4)')
    parser.add_argument('--gen-workers', type=int, default=4)
    parser.add_argument('--eval-workers', type=int, default=8)
    parser.add_argument('--screenshot-workers', type=int, default=2)
    parser.add_argument('--skip-first-round', action='store_true',
                        help='Skip round 1 (assume already done)')
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    if not args.skip_first_round:
        run_cmd([sys.executable, 'step1_inference.py',
                 '--model', args.gen_model,
                 '--max-workers', str(args.gen_workers),
                 '--round', '1'],
                "Round 1: Step1 Inference")

        run_cmd([sys.executable, 'step2_checklist.py',
                 '--model', args.eval_model,
                 '--max-workers', str(args.eval_workers)],
                "Round 1: Step2 Checklist")

        run_cmd([sys.executable, 'step3_code_judge.py',
                 '--model', args.eval_model,
                 '--max-workers', str(args.eval_workers)],
                "Round 1: Step3 Code Judge")

        run_cmd([sys.executable, 'step4_screenshot_judge.py',
                 '--model', args.eval_model,
                 '--max-workers', str(args.screenshot_workers)],
                "Round 1: Step4 Screenshot Judge")

    failed_ids = get_failed_ids(
        args.threshold, args.strategy,
        INPUT_JSONL, STEP2_OUTPUT, STEP3_OUTPUT, STEP4_OUTPUT, STEP5_OUTPUT
    )
    print(f"\n[Retry] Round 1 complete: {len(failed_ids)} items below threshold {args.threshold}")

    for round_num in range(2, args.max_rounds + 1):
        if not failed_ids:
            print(f"[Retry] All items passed! No more retries needed.")
            break

        print(f"\n{'#'*60}")
        print(f"  RETRY ROUND {round_num} — {len(failed_ids)} items to regenerate")
        print(f"{'#'*60}")

        ids_file = os.path.join(base_dir, 'output', f'retry_ids_r{round_num}.txt')
        with open(ids_file, 'w') as f:
            for id_ in sorted(failed_ids):
                f.write(id_ + '\n')

        run_cmd([sys.executable, 'step1_inference.py',
                 '--model', args.gen_model,
                 '--max-workers', str(args.gen_workers),
                 '--round', str(round_num),
                 '--retry-ids-file', ids_file],
                f"Round {round_num}: Step1 Inference (regenerate {len(failed_ids)} items)")

        run_cmd([sys.executable, 'step3_code_judge.py',
                 '--model', args.eval_model,
                 '--max-workers', str(args.eval_workers)],
                f"Round {round_num}: Step3 Code Judge")

        run_cmd([sys.executable, 'step4_screenshot_judge.py',
                 '--model', args.eval_model,
                 '--max-workers', str(args.screenshot_workers)],
                f"Round {round_num}: Step4 Screenshot Judge")

        failed_ids = get_failed_ids(
            args.threshold, args.strategy,
            INPUT_JSONL, STEP2_OUTPUT, STEP3_OUTPUT, STEP4_OUTPUT, STEP5_OUTPUT
        )
        print(f"\n[Retry] Round {round_num} complete: {len(failed_ids)} items still below threshold")

    if failed_ids:
        print(f"\n[Retry] Finished {args.max_rounds} rounds. {len(failed_ids)} items still below threshold.")
        ids_file = os.path.join(base_dir, 'output', 'final_failed_ids.txt')
        with open(ids_file, 'w') as f:
            for id_ in sorted(failed_ids):
                f.write(id_ + '\n')
        print(f"[Retry] Failed ids written to {ids_file}")
    else:
        print(f"\n[Retry] All items passed threshold {args.threshold}!")

    if os.path.exists(STEP5_OUTPUT):
        passed = sum(1 for _ in open(STEP5_OUTPUT))
        print(f"[Retry] Final output: {passed} items in {STEP5_OUTPUT}")


if __name__ == '__main__':
    main()
