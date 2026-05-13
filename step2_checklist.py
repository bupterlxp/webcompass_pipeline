#!/usr/bin/env python3
"""
Step 2: 为每条 instruction 生成评估 checklist

输入: all_merged_instructions.jsonl
输出: step2_checklists.jsonl (每行: {id, checklist: [...]})
"""

import os
import sys
import time
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import (
    INPUT_JSONL, STEP2_OUTPUT, MODEL,
    MAX_WORKERS_CHECKLIST, MAX_RETRIES, BACKOFF_BASE,
)
from utils import (
    load_jsonl, load_done_ids, append_jsonl_threadsafe,
    ensure_dir, call_api, parse_json_output,
)
from prompts import new_checklist

write_lock = threading.Lock()


def validate_checklist(checklist):
    if not isinstance(checklist, list) or len(checklist) == 0:
        return False
    required_keys = {'task', 'category', 'max_score'}
    for item in checklist:
        if not isinstance(item, dict):
            return False
        if not required_keys.issubset(item.keys()):
            return False
        if not isinstance(item.get('max_score'), (int, float)):
            return False
    return True


def generate_one_checklist(item, model, max_retries):
    item_id = item['id']
    instruction = item['instruction']

    prompt = new_checklist.replace('[QUERY]', instruction)

    for attempt in range(max_retries):
        try:
            result = call_api(prompt, model, stream_print=False)
            if not result:
                continue
            checklist = parse_json_output(result)
            if validate_checklist(checklist):
                return {'id': item_id, 'checklist': checklist}
        except Exception:
            pass
        if attempt < max_retries - 1:
            time.sleep(BACKOFF_BASE * (2 ** attempt))

    return {'id': item_id, 'checklist': None, 'error': 'failed_after_retries'}


def main():
    parser = argparse.ArgumentParser(description='Step 2: Generate Checklists')
    parser.add_argument('--input', default=INPUT_JSONL)
    parser.add_argument('--output', default=STEP2_OUTPUT)
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--max-workers', type=int, default=MAX_WORKERS_CHECKLIST)
    parser.add_argument('--max-retries', type=int, default=MAX_RETRIES)
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.output))

    print(f"读取: {args.input}")
    items = load_jsonl(args.input)
    print(f"共 {len(items)} 条")

    done_ids = load_done_ids(args.output)
    pending = [item for item in items if item['id'] not in done_ids]
    print(f"已完成 {len(done_ids)} 条，待处理 {len(pending)} 条")

    if not pending:
        print("没有需要处理的数据")
        return

    counter = {'ok': 0, 'error': 0}

    with tqdm(total=len(pending), desc="Step2 Checklist") as pbar:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(generate_one_checklist, item, args.model, args.max_retries): item
                for item in pending
            }
            for future in as_completed(futures):
                result = future.result()
                append_jsonl_threadsafe(args.output, result, write_lock)

                if result.get('checklist'):
                    counter['ok'] += 1
                else:
                    counter['error'] += 1

                pbar.update(1)
                pbar.set_postfix(**counter)

    print(f"\n完成! 成功: {counter['ok']}, 失败: {counter['error']}")


if __name__ == '__main__':
    main()
