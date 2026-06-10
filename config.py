"""
Pipeline 共享配置

所有 API 模型注册、路径、并发、阈值等均在此文件统一管理。
新增模型只需在 MODEL_REGISTRY 中添加一条即可。

API Key 通过环境变量注入，本地开发时请创建 .env 文件（已在 .gitignore 中排除）。
"""

import os as _os
from pathlib import Path as _Path

# =====================================================================
#  从 .env 文件加载环境变量（如果存在）
# =====================================================================
_env_file = _Path(__file__).parent / ".env"
if _env_file.exists():
    with open(_env_file, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _os.environ.setdefault(_k.strip(), _v.strip())

# =====================================================================
#  API Key 环境变量
# =====================================================================
_WANQING_KEY = _os.environ.get("WANQING_API_KEY", "")
_ROUTIFY_KEY = _os.environ.get("ROUTIFY_API_KEY", "")
_DASHSCOPE_KEY = _os.environ.get("DASHSCOPE_API_KEY", "")
_DOUBAO_KEY = _os.environ.get("DOUBAO_API_KEY", "")
_QWEN3_CODER_KEY = _os.environ.get("QWEN3_CODER_API_KEY", "")
_GPT5_KEY = _os.environ.get("GPT5_API_KEY", "")
_DEEPSEEK_R1_KEY = _os.environ.get("DEEPSEEK_R1_API_KEY", "")
_GEMINI25PRO_KEY = _os.environ.get("GEMINI25PRO_API_KEY", "")
_CLAUDE_OPUS_KEY = _os.environ.get("CLAUDE_OPUS_API_KEY", "")
_QWEN37_MAX_KEY = _os.environ.get("QWEN37_MAX_API_KEY", "")

# =====================================================================
#  模型注册表  —— 新增 / 修改模型只需编辑这里
#  每个 key 是对外使用的模型别名，value 包含:
#    base_url : OpenAI-compatible API 地址
#    model_id : 实际传给 API 的 model 字段
#    api_key  : 鉴权密钥（从环境变量读取）
# =====================================================================
MODEL_REGISTRY = {
    "Gemini-3.1-Pro": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-g9c0rd-1776189746510635625",
        "api_key":  _WANQING_KEY,
    },
    "claude-opus-4-6": {
        "base_url": "https://routify-pub.alibaba-inc.com/protocol/openai/v1",
        "model_id": "claude-opus-4-6-20260205",
        "api_key":  _ROUTIFY_KEY,
    },
    "qwen3.6-plus": {
        "base_url": "https://app-hk.ppapi.ai/v1",
        "model_id": "qwen3.6-plus",
        "api_key":  _QWEN37_MAX_KEY,
    },
    "Qwen3-Max": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_id": "qwen3-max",
        "api_key":  _DASHSCOPE_KEY,
    },
    "Qwen3-VL-32B-Instruct": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-qawpum-1768916716519538858",
        "api_key":  _WANQING_KEY,
    },
    "doubao-seed-1-8-251228-thinking": {
        "base_url": "http://14.103.68.46/v1",
        "model_id": "doubao-seed-1-8-251228-thinking",
        "api_key":  _DOUBAO_KEY,
        "thinking": True,
    },
    "MiniMax-M2.1": {
        "base_url": "http://10.48.88.226:17878/v1",
        "model_id": "kwaipilot_model",
        "api_key":  _WANQING_KEY,
    },
    "GLM-4.7": {
        "base_url": "http://10.48.88.226:17878/v1",
        "model_id": "kwaipilot_model",
        "api_key":  _WANQING_KEY,
    },
    "Gemini-3-Flash": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-8w9vvg-1767852769298778463",
        "api_key":  _WANQING_KEY,
    },
    "Deepseek-V3.2": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-p9rly5-1768916443761780320",
        "api_key":  _WANQING_KEY,
    },
    "Gemini-2.5-Flash": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-ryvuij-1767548103857838585",
        "api_key":  _WANQING_KEY,
    },
    "KAT-Coder-Pro-V1": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-kkaiur-1767520117901054060",
        "api_key":  _WANQING_KEY,
    },
    "Claude-4.5-Sonnet": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-eoxrq2-1767551947609474236",
        "api_key":  _WANQING_KEY,
    },
    "Gemini-3-Pro": {
        "base_url": "http://14.103.68.46/v1",
        "model_id": "gemini-3-pro-preview",
        "api_key":  _DOUBAO_KEY,
    },
    "Qwen3-Coder-480B": {
        "base_url": "http://wanqing.internal/api/agent/v1/apps",
        "model_id": "app-dsw4xd-1757654301803448727",
        "api_key":  _QWEN3_CODER_KEY,
    },
    "GPT-5": {
        "base_url": "http://wanqing.internal/api/agent/v1/apps",
        "model_id": "app-4lj8uu-1757909116059641172",
        "api_key":  _GPT5_KEY,
    },
    "Deepseek-R1-0528": {
        "base_url": "http://wanqing.internal/api/agent/v1/apps",
        "model_id": "app-839nz1-1759126476449313320",
        "api_key":  _DEEPSEEK_R1_KEY,
    },
    "GLM-4.5V": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-czndhm-1766406106266361745",
        "api_key":  _WANQING_KEY,
    },
    "Qwen3-VL-235B-A22B-Instruct": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-0rr3sg-1769954569769400592",
        "api_key":  _WANQING_KEY,
    },
    "Gemini-2.5-Pro": {
        "base_url": "http://wanqing.internal/api/agent/v1/apps",
        "model_id": "app-exhr1i-1757909494278942850",
        "api_key":  _GEMINI25PRO_KEY,
    },
    "MiniMax-M2": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-9ed4x4-1766979725319627755",
        "api_key":  _WANQING_KEY,
    },
    "GPT-5.2": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-xm8qyg-1768815018029154582",
        "api_key":  _WANQING_KEY,
    },
    "Claude-Opus-4.5": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-5b9ezm-1768964270166908191",
        "api_key":  _CLAUDE_OPUS_KEY,
    },
    "Qwen3-8B": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-840m4r-1769583745464083649",
        "api_key":  _WANQING_KEY,
    },
    "Kimi-K2.5": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-qseqgr-1769938013519203411",
        "api_key":  _WANQING_KEY,
    },
    "Qwen3-VL-30B-A3B-Instruct": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-0qdli0-1770139500567664793",
        "api_key":  _WANQING_KEY,
    },
    "Qwen3-32B": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-xursx4-1772422818748794214",
        "api_key":  _WANQING_KEY,
    },
    "Qwen3-VL-30B-A3B-Thinking": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-sjdtmv-1772867188020498151",
        "api_key":  _WANQING_KEY,
    },
    "Qwen3-VL-235B-A22B-Thinking": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-sraqqn-1772867277214155072",
        "api_key":  _WANQING_KEY,
    },
    "Deepseek-v4-pro": {
        "base_url": "http://wanqing.internal/api/gateway/v1/endpoints",
        "model_id": "ep-xr2rp2-1778509411434814651",
        "api_key":  _WANQING_KEY,
    },
    "Qwen3.7-Max": {
        "base_url": "https://app-hk.ppapi.ai/v1",
        "model_id": "qwen3.7-max",
        "api_key":  _QWEN37_MAX_KEY,
        "thinking": True,
    },
}

