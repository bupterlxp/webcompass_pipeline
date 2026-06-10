#!/usr/bin/env python3
"""
Step 3b: Interaction Test - LLM 生成 Playwright 测试脚本，实际运行验证交互

输入: step1 repos + step2 checklists + 代码
输出: step3b_interaction_scores.jsonl
"""

import os
import sys
import json
import time
import tempfile
import subprocess
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import (
    REPOS_DIR, STEP1_LOG, STEP2_OUTPUT, MODEL,
    MAX_WORKERS_CODE_JUDGE, MAX_RETRIES, BACKOFF_BASE,
    CODE_EXTENSIONS, MAX_CODE_LENGTH,
)
from utils import (
    load_jsonl, append_jsonl_threadsafe,
    ensure_dir, read_repo_code, call_api, parse_json_output,
)

write_lock = threading.Lock()

STEP3B_OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "output", "step3b_interaction_scores.jsonl"
)

GENERATE_TEST_PROMPT = '''You are an expert test engineer. Given a web page's source code and interactive checklist items, generate test cases.

## Source Code
{code_content}

## Checklist (interactive items to test)
```json
{checklist_json}
```

## Requirements
For each checklist item, write a **browser-side JavaScript test function** that:
- Simulates user interaction (click elements, check visibility, verify text changes, etc.)
- Returns `true` if the test passes, `false` otherwise
- Uses ONLY standard DOM APIs (querySelector, click(), classList, getComputedStyle, etc.)
- Each test is a self-contained function body (no imports needed)

Output ONLY a JSON array inside a ```json code block:
```json
[
  {{
    "task": "checklist task description",
    "max_score": 10,
    "setup": "CSS selector to click before testing (empty string if none)",
    "test_js": "(() => {{ /* test code */ return document.querySelector('#btn') !== null; }})()"
  }}
]
```

Keep each test_js under 5 lines. Focus on verifiable DOM state: element existence, visibility, text content, CSS classes, computed styles.
For interactions like click, the setup field should contain the selector to click (we will click it for you before running test_js).
'''

INTERACTION_CATEGORIES = {'Interactivity', 'Interaction', 'Dynamic Behavior', 'Animation',
                          'User Interaction', 'Functionality', 'Interactive', 'Event Handling'}


def filter_interactive_items(checklist):
    interactive = []
    for item in checklist:
        cat = item.get('category', '')
        task = item.get('task', '').lower()
        is_interactive = (
            cat in INTERACTION_CATEGORIES
            or any(kw in cat.lower() for kw in ['interact', 'dynamic', 'animation', 'event', 'function'])
            or any(kw in task for kw in ['click', 'hover', 'drag', 'tap', 'press', 'toggle',
                                          'button', 'input', 'submit', 'scroll', 'animate',
                                          'transition', 'event', 'trigger', 'select', 'expand',
                                          'collapse', 'modal', 'dropdown', 'slider'])
        )
        if is_interactive:
            interactive.append(item)
    return interactive


