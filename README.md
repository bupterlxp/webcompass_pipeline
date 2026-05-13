# WebCompass Pipeline

A multi-step data filter pipeline for generating, evaluating, and filtering LLM-generated web project code. The pipeline takes web design instructions as input, generates code repositories via LLM, and evaluates them through code review and visual screenshot analysis.

## Pipeline Overview

```
Input (instructions.jsonl)
        │
        ├──► Step 1: Inference ──► Generate web project repos from instructions
        │
        ├──► Step 2: Checklist ──► Generate evaluation checklists per instruction
        │
        ├──► Step 3: Code Judge ──► Score repos against checklists (code review)
        │
        ├──► Step 4: Screenshot Judge ──► Score repos via visual screenshots
        │
        └──► Step 5: Filter ──► Combine scores, apply threshold, output filtered data
```

## Project Structure

```
├── config.py              # Centralized configuration (models, paths, thresholds)
├── call_model.py           # OpenAI-compatible API client (uses MODEL_REGISTRY)
├── parse_json.py           # Extract JSON from LLM markdown output
├── prompts.py              # Prompt templates for generation and evaluation
├── utils.py                # Shared utilities (JSONL I/O, code reading, etc.)
├── webhandler.py           # Web project screenshot capture (Playwright)
├── step1_inference.py      # Step 1: Generate web repos from instructions
├── step2_checklist.py      # Step 2: Generate evaluation checklists
├── step3_code_judge.py     # Step 3: Code-based scoring
├── step4_screenshot_judge.py  # Step 4: Visual scoring via screenshots
├── step5_filter.py         # Step 5: Score aggregation and filtering
├── run_retry.py            # Multi-round retry orchestrator (Best-of-N)
├── run_all.sh              # Pipeline orchestration script
├── .env.example            # Environment variable template
└── requirements.txt        # Python dependencies
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure API keys

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

### 3. Prepare input data

Place your input JSONL file at the path specified in `config.py` (`INPUT_JSONL`). Each line should contain:

```json
{"id": "unique_id", "instruction": "web design document text..."}
```

## Usage

### Serial mode (default)

```bash
bash run_all.sh
```

### Run specific steps

```bash
bash run_all.sh --steps 1,2,3
```

### Decoupled mode (all steps in parallel with polling)

```bash
bash run_all.sh --decouple
```

### Multi-round retry with Best-of-N

```bash
python3 run_retry.py --threshold 70 --max-rounds 5 --gen-model Deepseek-v4-pro --eval-model Gemini-3.1-Pro
```

### Run individual steps

```bash
python3 step1_inference.py --model Deepseek-v4-pro --max-workers 4
python3 step2_checklist.py --model Gemini-3.1-Pro --max-workers 8
python3 step3_code_judge.py --model Gemini-3.1-Pro --watch 30
python3 step4_screenshot_judge.py --model Gemini-3.1-Pro --watch 60
python3 step5_filter.py --threshold 70 --strategy average
```

## Configuration

All configuration is in `config.py`:

- **MODEL_REGISTRY**: Register new models by adding entries with `base_url`, `model_id`, and `api_key`
- **Concurrency**: `MAX_WORKERS_*` controls parallelism per step
- **Retry**: `MAX_RETRIES` and `BACKOFF_BASE` for API call retries
- **Threshold**: `SCORE_THRESHOLD` (default 70/100) for quality filtering
- **Scoring strategy**: `average`, `code-only`, or `visual-only`
