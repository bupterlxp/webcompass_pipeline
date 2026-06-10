#!/usr/bin/env python3
"""
Step 5: 合并 code_scores 和 visual_scores，计算总分并筛选

输入: step3_code_scores.jsonl + step4_visual_scores.jsonl
输出: step5_filtered.jsonl (通过阈值的高质量数据)
"""

import os
import sys
import json
import time
import argparse
from collections import defaultdict

from config import (
    INPUT_JSONL, STEP2_OUTPUT, STEP3_OUTPUT, STEP3B_OUTPUT, STEP4_OUTPUT, STEP5_OUTPUT,
    SCORE_THRESHOLD,
)
from utils import load_jsonl, ensure_dir


def sum_scores(scores_list):
    if not scores_list:
        return 0
    total = 0
    for item in scores_list:
        score = item.get('score', 0)
        if isinstance(score, (int, float)):
            total += score
    return total


def run_once(args):
    input_data = load_jsonl(args.input)
    input_map = {item['id']: item for item in input_data}

    step2_data = load_jsonl(args.step2)
    checklist_map = {item['id']: item.get('checklist') for item in step2_data}

    step3_data = load_jsonl(args.step3)
    step3b_data = load_jsonl(args.step3b)
    step4_data = load_jsonl(args.step4)

    code_by_id_round = {}
    for item in step3_data:
        if item.get('scores'):
            key = (item['id'], item.get('round', 1))
            code_by_id_round[key] = item['scores']

    interaction_by_id_round = {}
    for item in step3b_data:
        if item.get('scores'):
            key = (item['id'], item.get('round', 1))
            interaction_by_id_round[key] = item['scores']

    visual_by_id_round = {}
    for item in step4_data:
        if item.get('scores'):
            key = (item['id'], item.get('round', 1))
            visual_by_id_round[key] = item['scores']

    if args.strategy == 'code-only':
        scoreable_keys = set(code_by_id_round.keys())
    elif args.strategy == 'visual-only':
        scoreable_keys = set(visual_by_id_round.keys())
    else:
        scoreable_keys = set(code_by_id_round.keys()) & set(visual_by_id_round.keys())

    code_weight = args.code_weight
    interaction_weight = args.interaction_weight
    visual_weight = 1.0 - code_weight - interaction_weight

    attempts_by_id = defaultdict(list)
    for (id_, round_num) in scoreable_keys:
        code_total = sum_scores(code_by_id_round.get((id_, round_num)))
        interaction_total = sum_scores(interaction_by_id_round.get((id_, round_num)))
        visual_total = sum_scores(visual_by_id_round.get((id_, round_num)))

        if args.strategy == 'average':
            combined = (code_total + visual_total) / 2
            if interaction_by_id_round.get((id_, round_num)):
                combined = (code_total + interaction_total + visual_total) / 3
        elif args.strategy == 'weighted':
            combined = code_total * code_weight + visual_total * visual_weight
            if interaction_by_id_round.get((id_, round_num)):
                combined = (code_total * code_weight
                            + interaction_total * interaction_weight
                            + visual_total * visual_weight)
        elif args.strategy == 'code-only':
            combined = code_total
        else:
            combined = visual_total

        attempts_by_id[id_].append({
            'round': round_num,
            'code_total': code_total,
            'interaction_total': interaction_total,
            'visual_total': visual_total,
            'combined_score': combined,
            'code_scores': code_by_id_round.get((id_, round_num)),
            'interaction_scores': interaction_by_id_round.get((id_, round_num)),
            'visual_scores': visual_by_id_round.get((id_, round_num)),
        })

    passed = 0
    failed = 0
    failed_ids = []
    total_code = 0
    total_visual = 0

    with open(args.output, 'w', encoding='utf-8') as fout:
        for id_ in sorted(attempts_by_id.keys()):
            best = max(attempts_by_id[id_], key=lambda x: x['combined_score'])
            total_code += best['code_total']
            total_visual += best['visual_total']

            if best['combined_score'] >= args.threshold:
                record = {
                    'id': id_,
                    'instruction': input_map.get(id_, {}).get('instruction', ''),
                    'checklist': checklist_map.get(id_),
                    'best_round': best['round'],
                    'num_attempts': len(attempts_by_id[id_]),
                    'code_total': best['code_total'],
                    'interaction_total': best['interaction_total'],
                    'visual_total': best['visual_total'],
                    'combined_score': best['combined_score'],
                    'code_scores': best['code_scores'],
                    'interaction_scores': best['interaction_scores'],
                    'visual_scores': best['visual_scores'],
                }
                fout.write(json.dumps(record, ensure_ascii=False) + '\n')
                passed += 1
            else:
                failed += 1
                failed_ids.append(id_)

    n = len(attempts_by_id) or 1
    print(f"[Step5] 总={len(attempts_by_id)}, 通过={passed}, 淘汰={failed}, "
          f"通过率={passed / n * 100:.1f}%, 平均code={total_code / n:.1f}, 平均visual={total_visual / n:.1f}")
    return len(attempts_by_id), failed_ids


def main():
    parser = argparse.ArgumentParser(description='Step 5: Filter')
    parser.add_argument('--input', default=INPUT_JSONL)
    parser.add_argument('--step2', default=STEP2_OUTPUT)
    parser.add_argument('--step3', default=STEP3_OUTPUT)
    parser.add_argument('--step3b', default=STEP3B_OUTPUT)
    parser.add_argument('--step4', default=STEP4_OUTPUT)
    parser.add_argument('--output', default=STEP5_OUTPUT)
    parser.add_argument('--threshold', type=float, default=SCORE_THRESHOLD)
    parser.add_argument('--strategy', choices=['average', 'code-only', 'visual-only', 'weighted'], default='average')
    parser.add_argument('--code-weight', type=float, default=0.4,
                        help='Code judge weight for "weighted" strategy')
    parser.add_argument('--interaction-weight', type=float, default=0.3,
                        help='Interaction test weight for "weighted" strategy')
    # visual_weight = 1.0 - code_weight - interaction_weight
    parser.add_argument('--watch', type=int, default=0, metavar='SECONDS',
                        help='轮询模式：每隔 N 秒重新汇总')
    parser.add_argument('--idle-exit', type=int, default=30, metavar='ROUNDS',
                        help='连续多少轮结果不变后自动退出 (默认30)')
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.output))

    if args.watch > 0:
        last_count = -1
        idle_rounds = 0
        while idle_rounds < args.idle_exit:
            count, _ = run_once(args)
            if count == last_count:
                idle_rounds += 1
                print(f"[Step5] 结果无变化 ({idle_rounds}/{args.idle_exit})，{args.watch}s 后重试...")
            else:
                idle_rounds = 0
            last_count = count
            time.sleep(args.watch)
        print("[Step5] 长时间无变化，退出 watch 模式")
    else:
        run_once(args)


def get_failed_ids(args):
    _, failed_ids = run_once(args)
    return failed_ids


if __name__ == '__main__':
    main()