# =====================================================================
#  Pipeline 配置
# =====================================================================

# --- 输入 ---
INPUT_JSONL = "/share/leixinping/opensource_data/generation/all_merged_instructions.jsonl"

# --- 输出根目录 ---
OUTPUT_ROOT = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "output")
REPOS_DIR = f"{OUTPUT_ROOT}/repos"

# --- 各步骤输出文件 ---
STEP1_LOG = f"{OUTPUT_ROOT}/step1_inference_log.jsonl"
STEP1_RESPONSES = f"{OUTPUT_ROOT}/step1_responses.jsonl"
STEP2_OUTPUT = f"{OUTPUT_ROOT}/step2_checklists.jsonl"
STEP3_OUTPUT = f"{OUTPUT_ROOT}/step3_code_scores.jsonl"
STEP3B_OUTPUT = f"{OUTPUT_ROOT}/step3b_interaction_scores.jsonl"
STEP4_OUTPUT = f"{OUTPUT_ROOT}/step4_visual_scores.jsonl"
STEP5_OUTPUT = f"{OUTPUT_ROOT}/step5_filtered.jsonl"

# --- 默认模型 ---
MODEL = "Deepseek-v4-pro"

# --- 并发 ---
MAX_WORKERS_INFERENCE = 4
MAX_WORKERS_CHECKLIST = 8
MAX_WORKERS_CODE_JUDGE = 8
MAX_WORKERS_SCREENSHOT = 2

# --- 重试 ---
MAX_RETRIES = 3
BACKOFF_BASE = 0.8

# --- 筛选阈值 ---
SCORE_THRESHOLD = 70  # 满分 100

# --- 代码读取 ---
CODE_EXTENSIONS = {".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".json"}
MAX_CODE_LENGTH = 150000
