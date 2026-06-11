#!/usr/bin/env python3
"""ArtifactsBenchmark 评分脚本（独立版，用标准 OpenAI 接口调 gemini-3.1-pro 当裁判）。
流程：读某模型答案 jsonl -> 抽HTML渲染截图 -> 截图+question+checklist 发裁判 -> 解析总分(满分100)。
用法: python score.py <answers_jsonl> <out_scored_jsonl> <screenshots_dir>
注：裁判常逐项打分而不给 "Overall Score"，robust_score 做三级兜底（Overall->各项求和->正则求和）。
"""
import sys, os, json, base64, time, re
import concurrent.futures as cf

sys.path.insert(0, "/share/leixinping/sft_train/8b-vl-sft/ArtifactsBenchmark/src")
from utils import extract_information
from prompts.prompt_mllm_check import get_prompt_mllm_checklist
from extract_ans import extract_mllm_overall
from openai import OpenAI

ANS = sys.argv[1]
OUT = sys.argv[2]
SHOTS = sys.argv[3]
COUNT = 3
NUM_WORKERS = 16

JUDGE_MODEL = "ep-1npj58-1780842260886255607"  # gemini-2.5-pro (reasoning模型)
client = OpenAI(base_url="http://wanqing.internal/api/gateway/v1/endpoints",
                api_key=os.environ["WQ_API_KEY"])

SCORE_SUFFIX = (
    "\n\nIMPORTANT OUTPUT FORMAT: First score each checklist dimension, then you MUST "
    "end your response with a single JSON object on its own, exactly like:\n"
    "```json\n{\"Overall Score\": \"<sum of all dimension scores, 0-100>\"}\n```\n"
)

os.makedirs(SHOTS, exist_ok=True)
rows = [json.loads(l) for l in open(ANS) if l.strip()]


def robust_score(idx, out):
    """三级兜底解析裁判输出，返回 0-100 的总分（float）或 None。"""
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
    md = re.findall(r'[Ss]core\**\s*[:：]\s*\**\s*(\d+(?:\.\d+)?)\s*(?:/\s*10)?', out)
    if 1 <= len(md) <= 20:
        return sum(float(n) for n in md)
    return None


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
        for attempt in range(5):
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
    futs = {ex.submit(judge_one, row): row["index"] for row in rows}
    done = 0
    for fut in cf.as_completed(futs):
        idx, res = fut.result()
        results[idx] = res
        done += 1
        print(f"  [{done}/{len(rows)}] idx={idx} score={res.get('score')}", flush=True)

out_rows = []
for row in rows:
    r = dict(row)
    res = results.get(row["index"], {})
    r["judge_score"] = res.get("score")
    r["judge_reason"] = res.get("reason")
    r["judge_has_img"] = res.get("has_img")
    out_rows.append(r)
with open(OUT, "w") as f:
    for r in out_rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

scores = [float(res["score"]) for res in results.values() if res.get("score") not in (None, "")]
n_total = len(rows); n_scored = len(scores)
avg = sum(scores) / n_scored if scores else 0
print(f"\n[{os.path.basename(ANS)}] 评分完成: {n_scored}/{n_total} 有分, 平均分={avg:.2f} (满分100)", flush=True)
print(f"AVG_SCORE={avg:.4f} SCORED={n_scored}/{n_total}", flush=True)
