#!/usr/bin/env python3
"""
Step 4: Screenshot Judge - 启动网页截图，结合 checklist 进行视觉评分

输入: step1 的 repos + step2 的 checklists
输出: step4_visual_scores.jsonl (每行: {id, scores: [{task, score, max_score, reason}]})
"""

import os
import sys
import json
import time
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import (
    REPOS_DIR, STEP1_LOG, STEP2_OUTPUT, STEP4_OUTPUT, MODEL,
    MAX_WORKERS_SCREENSHOT, MAX_RETRIES, BACKOFF_BASE,
)
from utils import (
    load_jsonl, load_done_ids, append_jsonl_threadsafe,
    ensure_dir, call_api, parse_json_output,
)
from webhandler import save_screenshots

write_lock = threading.Lock()

VISUAL_JUDGE_PROMPT = '''You are a strict visual QA expert. You are given a checklist and screenshots of a generated web application. Evaluate each checklist item based on what you can see in the screenshots.

## Checklist
```json
{checklist_json}
```

## Screenshots
The attached images are full-page screenshots of the web application (each sub-page captured separately).

## Instructions
For each checklist item, evaluate whether the screenshots demonstrate that the required functionality, interaction, and visual design have been correctly implemented. Score each item from 0 to its max_score.

You must output ONLY a JSON array (inside a ```json code block), with one object per checklist item:
```json
[
  {{"task": "the task description", "score": <number 0 to max_score>, "max_score": <number>, "reason": "brief explanation based on visual evidence"}}
]
```
'''


def judge_one_visual(item_id, repo_path, checklist, model, max_retries, round_num=1):
    try:
        screenshot_fns = save_screenshots(repo_path)
    except Exception as e:
        return {
            'id': item_id, 'round': round_num,
            'scores': [{'task': c['task'], 'score': 0, 'max_score': c['max_score'], 'reason': f'Screenshot failed: {e}'}
                       for c in checklist],
            'error': f'screenshot_failed: {e}'
        }

    if not screenshot_fns:
        return {
            'id': item_id, 'round': round_num,
            'scores': [{'task': c['task'], 'score': 0, 'max_score': c['max_score'], 'reason': 'No screenshots captured'}
                       for c in checklist],
            'error': 'no_screenshots'
        }

    image_paths = []
    for fn in screenshot_fns:
        full_path = os.path.join(repo_path, fn)
        if os.path.exists(full_path):
            image_paths.append(full_path)

    if not image_paths:
        return {
            'id': item_id, 'round': round_num,
            'scores': [{'task': c['task'], 'score': 0, 'max_score': c['max_score'], 'reason': 'Screenshot files not found'}
                       for c in checklist],
            'error': 'screenshots_missing'
        }

    checklist_json = json.dumps(checklist, ensure_ascii=False, indent=2)
    prompt = VISUAL_JUDGE_PROMPT.replace('{checklist_json}', checklist_json)

    for attempt in range(max_retries):
        try:
            result = call_api(prompt, model, image_path=image_paths, stream_print=False)
            if not result:
                continue
            scores = parse_json_output(result)
            if isinstance(scores, list) and len(scores) > 0:
                return {'id': item_id, 'round': round_num, 'scores': scores}
        except Exception:
            pass
        if attempt < max_retries - 1:
            time.sleep(BACKOFF_BASE * (2 ** attempt))

    return {'id': item_id, 'round': round_num, 'scores': None, 'error': 'failed_after_retries'}


def run_once(args):
    step1_data = load_jsonl(args.step1_log)
    repo_entries = []
    for item in step1_data:
        if item.get('status') == 'ok':
            repo_entries.append({
                'id': item['id'],
                'round': item.get('round', 1),
                'repo_path': item['repo_path'],
            })

    step2_data = load_jsonl(args.step2_output)
    checklist_map = {item['id']: item['checklist'] for item in step2_data if item.get('checklist')}

    done_keys = set()
    if os.path.exists(args.output):
        for line in open(args.output, 'r', encoding='utf-8'):
            try:
                obj = json.loads(line.strip())
                done_keys.add((obj['id'], obj.get('round', 1)))
            except (json.JSONDecodeError, KeyError):
                continue

    pending = [e for e in repo_entries
               if e['id'] in checklist_map and (e['id'], e['round']) not in done_keys]

    print(f"[Step4] repos={len(repo_entries)}, checklists={len(checklist_map)}, 待处理={len(pending)}")

    if not pending:
        return 0

    counter = {'ok': 0, 'error': 0}

    with tqdm(total=len(pending), desc="Step4 ScreenshotJudge") as pbar:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(
                    judge_one_visual, e['id'], e['repo_path'], checklist_map[e['id']],
                    args.model, args.max_retries, e['round']
                ): e
                for e in pending
            }
            for future in as_completed(futures):
                result = future.result()
                append_jsonl_threadsafe(args.output, result, write_lock)

                if result.get('scores'):
                    counter['ok'] += 1
                else:
                    counter['error'] += 1

                pbar.update(1)
                pbar.set_postfix(**counter)

    print(f"[Step4] 本轮完成: 成功={counter['ok']}, 失败={counter['error']}")
    return len(pending)


def main():
    parser = argparse.ArgumentParser(description='Step 4: Screenshot Judge')
    parser.add_argument('--step1-log', default=STEP1_LOG)
    parser.add_argument('--step2-output', default=STEP2_OUTPUT)
    parser.add_argument('--output', default=STEP4_OUTPUT)
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--max-workers', type=int, default=MAX_WORKERS_SCREENSHOT)
    parser.add_argument('--max-retries', type=int, default=MAX_RETRIES)
    parser.add_argument('--watch', type=int, default=0, metavar='SECONDS',
                        help='轮询模式：每隔 N 秒扫描上游新产出')
    parser.add_argument('--idle-exit', type=int, default=30, metavar='ROUNDS',
                        help='连续多少轮无新数据后自动退出 (默认30)')
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.output))

    if args.watch > 0:
        idle_rounds = 0
        while idle_rounds < args.idle_exit:
            processed = run_once(args)
            if processed == 0:
                idle_rounds += 1
                print(f"[Step4] 无新数据 ({idle_rounds}/{args.idle_exit})，{args.watch}s 后重试...")
            else:
                idle_rounds = 0
            time.sleep(args.watch)
        print("[Step4] 长时间无新数据，退出 watch 模式")
    else:
        run_once(args)


if __name__ == '__main__':
    main()
