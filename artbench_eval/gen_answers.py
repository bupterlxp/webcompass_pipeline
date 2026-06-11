#!/usr/bin/env python3
"""连 vllm OpenAI 接口，对 62 题并发生成答案，存成 benchmark 输入格式。
用法: python gen_answers.py <served_model_name> <out_jsonl>
"""
import sys, json, asyncio, aiohttp

SUBSET = "/share/leixinping/sft_train/8b-vl-sft/artbench_eval/subset_62.jsonl"
URL = "http://localhost:8000/v1/chat/completions"
CONC = 62           # 8卡H800,62题全并发
MAX_TOKENS = None   # 不设输出上限，由 vllm 的 max-model-len 兜底

model_name = sys.argv[1]
out_path = sys.argv[2]

rows = [json.loads(l) for l in open(SUBSET) if l.strip()]

async def gen(session, row, sem, results):
    async with sem:
        q = row["question"]
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": q}],
            "temperature": 0.7,
            "top_p": 0.8,
        }
        if MAX_TOKENS:
            payload["max_tokens"] = MAX_TOKENS
        for attempt in range(3):
            try:
                async with session.post(URL, json=payload) as r:
                    d = await r.json()
                    ans = d["choices"][0]["message"]["content"]
                    fr = d["choices"][0]["finish_reason"]
                    out = dict(row)
                    out["answer"] = ans
                    out["finish_reason"] = fr
                    results.append(out)
                    print(f"  idx={row['index']} done ({len(ans)} chars, {fr})", flush=True)
                    return
            except Exception as e:
                if attempt == 2:
                    print(f"  idx={row['index']} FAILED: {e}", flush=True)
                    out = dict(row); out["answer"] = ""; out["finish_reason"] = "error"
                    results.append(out)
                await asyncio.sleep(2)

async def main():
    sem = asyncio.Semaphore(CONC)
    results = []
    timeout = aiohttp.ClientTimeout(total=1200)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        await asyncio.gather(*[gen(session, row, sem, results) for row in rows])
    results.sort(key=lambda x: x["index"])
    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = sum(1 for r in results if r["answer"])
    print(f"[{model_name}] 生成完成: {ok}/{len(results)} 有答案 -> {out_path}", flush=True)

asyncio.run(main())
