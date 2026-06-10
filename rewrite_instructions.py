#!/usr/bin/env python3
"""
把原始 instruction 用新模板风格重写，调用 Qwen3.7-Max API。
输出: new_instructions.jsonl
"""

import os
import sys
import json
import time
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from config import MODEL_REGISTRY
from utils import load_jsonl, append_jsonl_threadsafe, ensure_dir, call_api

write_lock = threading.Lock()

REWRITE_PROMPT = '''You are a senior UI/UX design architect. Your task is to transform a web page design document into a highly detailed design specification.

## STEP 0 — Read the original document FIRST and decide the theme brightness

Read the original design document below. Before writing anything, determine:
- What is this page about? (e.g. blog, e-commerce, game, dashboard, portfolio...)
- Who is the audience? (e.g. general consumers, developers, children, professionals...)
- Should it use a LIGHT or DARK background?

**THEME DECISION RULE**: Default to LIGHT. Over 80% of real-world web pages use light backgrounds. You MUST use a LIGHT background UNLESS the page is clearly about one of these NARROW categories:
  - First-person / immersive video games (FPS, RPG, battle royale) — NOT board games, card games, puzzles, or casual games
  - Movie theater / cinema / streaming video platforms
  - Nightclub / bar / nightlife venues
  - Space / sci-fi / cyberpunk themed pages
  - Music visualizers with full-screen album art

That's it. Everything else is LIGHT. Specifically:
  - Board games, card games, chess, puzzles → LIGHT (they simulate tabletop, which is lit)
  - Arcade / casual / 2D games → LIGHT (bright, colorful, fun)
  - Calculators, keyboard simulators, tools → LIGHT
  - Developer dashboards, admin panels, analytics → LIGHT
  - Dev tools landing pages, API docs → LIGHT
  - Blogs, news, articles → LIGHT
  - E-commerce, product pages → LIGHT
  - Portfolios, galleries → LIGHT
  - Educational pages → LIGHT
  - Food, recipes, restaurants → LIGHT
  - Travel, tourism → LIGHT
  - Social media, community → LIGHT
  - Business, corporate, SaaS → LIGHT
  - Healthcare, fitness → LIGHT
  - Finance, banking → LIGHT
  - NFT / Web3 marketplaces → LIGHT
  - Emoji / sticker / fun tools → LIGHT
  - Luxury / jewelry / fashion → LIGHT (cream/ivory, not black)
  - Sports news / stats → LIGHT
  - Podcast / audio pages → LIGHT
  - Remote work / tracking tools → LIGHT
  - Performance monitoring / benchmarks → LIGHT
  - Any page where the content doesn't scream "darkness" → LIGHT

For a LIGHT theme: background should be #F5+ range (e.g. #FFFFFF, #FAFAFA, #F8F6F0, #FFF9E6, #F0F4F8). Primary text should be dark (#1A-#3A range).
For a DARK theme: background should be #0A-#1A range. Primary text should be light (#E0+ range).

## Original Design Document
---
{instruction}
---

## Reference Template (follow ONLY the STRUCTURE/FORMAT below — ignore its specific colors, style name, and theme)
The template below uses a dark "Cyber-Industrial" style as an EXAMPLE. Do NOT copy its colors, fonts, or aesthetic. Only copy the SECTION STRUCTURE (A through F) and the 3-LAYER FORMAT ([用户感受] → [设计原理] → [技术实现]).

{template}

## Output Instructions
1. Rewrite the original document into the same structured format as the reference template (sections A through F). Derive ALL style decisions from the ORIGINAL document's content — the template is purely a structural reference.
2. For each section:
   - **A (页面基础输入信息)**: Extract from the original document's content and purpose. The style_name block at the top MUST include a creative, evocative style name (both English and Chinese), a vivid style_user_impression, style_animation_vibe, and palette_hex with **exactly 5-6 named color values** (e.g. `#2563EB (Royal Blue - Primary Action)`). The FIRST color in palette_hex MUST be the page background color — it must match your LIGHT/DARK decision from Step 0.
   - **B (全局视觉规范)**: Design an appropriate visual system. MUST include at least 5 sub-items (视觉一致性, 色彩系统, 字体系统, 图标系统, 组件系统, 图像/装饰). Each sub-item MUST have all 3 layers: [用户感受], [设计原理] with a bolded design principle name, and [技术实现] with concrete Tailwind/CSS code.
   - **C (交互与动效规范)**: MUST include at least 3 sub-items (基础交互反馈, 进场动画, 持续动态). Each with the 3-layer format.
   - **D (排版规范)**: MUST include at least 3 sub-items (栅格与对齐, 信息层级, 间距体系). Each with the 3-layer format.
   - **E (模块级规范)**: Break down the page into **6-8 modules** (MUST be at least 6). Each module MUST include: 模块目标, 排版规范 (with 3-layer format), and 视觉规范 (with 3-layer format). Name modules with both Chinese and descriptive English names.
   - **F (输出要求)**: Include: tech stack, font strategy (with specific Google Font names), key CSS/Tailwind implementations, copywriting tone guidance, code structure notes, image resource suggestions, and output format requirement.
3. Be creative and specific — each page should get a UNIQUE style system derived from its content. A children's game page should feel playful; a financial dashboard should feel precise and trustworthy; an art portfolio should feel elegant and minimal.
4. **Font diversity**: Do NOT default to "Inter" for every page. Choose fonts that match the page's character. Consider: Outfit, DM Sans, Space Grotesk (modern tech), Playfair Display, Cormorant Garamond, Merriweather (editorial/luxury), Fredoka, Baloo 2, Bubblegum Sans (playful), Source Sans 3, IBM Plex Sans (professional), Lora, Crimson Pro (classic). Monospace options beyond JetBrains Mono: IBM Plex Mono, Source Code Pro, Fira Code, Space Mono.
5. Include concrete CSS/Tailwind class names and hex color codes in ALL 技术实现 sections — never leave them vague.
6. Output ONLY the rewritten design specification. No extra commentary, no markdown code fences wrapping the whole output.
'''


