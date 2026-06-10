#!/usr/bin/env python3
"""
把 step5 通过筛选的数据整理成 SFT 训练格式。

input  = Generate_Repo_Template 包裹 instruction(设计文档),与生成时完全一致
output = repo 内代码文件,沿用 "# path + ```lang 代码块" 契约

输出: output/sft_messages.jsonl  (messages 对话格式)
"""

import os
import sys
import json
import argparse

from config import STEP5_OUTPUT, REPOS_DIR, CODE_EXTENSIONS
from prompts import Generate_Repo_Template

# 仓库内忽略的文件
IGNORE_FILES = {'.done'}
IGNORE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico'}

LANG_MAP = {
    '.html': 'html', '.css': 'css', '.js': 'javascript', '.jsx': 'jsx',
    '.ts': 'typescript', '.tsx': 'tsx', '.vue': 'vue', '.svelte': 'svelte',
    '.json': 'json', '.md': 'markdown', '.txt': 'txt',
}

# 文件顺序优先级(让 index.html 排第一,符合生成习惯)
ORDER = {'index.html': 0, 'styles.css': 1, 'style.css': 1, 'main.js': 2, 'script.js': 2}


def collect_repo_files(repo_path):
    """收集 repo 内的代码文件,返回 [(relpath, content), ...] 已排序"""
    files = []
    for root, dirs, fnames in os.walk(repo_path):
        for fn in fnames:
            if fn in IGNORE_FILES:
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in IGNORE_EXTS:
                continue
            if ext not in CODE_EXTENSIONS:
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, repo_path)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            files.append((rel, content))

    files.sort(key=lambda x: (ORDER.get(x[0], 99), x[0]))
    return files


def build_output_markdown(files):
    """把文件列表拼成 '# path\n```lang\n...\n```' 契约格式"""
    blocks = []
    for rel, content in files:
        ext = os.path.splitext(rel)[1].lower()
        lang = LANG_MAP.get(ext, '')
        blocks.append(f"# {rel}\n```{lang}\n{content}\n```")
    return "\n\n".join(blocks)


def main():
    parser = argparse.ArgumentParser(description='Build SFT dataset from step5 filtered data')
    parser.add_argument('--step5', default=STEP5_OUTPUT)
    parser.add_argument('--repos-dir', default=REPOS_DIR)
    parser.add_argument('--out-messages', default=os.path.join(os.path.dirname(STEP5_OUTPUT), 'sft_messages.jsonl'))
    parser.add_argument('--out-alpaca', default=None, help='可选: 同时输出 alpaca 格式')
    args = parser.parse_args()

    n_ok, n_no_repo, n_empty = 0, 0, 0
    f_msg = open(args.out_messages, 'w', encoding='utf-8')
    f_alpaca = open(args.out_alpaca, 'w', encoding='utf-8') if args.out_alpaca else None

    with open(args.step5, 'r', encoding='utf-8') as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            item_id = obj['id']
            instruction = obj.get('instruction', '')
            best_round = obj.get('best_round', 1)

            suffix = f'_r{best_round}' if best_round > 1 else ''
            repo_path = os.path.join(args.repos_dir, f'{item_id}{suffix}')

            if not os.path.isdir(repo_path):
                n_no_repo += 1
                continue

            files = collect_repo_files(repo_path)
            if not files:
                n_empty += 1
                continue

            user_prompt = Generate_Repo_Template.replace('[DOCUMENT]', instruction)
            assistant_output = build_output_markdown(files)

            rec = {
                'id': item_id,
                'messages': [
                    {'role': 'user', 'content': user_prompt},
                    {'role': 'assistant', 'content': assistant_output},
                ],
            }
            f_msg.write(json.dumps(rec, ensure_ascii=False) + '\n')

            if f_alpaca:
                f_alpaca.write(json.dumps({
                    'id': item_id,
                    'instruction': user_prompt,
                    'input': '',
                    'output': assistant_output,
                }, ensure_ascii=False) + '\n')

            n_ok += 1

    f_msg.close()
    if f_alpaca:
        f_alpaca.close()

    print(f"完成! SFT样本={n_ok}, 仓库缺失={n_no_repo}, 空仓库={n_empty}")
    print(f"输出: {args.out_messages}")
    if args.out_alpaca:
        print(f"输出: {args.out_alpaca}")


if __name__ == '__main__':
    main()
