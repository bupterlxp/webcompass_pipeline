#!/usr/bin/env python3
"""
Step 1: Inference - 根据 instruction 生成网页代码仓库

输入: all_merged_instructions.jsonl
输出: repos/{id}/ 目录 + step1_inference_log.jsonl
"""

import os
import sys
import time
import re
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import (
    INPUT_JSONL, REPOS_DIR, STEP1_LOG, STEP1_RESPONSES, MODEL,
    MAX_WORKERS_INFERENCE, MAX_RETRIES, BACKOFF_BASE,
)
from utils import (
    load_jsonl, load_done_ids, append_jsonl_threadsafe,
    ensure_dir, call_api,
)
from prompts import Generate_Repo_Template

write_lock = threading.Lock()
response_lock = threading.Lock()


def parse_markdown_to_files(text, repo_path):
    text = text.strip("\n")
    pattern = (
        r"^#\s+([^\n]+)\n"
        r"(?:\s*\n)*"
        r"```([^\n`]*)\n"
        r"(.*?)\n```\s*(?:\n|$)"
    )
    matches = re.findall(pattern, text, flags=re.DOTALL | re.MULTILINE)
    count = 0
    for file_path, _lang, content in matches:
        file_path = file_path.strip()
        if not file_path:
            continue
        abs_path = os.path.join(repo_path, file_path)
        os.makedirs(os.path.dirname(abs_path) or repo_path, exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        count += 1
    return count


def is_done(repo_path):
    return os.path.exists(os.path.join(repo_path, '.done'))


def mark_done(repo_path):
    done_path = os.path.join(repo_path, '.done')
    tmp = done_path + '.tmp'
    with open(tmp, 'w') as f:
        f.write('done')
    os.replace(tmp, done_path)


def process_one(item, model, repos_dir, max_retries, round_num=1):
    item_id = item['id']
    instruction = item['instruction']
    suffix = f"_r{round_num}" if round_num > 1 else ""
    repo_path = os.path.join(repos_dir, f"{item_id}{suffix}")

    if is_done(repo_path):
        return {'id': item_id, 'round': round_num, 'repo_path': repo_path, 'status': 'skipped_done', 'file_count': -1, 'response': None}

    ensure_dir(repo_path)

    prompt = Generate_Repo_Template.replace('[DOCUMENT]', instruction)

    last_count = 0
    for attempt in range(max_retries):
        try:
            result = call_api(prompt, model, stream_print=False)
            if not result:
                continue
            count = parse_markdown_to_files(result, repo_path)
            if count > 0:
                mark_done(repo_path)
                return {'id': item_id, 'round': round_num, 'repo_path': repo_path, 'status': 'ok', 'file_count': count, 'response': result}
            last_count = count
        except Exception as e:
            last_count = 0
            if attempt < max_retries - 1:
                time.sleep(BACKOFF_BASE * (2 ** attempt))

    return {'id': item_id, 'round': round_num, 'repo_path': repo_path, 'status': 'error', 'file_count': last_count, 'response': None}


def main():
    parser = argparse.ArgumentParser(description='Step 1: Inference')
    parser.add_argument('--input', default=INPUT_JSONL)
    parser.add_argument('--repos-dir', default=REPOS_DIR)
    parser.add_argument('--log', default=STEP1_LOG)
    parser.add_argument('--responses', default=STEP1_RESPONSES)
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--max-workers', type=int, default=MAX_WORKERS_INFERENCE)
    parser.add_argument('--max-retries', type=int, default=MAX_RETRIES)
    parser.add_argument('--round', type=int, default=1, help='当前重试轮次 (1=首次)')
    parser.add_argument('--retry-ids-file', default=None, help='需要重试的 id 列表文件（每行一个 id）')
    args = parser.parse_args()

    ensure_dir(args.repos_dir)
    ensure_dir(os.path.dirname(args.log))
    ensure_dir(os.path.dirname(args.responses))

    print(f"读取: {args.input}")
    items = load_jsonl(args.input)
    print(f"共 {len(items)} 条")

    if args.retry_ids_file:
        with open(args.retry_ids_file, 'r') as f:
            retry_ids = set(line.strip() for line in f if line.strip())
        items = [item for item in items if item['id'] in retry_ids]
        print(f"重试模式 (round {args.round}): 需要重试 {len(items)} 条")

    done_ids = load_done_ids(args.log)
    pending = [item for item in items if item['id'] not in done_ids]
    print(f"已完成 {len(done_ids)} 条，待处理 {len(pending)} 条")

    if not pending:
        print("没有需要处理的数据")
        return

    counter = {'ok': 0, 'error': 0, 'skipped': 0}

    with tqdm(total=len(pending), desc="Step1 Inference") as pbar:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(process_one, item, args.model, args.repos_dir, args.max_retries, args.round): item
                for item in pending
            }
            for future in as_completed(futures):
                result = future.result()
                response = result.pop('response', None)
                append_jsonl_threadsafe(args.log, result, write_lock)
                if response:
                    append_jsonl_threadsafe(args.responses, {'id': result['id'], 'response': response}, response_lock)

                status = result['status']
                if status == 'ok':
                    counter['ok'] += 1
                elif status == 'skipped_done':
                    counter['skipped'] += 1
                else:
                    counter['error'] += 1

                pbar.update(1)
                pbar.set_postfix(**counter)

    print(f"\n完成! 成功: {counter['ok']}, 失败: {counter['error']}, 跳过: {counter['skipped']}")


if __name__ == '__main__':
    main()
