#!/bin/bash
### 逐个模型：起 vllm -> 等就绪 -> 生成62题答案 -> 停 vllm 清显存
### 用法: bash run_gen_all.sh
set -u
VLLM_PY=/share/xiongjunqi/vllm_env/bin/python
EVAL=/share/leixinping/sft_train/8b-vl-sft/artbench_eval
ANS_DIR=$EVAL/answers
mkdir -p $ANS_DIR

# 模型清单： 名称|路径
MODELS=(
  "base|/share/baoyoujun/zhuzihao/model_scope_download/Qwen3-VL-8B-Instruct"
  "ckpt100|/share/leixinping/sft_train/8b-vl-sft/output/qwen3vl-8b-text-sft/checkpoint-100"
  "ckpt200|/share/leixinping/sft_train/8b-vl-sft/output/qwen3vl-8b-text-sft/checkpoint-200"
  "ckpt300|/share/leixinping/sft_train/8b-vl-sft/output/qwen3vl-8b-text-sft/checkpoint-300"
  "ckpt306|/share/leixinping/sft_train/8b-vl-sft/output/qwen3vl-8b-text-sft/checkpoint-306"
)

stop_vllm() {
  pkill -9 -f "vllm.entrypoints.openai.api_server" 2>/dev/null
  pkill -9 -f "VLLM::EngineCore" 2>/dev/null
  pkill -9 -f "VLLM::Worker" 2>/dev/null
  sleep 6
  # fuser 兜底清僵尸显存，循环直到显存真释放(最多5轮)
  for r in 1 2 3 4 5; do
    RP=$(fuser /dev/nvidia* 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u)
    [ -z "$RP" ] && break
    echo "fuser kill(轮$r): $RP"; for p in $RP; do kill -9 $p 2>/dev/null; done
    sleep 6
  done
}

for entry in "${MODELS[@]}"; do
  name="${entry%%|*}"; path="${entry##*|}"
  out="$ANS_DIR/answers_${name}.jsonl"
  if [ -f "$out" ] && [ $(wc -l < "$out") -eq 62 ]; then
    echo "==== $name 已有完整答案，跳过 ===="; continue
  fi
  echo "==================== 模型: $name ===================="
  echo "路径: $path"
  stop_vllm
  echo "--- 起 vllm ---"
  nohup $VLLM_PY -m vllm.entrypoints.openai.api_server \
    --model "$path" --served-model-name evalmodel \
    --tensor-parallel-size 8 --gpu-memory-utilization 0.85 \
    --max-model-len 65536 --port 8000 --trust-remote-code \
    > /tmp/vllm_eval_${name}.log 2>&1 &
  # 等就绪
  echo "--- 等待就绪 ---"
  for i in $(seq 1 120); do
    if curl -s --max-time 3 http://localhost:8000/v1/models 2>/dev/null | grep -q evalmodel; then
      echo "就绪 (${i}0s)"; break
    fi
    sleep 10
  done
  echo "--- 生成答案 ---"
  $VLLM_PY $EVAL/gen_answers.py evalmodel "$out"
  echo "--- 停 vllm ---"
  stop_vllm
done
echo "ALL_GEN_DONE"
