#!/bin/bash
# Pipeline 编排脚本
# 用法:
#   bash run_all.sh                    # 串行模式（默认，同以前）
#   bash run_all.sh --steps 1,2,3      # 只跑指定步骤
#   bash run_all.sh --decouple         # 解耦模式：所有步骤并行，step3/4/5 自动轮询上游

set -e
cd "$(dirname "$0")"

MODE="serial"
STEPS="1,2,3,4,5"

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --decouple)
            MODE="decouple"
            shift
            ;;
        --steps)
            STEPS="$2"
            shift 2
            ;;
        *)
            STEPS="$1"
            shift
            ;;
    esac
done

# ============================================
#  解耦模式
# ============================================
if [ "$MODE" = "decouple" ]; then
    LOG_DIR="output/logs"
    mkdir -p "$LOG_DIR"

    echo "============================================"
    echo "  Data Filter Pipeline (解耦模式)"
    echo "  生成: Deepseek-v4-pro | 评分: Gemini-3.1-Pro"
    echo "  所有步骤并行启动，日志在 $LOG_DIR/"
    echo "============================================"

    python3 step1_inference.py --model Deepseek-v4-pro > "$LOG_DIR/step1.log" 2>&1 &
    PID1=$!
    echo "[Step 1] Inference        PID=$PID1  (Deepseek-v4-pro)"

    python3 step2_checklist.py --model Gemini-3.1-Pro > "$LOG_DIR/step2.log" 2>&1 &
    PID2=$!
    echo "[Step 2] Checklist        PID=$PID2  (Gemini-3.1-Pro)"

    python3 step3_code_judge.py --model Gemini-3.1-Pro --watch 30 --idle-exit 30 > "$LOG_DIR/step3.log" 2>&1 &
    PID3=$!
    echo "[Step 3] Code Judge       PID=$PID3  (Gemini-3.1-Pro, 每30s轮询)"

    python3 step4_screenshot_judge.py --model Gemini-3.1-Pro --watch 60 --idle-exit 30 > "$LOG_DIR/step4.log" 2>&1 &
    PID4=$!
    echo "[Step 4] Screenshot Judge PID=$PID4  (Gemini-3.1-Pro, 每60s轮询)"

    python3 step5_filter.py --watch 120 --idle-exit 30 > "$LOG_DIR/step5.log" 2>&1 &
    PID5=$!
    echo "[Step 5] Filter           PID=$PID5  (每120s轮询)"

    echo ""
    echo "查看实时日志:  tail -f $LOG_DIR/*.log"
    echo "停止全部:      kill $PID1 $PID2 $PID3 $PID4 $PID5"
    echo ""

    # 等待所有进程结束
    wait $PID1 && echo "[Step 1] 完成" || echo "[Step 1] 异常退出"
    wait $PID2 && echo "[Step 2] 完成" || echo "[Step 2] 异常退出"
    wait $PID3 && echo "[Step 3] 完成" || echo "[Step 3] 异常退出"
    wait $PID4 && echo "[Step 4] 完成" || echo "[Step 4] 异常退出"
    wait $PID5 && echo "[Step 5] 完成" || echo "[Step 5] 异常退出"

    echo ""
    echo "============================================"
    echo "  Pipeline 全部完成!"
    echo "============================================"
    exit 0
fi

# ============================================
#  串行模式（原有逻辑）
# ============================================
echo "============================================"
echo "  Data Filter Pipeline"
echo "  Steps: $STEPS"
echo "============================================"

# Step 1 和 Step 2 可以并行
if echo "$STEPS" | grep -q "1" && echo "$STEPS" | grep -q "2"; then
    echo ""
    echo "[Step 1 & 2] 并行运行: Inference + Checklist"
    echo "--------------------------------------------"
    python3 step1_inference.py &
    PID1=$!
    python3 step2_checklist.py &
    PID2=$!
    wait $PID1
    echo "[Step 1] 完成"
    wait $PID2
    echo "[Step 2] 完成"
elif echo "$STEPS" | grep -q "1"; then
    echo ""
    echo "[Step 1] Inference"
    echo "--------------------------------------------"
    python3 step1_inference.py
elif echo "$STEPS" | grep -q "2"; then
    echo ""
    echo "[Step 2] Checklist"
    echo "--------------------------------------------"
    python3 step2_checklist.py
fi

# Step 3 和 Step 4 可以并行
if echo "$STEPS" | grep -q "3" && echo "$STEPS" | grep -q "4"; then
    echo ""
    echo "[Step 3 & 4] 并行运行: Code Judge + Screenshot Judge"
    echo "--------------------------------------------"
    python3 step3_code_judge.py &
    PID3=$!
    python3 step4_screenshot_judge.py &
    PID4=$!
    wait $PID3
    echo "[Step 3] 完成"
    wait $PID4
    echo "[Step 4] 完成"
elif echo "$STEPS" | grep -q "3"; then
    echo ""
    echo "[Step 3] Code Judge"
    echo "--------------------------------------------"
    python3 step3_code_judge.py
elif echo "$STEPS" | grep -q "4"; then
    echo ""
    echo "[Step 4] Screenshot Judge"
    echo "--------------------------------------------"
    python3 step4_screenshot_judge.py
fi

# Step 5
if echo "$STEPS" | grep -q "5"; then
    echo ""
    echo "[Step 5] Filter"
    echo "--------------------------------------------"
    python3 step5_filter.py
fi

echo ""
echo "============================================"
echo "  Pipeline 完成!"
echo "============================================"
