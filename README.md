# WebCompass Pipeline

多步骤数据过滤流水线，用于生成、评估和筛选 LLM 生成的网页项目代码。流水线接收网页设计指令作为输入，通过 LLM 生成代码仓库，并通过代码审查和视觉截图分析进行评估。

## 流水线概览

```
输入 (instructions.jsonl)
        │
        ├──► Step 1: 推理生成 ──► 根据指令生成网页项目仓库
        │
        ├──► Step 2: 清单生成 ──► 为每条指令生成评估清单
        │
        ├──► Step 3: 代码评分 ──► 基于代码内容对清单逐项打分
        │
        ├──► Step 4: 截图评分 ──► 启动网页截图进行视觉评分
        │
        └──► Step 5: 筛选过滤 ──► 合并分数、应用阈值、输出高质量数据
```

## 项目结构

```
├── config.py                  # 统一配置（模型注册、路径、阈值等）
├── call_model.py              # OpenAI 兼容 API 客户端（使用 MODEL_REGISTRY）
├── parse_json.py              # 从 LLM 输出中提取 JSON
├── prompts.py                 # 生成和评估的 Prompt 模板
├── utils.py                   # 共享工具函数（JSONL 读写、代码读取等）
├── webhandler.py              # 网页项目截图工具（Playwright）
├── step1_inference.py         # Step 1: 根据指令生成网页代码仓库
├── step2_checklist.py         # Step 2: 生成评估清单
├── step3_code_judge.py        # Step 3: 基于代码的评分
├── step4_screenshot_judge.py  # Step 4: 基于截图的视觉评分
├── step5_filter.py            # Step 5: 分数汇总与筛选
├── run_retry.py               # 多轮重试编排器（Best-of-N 选择）
├── run_all.sh                 # 流水线编排脚本
├── .env.example               # 环境变量模板
└── requirements.txt           # Python 依赖
```

## 安装

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 API Key

将 `.env.example` 复制为 `.env` 并填入真实的 API Key：

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 3. 准备输入数据

将输入 JSONL 文件放到 `config.py` 中 `INPUT_JSONL` 指定的路径。每行格式：

```json
{"id": "唯一ID", "instruction": "网页设计文档内容..."}
```

## 使用方式

### 串行模式（默认）

```bash
bash run_all.sh
```

### 仅运行指定步骤

```bash
bash run_all.sh --steps 1,2,3
```

### 解耦模式（所有步骤并行，自动轮询上游数据）

```bash
bash run_all.sh --decouple
```

### 多轮重试 + Best-of-N 选择

```bash
python3 run_retry.py --threshold 70 --max-rounds 5 --gen-model Deepseek-v4-pro --eval-model Gemini-3.1-Pro
```

### 单独运行各步骤

```bash
python3 step1_inference.py --model Deepseek-v4-pro --max-workers 4
python3 step2_checklist.py --model Gemini-3.1-Pro --max-workers 8
python3 step3_code_judge.py --model Gemini-3.1-Pro --watch 30
python3 step4_screenshot_judge.py --model Gemini-3.1-Pro --watch 60
python3 step5_filter.py --threshold 70 --strategy average
```

## 配置说明

所有配置集中在 `config.py` 中：

- **MODEL_REGISTRY**：模型注册表，新增模型只需添加 `base_url`、`model_id`、`api_key` 三个字段
- **并发控制**：`MAX_WORKERS_*` 控制各步骤的并行数
- **重试策略**：`MAX_RETRIES`（最大重试次数）和 `BACKOFF_BASE`（退避基数）
- **筛选阈值**：`SCORE_THRESHOLD`（默认 70/100）
- **评分策略**：`average`（代码+视觉平均）、`code-only`（仅代码）、`visual-only`（仅视觉）
