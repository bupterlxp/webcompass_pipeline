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
import json
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import (
    INPUT_JSONL, REPOS_DIR, STEP1_LOG, STEP1_RESPONSES, MODEL,
    STEP3_OUTPUT, STEP3B_OUTPUT, STEP4_OUTPUT,
    MAX_WORKERS_INFERENCE, MAX_RETRIES, BACKOFF_BASE,
    CODE_EXTENSIONS, MAX_CODE_LENGTH,
)
from utils import (
    load_jsonl, load_done_ids, append_jsonl_threadsafe,
    ensure_dir, call_api, read_repo_code,
)
from prompts import Generate_Repo_Template, SELF_REPAIR_PROMPT

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


def build_repair_context(item_id, prev_round, repos_dir, step3_path, step3b_path, step4_path):
    prev_suffix = f"_r{prev_round}" if prev_round > 1 else ""
    prev_repo = os.path.join(repos_dir, f"{item_id}{prev_suffix}")

    prev_code = read_repo_code(prev_repo, CODE_EXTENSIONS, MAX_CODE_LENGTH)
    if not prev_code.strip():
        return None

    source_labels = {step3_path: "Code", step3b_path: "Interaction", step4_path: "Visual"}
    feedback_lines = []
    for score_path in [step3_path, step3b_path, step4_path]:
        if not score_path or not os.path.exists(score_path):
            continue
        with open(score_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    if obj['id'] == item_id and obj.get('round', 1) == prev_round and obj.get('scores'):
                        source = source_labels.get(score_path, "Unknown")
                        for s in obj['scores']:
                            score = s.get('score', 0)
                            max_score = s.get('max_score', 0)
                            if score < max_score:
                                feedback_lines.append(
                                    f"- [{source}] [{score}/{max_score}] {s.get('task','')}: {s.get('reason','')}"
                                )
                except (json.JSONDecodeError, KeyError):
                    continue

    if not feedback_lines:
        return None

    return {
        'previous_code': prev_code,
        'feedback': '\n'.join(feedback_lines),
    }


def process_one(item, model, repos_dir, max_retries, round_num=1, step3_path=None, step3b_path=None, step4_path=None):
    item_id = item['id']
    instruction = item['instruction']
    suffix = f"_r{round_num}" if round_num > 1 else ""
    repo_path = os.path.join(repos_dir, f"{item_id}{suffix}")

    if is_done(repo_path):
        return {'id': item_id, 'round': round_num, 'repo_path': repo_path, 'status': 'skipped_done', 'file_count': -1, 'response': None}

    ensure_dir(repo_path)

    if round_num > 1 and step3_path and step4_path:
        repair_ctx = build_repair_context(item_id, round_num - 1, repos_dir, step3_path, step3b_path, step4_path)
        if repair_ctx:
            prompt = SELF_REPAIR_PROMPT.format(
                instruction=instruction,
                previous_code=repair_ctx['previous_code'],
                feedback=repair_ctx['feedback'],
            )
        else:
            prompt = Generate_Repo_Template.replace('[DOCUMENT]', instruction)
    else:
        prompt = Generate_Repo_Template.replace('[DOCUMENT]', instruction)

    last_count = 0
    for attempt in range(max_retries):
        try:
            result, thinking, usage = call_api(prompt, model, stream_print=False, return_thinking=True, return_usage=True)
            if not result:
                continue
            count = parse_markdown_to_files(result, repo_path)
            if count > 0:
                mark_done(repo_path)
                return {'id': item_id, 'round': round_num, 'repo_path': repo_path, 'status': 'ok', 'file_count': count, 'response': result, 'thinking': thinking, 'usage': usage}
            last_count = count
        except Exception as e:
            last_count = 0
            if attempt < max_retries - 1:
                time.sleep(BACKOFF_BASE * (2 ** attempt))

    return {'id': item_id, 'round': round_num, 'repo_path': repo_path, 'status': 'error', 'file_count': last_count, 'response': None, 'thinking': None, 'usage': None}


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
    parser.add_argument('--step3-output', default=STEP3_OUTPUT)
    parser.add_argument('--step3b-output', default=STEP3B_OUTPUT)
    parser.add_argument('--step4-output', default=STEP4_OUTPUT)
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

    if args.round > 1:
        print(f"Self-repair 模式: 将读取上轮评分反馈进行定向修复")

    if not pending:
        print("没有需要处理的数据")
        return

    counter = {'ok': 0, 'error': 0, 'skipped': 0}

    with tqdm(total=len(pending), desc="Step1 Inference") as pbar:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(
                    process_one, item, args.model, args.repos_dir, args.max_retries,
                    args.round, args.step3_output, args.step3b_output, args.step4_output,
                ): item
                for item in pending
            }
            for future in as_completed(futures):
                result = future.result()
                response = result.pop('response', None)
                thinking = result.pop('thinking', None)
                usage = result.get('usage')
                append_jsonl_threadsafe(args.log, result, write_lock)
                if response:
                    resp_record = {'id': result['id'], 'response': response}
                    if thinking:
                        resp_record['thinking'] = thinking
                    if usage:
                        resp_record['usage'] = usage
                    append_jsonl_threadsafe(args.responses, resp_record, response_lock)

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