def extract_js_code(text):
    import re
    match = re.search(r'```(?:javascript|js)\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'```\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


RUNNER_TEMPLATE_PREFIX = '''const { chromium } = require('playwright');
const path = require('path');
const tests = '''

RUNNER_TEMPLATE_SUFFIX = ''';

(async () => {
  const repoPath = process.argv[2];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(repoPath, 'index.html'), { waitUntil: 'load' });
  await page.waitForTimeout(1000);

  const results = [];
  for (const t of tests) {
    try {
      if (t.setup) {
        try { await page.click(t.setup, { timeout: 3000 }); } catch(e) {}
        await page.waitForTimeout(500);
      }
      const passed = await page.evaluate(t.test_js);
      results.push({ task: t.task, passed: !!passed, max_score: t.max_score, detail: passed ? 'passed' : 'check failed' });
    } catch(e) {
      results.push({ task: t.task, passed: false, max_score: t.max_score, detail: e.message.slice(0, 200) });
    }
  }

  console.log(JSON.stringify(results));
  await browser.close();
})();
'''


def build_runner_script(test_cases):
    tests_json = json.dumps(test_cases, ensure_ascii=False)
    return RUNNER_TEMPLATE_PREFIX + tests_json + RUNNER_TEMPLATE_SUFFIX


def run_test_script(script_code, repo_path, timeout=60):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, dir='/tmp') as f:
        f.write(script_code)
        script_path = f.name

    try:
        env = os.environ.copy()
        env['NODE_PATH'] = os.path.expanduser('~/.local/lib/node_modules')
        result = subprocess.run(
            ['node', script_path, str(repo_path)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(repo_path), env=env,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            # Save debug info
            debug_path = f"/tmp/step3b_debug_{os.path.basename(repo_path)}.log"
            with open(debug_path, 'w') as df:
                df.write(f"=== SCRIPT ===\n{script_code[:2000]}\n\n=== STDERR ===\n{stderr[:2000]}\n\n=== STDOUT ===\n{stdout[:2000]}\n")

        # Try to find JSON array in stdout
        try:
            import re
            json_matches = re.findall(r'\[[\s\S]*?\]', stdout)
            if json_matches:
                for jm in reversed(json_matches):
                    try:
                        parsed = json.loads(jm)
                        if isinstance(parsed, list):
                            return parsed, None
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return None, f"exit={result.returncode}, stderr={stderr[:300]}"
    except subprocess.TimeoutExpired:
        return None, "test_timeout"
    except Exception as e:
        return None, str(e)
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def test_one(item_id, repo_path, checklist, model, max_retries, round_num=1):
    interactive_items = filter_interactive_items(checklist)

    if not interactive_items:
        return {
            'id': item_id, 'round': round_num,
            'scores': [],
            'note': 'no_interactive_items'
        }

    code_content = read_repo_code(repo_path, CODE_EXTENSIONS, MAX_CODE_LENGTH)
    if not code_content.strip():
        return {
            'id': item_id, 'round': round_num,
            'scores': [{'task': c['task'], 'score': 0, 'max_score': c.get('max_score', 10),
                        'reason': 'No code found'} for c in interactive_items],
            'error': 'empty_repo'
        }

    checklist_json = json.dumps(interactive_items, ensure_ascii=False, indent=2)
    prompt = GENERATE_TEST_PROMPT.replace('{code_content}', code_content).replace('{checklist_json}', checklist_json)

    for attempt in range(max_retries):
        try:
            result = call_api(prompt, model, stream_print=False)
            if not result:
                continue

            test_cases = parse_json_output(result)
            if not isinstance(test_cases, list) or not test_cases:
                continue

            script_code = build_runner_script(test_cases)
            test_results, error = run_test_script(script_code, repo_path)

            if test_results and isinstance(test_results, list):
                scores = []
                for tr in test_results:
                    task = tr.get('task', '')
                    passed = tr.get('passed', False)
                    max_score = tr.get('max_score', 10)
                    detail = tr.get('detail', '')
                    scores.append({
                        'task': task,
                        'score': max_score if passed else 0,
                        'max_score': max_score,
                        'reason': detail if not passed else 'passed',
                    })
                return {'id': item_id, 'round': round_num, 'scores': scores}

        except Exception:
            pass
        if attempt < max_retries - 1:
            time.sleep(BACKOFF_BASE * (2 ** attempt))

    return {
        'id': item_id, 'round': round_num,
        'scores': [{'task': c['task'], 'score': 0, 'max_score': c.get('max_score', 10),
                    'reason': 'test_generation_failed'} for c in interactive_items],
        'error': 'failed_after_retries'
    }


def main():
    parser = argparse.ArgumentParser(description='Step 3b: Interaction Test')
    parser.add_argument('--step1-log', default=STEP1_LOG)
    parser.add_argument('--step2-output', default=STEP2_OUTPUT)
    parser.add_argument('--output', default=STEP3B_OUTPUT)
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--max-workers', type=int, default=MAX_WORKERS_CODE_JUDGE)
    parser.add_argument('--max-retries', type=int, default=MAX_RETRIES)
    parser.add_argument('--watch', type=int, default=0, metavar='SECONDS')
    parser.add_argument('--idle-exit', type=int, default=30, metavar='ROUNDS')
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.output))

    def run_once():
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

        print(f"[Step3b] repos={len(repo_entries)}, checklists={len(checklist_map)}, 待处理={len(pending)}")

        if not pending:
            return 0

        counter = {'ok': 0, 'error': 0}

        with tqdm(total=len(pending), desc="Step3b InteractionTest") as pbar:
            with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                futures = {
                    executor.submit(
                        test_one, e['id'], e['repo_path'], checklist_map[e['id']],
                        args.model, args.max_retries, e['round']
                    ): e
                    for e in pending
                }
                for future in as_completed(futures):
                    result = future.result()
                    append_jsonl_threadsafe(args.output, result, write_lock)

                    if result.get('scores') is not None and not result.get('error'):
                        counter['ok'] += 1
                    else:
                        counter['error'] += 1

                    pbar.update(1)
                    pbar.set_postfix(**counter)

        print(f"[Step3b] 本轮完成: 成功={counter['ok']}, 失败={counter['error']}")
        return len(pending)

    if args.watch > 0:
        idle_rounds = 0
        while idle_rounds < args.idle_exit:
            processed = run_once()
            if processed == 0:
                idle_rounds += 1
                print(f"[Step3b] 无新数据 ({idle_rounds}/{args.idle_exit})，{args.watch}s 后重试...")
            else:
                idle_rounds = 0
            time.sleep(args.watch)
        print("[Step3b] 长时间无新数据，退出 watch 模式")
    else:
        run_once()


if __name__ == '__main__':
    main()
