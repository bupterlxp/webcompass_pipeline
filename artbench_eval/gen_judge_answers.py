#!/usr/bin/env python3
"""让裁判模型(gemini-3.1-pro)自己做这 62 题，生成答案文件作为参考线。
输出格式与 answers_{model}.jsonl 一致，供 score.py 评分。
用法: python gen_judge_answers.py <subset_jsonl> <out_answers_jsonl>
"""
import sys, os, json, time
import concurrent.futures as cf
from openai import OpenAI

SRC = sys.argv[1]
OUT = sys.argv[2]
NUM_WORKERS = 10
MAX_TOKENS = 16384  # 网页代码很长，给足
MODEL = "ep-2njmct-1780110282090259280"  # gemini-3.1-pro（与裁判同一个）
client = OpenAI(base_url="http://wanqing.internal/api/gateway/v1/endpoints",
                api_key=os.environ["WQ_API_KEY"])

rows = [json.loads(l) for l in open(SRC) if l.strip()]
print(f"待生成 {len(rows)} 题", flush=True)


def gen_one(row):
    idx = row["index"]
    q = row["question"]
    for attempt in range(5):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": q}],
                max_tokens=MAX_TOKENS, temperature=0.0)
            ans = r.choices[0].message.content or ""
            fr = r.choices[0].finish_reason
            return idx, ans, fr
        except Exception as e:
            if attempt == 4:
                return idx, "", f"err:{str(e)[:100]}"
            time.sleep(5 + attempt * 3)


results = {}
with cf.ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
    futs = {ex.submit(gen_one, row): row["index"] for row in rows}
    done = 0
    for fut in cf.as_completed(futs):
        idx, ans, fr = fut.result()
        results[idx] = (ans, fr)
        done += 1
        print(f"  [{done}/{len(rows)}] idx={idx} len={len(ans)} finish={fr}", flush=True)

out_rows = []
for row in rows:
    ans, fr = results.get(row["index"], ("", "missing"))
    out_rows.append({
        "index": row["index"],
        "question": row["question"],
        "checklist": row["checklist"],
        "class": row.get("class"),
        "difficulty": row.get("difficulty"),
        "answer": ans,
        "finish_reason": fr,
    })
with open(OUT, "w") as f:
    for r in out_rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

n_ok = sum(1 for r in out_rows if r["answer"])
print(f"\n生成完成: {n_ok}/{len(rows)} 有答案 -> {OUT}", flush=True)
