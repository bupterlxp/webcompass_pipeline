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
    REPOS_DIR, STEP1_LOG, STEP4_OUTPUT, MODEL,
    MAX_WORKERS_SCREENSHOT, MAX_RETRIES, BACKOFF_BASE,
)
from utils import (
    load_jsonl, load_done_ids, append_jsonl_threadsafe,
    ensure_dir, call_api, parse_json_output,
)
from webhandler import save_screenshots

write_lock = threading.Lock()

VISUAL_JUDGE_PROMPT = '''You are a professional UI/UX design critic. You are given screenshots of a web application. Evaluate ONLY the visual design quality — do NOT evaluate interactivity, animations, hover states, or any dynamic behavior (those are tested separately via code review).

## Screenshots
The attached images are full-page screenshots of the web application.

## Evaluation Criteria
Score each of the following 10 dimensions from 0 to 10:

1. **Layout & Spacing** — Is the layout well-structured? Are elements properly aligned? Is whitespace used effectively with consistent spacing/margins?
2. **Color Palette & Harmony** — Are colors visually harmonious? Is there a coherent color scheme? Is contrast sufficient for readability?
3. **Typography** — Are fonts readable and well-chosen? Is there a clear hierarchy (headings vs body)? Are font sizes, weights, and line heights appropriate?
4. **Visual Hierarchy** — Can the user immediately identify the most important elements? Is the information flow logical and scannable?
5. **Component Design** — Are buttons, cards, inputs, and other UI components well-designed with proper borders, shadows, and rounded corners?
6. **Responsiveness Appearance** — Does the layout appear well-proportioned? Are elements not overflowing or awkwardly sized?
7. **Imagery & Icons** — Are icons/images/SVGs crisp and well-integrated? Do they enhance the design rather than clutter it?
8. **Overall Polish** — Does it look like a finished product? Are there any rough edges, misalignments, or unfinished areas?
9. **Creativity & Aesthetics** — Is the design visually appealing and creative? Does it go beyond a generic template look?
10. **Professional Quality** — Would this pass as a professionally designed web page? Could it be shown to a client or end user?

## Instructions
You must output ONLY a JSON array (inside a ```json code block):
```json
[
  {{"task": "Layout & Spacing", "score": <0-10>, "max_score": 10, "reason": "brief explanation"}},
  {{"task": "Color Palette & Harmony", "score": <0-10>, "max_score": 10, "reason": "brief explanation"}},
  ...all 10 items...
]
```
'''


def judge_one_visual(item_id, repo_path, model, max_retries, round_num=1):
    zero_scores = [{'task': t, 'score': 0, 'max_score': 10, 'reason': 'Screenshot failed'}
                   for t in ['Layout & Spacing', 'Color Palette & Harmony', 'Typography',
                             'Visual Hierarchy', 'Component Design', 'Responsiveness Appearance',
                             'Imagery & Icons', 'Overall Polish', 'Creativity & Aesthetics',
                             'Professional Quality']]

    try:
        screenshot_fns = save_screenshots(repo_path)
    except Exception as e:
        return {'id': item_id, 'round': round_num, 'scores': zero_scores, 'error': f'screenshot_failed: {e}'}

    if not screenshot_fns:
        return {'id': item_id, 'round': round_num, 'scores': zero_scores, 'error': 'no_screenshots'}

    image_paths = []
    for fn in screenshot_fns:
        full_path = os.path.join(repo_path, fn)
        if os.path.exists(full_path):
            image_paths.append(full_path)

    if not image_paths:
        return {'id': item_id, 'round': round_num, 'scores': zero_scores, 'error': 'screenshots_missing'}

    prompt = VISUAL_JUDGE_PROMPT

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

    done_keys = set()
    if os.path.exists(args.output):
        for line in open(args.output, 'r', encoding='utf-8'):
            try:
                obj = json.loads(line.strip())
                done_keys.add((obj['id'], obj.get('round', 1)))
            except (json.JSONDecodeError, KeyError):
                continue

    pending = [e for e in repo_entries
               if (e['id'], e['round']) not in done_keys]

    print(f"[Step4] repos={len(repo_entries)}, 待处理={len(pending)}")

    if not pending:
        return 0

    counter = {'ok': 0, 'error': 0}

    with tqdm(total=len(pending), desc="Step4 ScreenshotJudge") as pbar:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(
                    judge_one_visual, e['id'], e['repo_path'],
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