def rewrite_one(item, model, template):
    item_id = item['id']
    instruction = item['instruction']

    prompt = REWRITE_PROMPT.replace('{template}', template).replace('{instruction}', instruction)

    for attempt in range(3):
        try:
            result = call_api(prompt, model, stream_print=False)
            if result and len(result) > 500:
                return {
                    'id': item_id,
                    'instruction': result,
                    'original_instruction': instruction,
                    'length': len(result),
                }
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1.5 * (2 ** attempt))

    return {
        'id': item_id,
        'instruction': instruction,
        'error': 'rewrite_failed',
        'length': len(instruction),
    }


def main():
    parser = argparse.ArgumentParser(description='Rewrite instructions with new template')
    parser.add_argument('--input', required=True)
    parser.add_argument('--template', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', default='Qwen3.7-Max')
    parser.add_argument('--max-workers', type=int, default=20)
    args = parser.parse_args()

    ensure_dir(os.path.dirname(args.output))

    with open(args.template, 'r', encoding='utf-8') as f:
        template = f.read()

    items = load_jsonl(args.input)
    print(f"共 {len(items)} 条")

    done_ids = set()
    if os.path.exists(args.output):
        for line in open(args.output, 'r', encoding='utf-8'):
            try:
                obj = json.loads(line.strip())
                done_ids.add(obj['id'])
            except (json.JSONDecodeError, KeyError):
                continue

    pending = [item for item in items if item['id'] not in done_ids]
    print(f"已完成 {len(done_ids)} 条，待处理 {len(pending)} 条")

    if not pending:
        print("全部完成")
        return

    counter = {'ok': 0, 'error': 0}

    with tqdm(total=len(pending), desc="Rewrite Instructions") as pbar:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(rewrite_one, item, args.model, template): item
                for item in pending
            }
            for future in as_completed(futures):
                result = future.result()
                append_jsonl_threadsafe(args.output, result, write_lock)
                if result.get('error'):
                    counter['error'] += 1
                else:
                    counter['ok'] += 1
                pbar.update(1)
                pbar.set_postfix(**counter)

    print(f"\n完成! 成功={counter['ok']}, 失败={counter['error']}")


if __name__ == '__main__':
    main()
