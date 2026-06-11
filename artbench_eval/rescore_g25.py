#!/usr/bin/env python3
"""只对已评分文件里 judge_score 为空的题重判，原地更新（更稳健的重试+解析）。
用法: python rescore_missing.py scored/scored_{m}.jsonl shots/{m}
"""
import sys, os, json, base64, time, re
import concurrent.futures as cf

sys.path.insert(0, "/share/leixinping/sft_train/8b-vl-sft/ArtifactsBenchmark/src")
from utils import extract_information
from prompts.prompt_mllm_check import get_prompt_mllm_checklist
from extract_ans import extract_mllm_overall
from openai import OpenAI

SCORED = sys.argv[1]
SHOTS = sys.argv[2]
COUNT = 3
NUM_WORKERS = 8  # 调小并发，降低 API 限流
JUDGE_MODEL = "ep-1npj58-1780842260886255607"  # gemini-2.5-pro
client = OpenAI(base_url="http://wanqing.internal/api/gateway/v1/endpoints",
                api_key=os.environ["WQ_API_KEY"])

SCORE_SUFFIX = (
    "\n\nIMPORTANT OUTPUT FORMAT: First score each checklist dimension, then you MUST "
    "end your response with a single JSON object on its own, exactly like:\n"
    "```json\n{\"Overall Score\": \"<sum of all dimension scores, 0-100>\"}\n```\n"
)


def robust_score(idx, out):
    s = extract_mllm_overall(idx, out)
    if s not in (None, ""):
        try:
            return float(str(s).split("-")[0])
        except Exception:
            pass
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", out, re.S)
    blocks += re.findall(r"(\{(?:[^{}]|\{[^{}]*\})*\})", out, re.S)
    for blk in blocks:
        try:
            obj = json.loads(blk)
        except Exception:
            continue
        tot, got = 0.0, False
        for v in obj.values():
            if isinstance(v, dict) and "score" in v:
                try:
                    tot += float(v["score"]); got = True
                except Exception:
                    pass
        if got:
            return tot
    nums = re.findall(r'"score"\s*:\s*"?(\d+(?:\.\d+)?)"?', out)
    if 1 <= len(nums) <= 20:
        return sum(float(n) for n in nums)
    # 4) Markdown 格式：**Score: 8/10** / Score: 8 / "Score": 8（裁判常用逐维度标题式输出）
    md = re.findall(r'[Ss]core\**\s*[:：]\s*\**\s*(\d+(?:\.\d+)?)\s*(?:/\s*10)?', out)
    if 1 <= len(md) <= 20:
        return sum(float(n) for n in md)
    return None


rows = [json.loads(l) for l in open(SCORED) if l.strip()]
todo = [r for r in rows if r.get("judge_score") in (None, "")]
print(f"{os.path.basename(SCORED)}: 待重判 {len(todo)}/{len(rows)}", flush=True)


def judge_one(row):
    idx = row["index"]
    try:
        img_path, query, ans = extract_information(idx, row, COUNT, SHOTS)
        if not ans:
            return idx, {"score": None, "reason": "no_answer"}
        prompt = get_prompt_mllm_checklist(row["checklist"], query, ans) + SCORE_SUFFIX
        content = [{"type": "text", "text": prompt}]
        if img_path:
            for p in img_path:
                if p and os.path.exists(p):
                    b64 = base64.b64encode(open(p, "rb").read()).decode()
                    content.append({"type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{b64}"}})
        for attempt in range(5):  # 更多重试
            try:
                r = client.chat.completions.create(
                    model=JUDGE_MODEL,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=32768, temperature=0.0)
                out = r.choices[0].message.content
                score = robust_score(idx, out)
                return idx, {"score": score, "has_img": bool(img_path),
                             "reason": None if score is not None else "parse_fail"}
            except Exception as e:
                if attempt == 4:
                    return idx, {"score": None, "reason": f"judge_err:{str(e)[:100]}"}
                time.sleep(5 + attempt * 3)
    except Exception as e:
        return idx, {"score": None, "reason": f"render_err:{str(e)[:120]}"}


results = {}
with cf.ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
    futs = {ex.submit(judge_one, row): row["index"] for row in todo}
    done = 0
    for fut in cf.as_completed(futs):
        idx, res = fut.result()
        results[idx] = res
        done += 1
        print(f"  [{done}/{len(todo)}] idx={idx} score={res.get('score')} reason={res.get('reason')}", flush=True)

# 原地合并更新
n_fixed = 0
for r in rows:
    res = results.get(r["index"])
    if res and res.get("score") is not None:
        r["judge_score"] = res["score"]
        r["judge_reason"] = None
        r["judge_has_img"] = res.get("has_img")
        n_fixed += 1
    elif res:
        r["judge_reason"] = res.get("reason")

with open(SCORED, "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

scores = [float(r["judge_score"]) for r in rows if r.get("judge_score") not in (None, "")]
print(f"\n[{os.path.basename(SCORED)}] 本轮补回 {n_fixed} 题, 现有分 {len(scores)}/{len(rows)}, "
      f"平均分={sum(scores)/len(scores) if scores else 0:.2f}", flush=True)
