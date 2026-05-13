"""
Pipeline 共享工具函数
"""

import os
import json
import threading

from call_model import call_api
from parse_json import parse_json_output


def load_jsonl(path):
    items = []
    if not os.path.exists(path):
        return items
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def load_done_ids(path, id_field='id'):
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    if id_field in obj:
                        done.add(obj[id_field])
                except json.JSONDecodeError:
                    continue
    return done


def append_jsonl_threadsafe(path, obj, lock):
    with lock:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def read_repo_code(repo_path, extensions, max_length=150000):
    parts = []
    total_len = 0

    for root, _dirs, files in os.walk(repo_path):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in extensions:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, repo_path)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue

            chunk = f"--- {rel_path} ---\n{content}\n\n"
            if total_len + len(chunk) > max_length:
                parts.append(f"\n[... 代码已截断，总长度超过 {max_length} 字符 ...]\n")
                break
            parts.append(chunk)
            total_len += len(chunk)
        else:
            continue
        break

    return ''.join(parts)
